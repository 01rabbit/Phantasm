from __future__ import annotations

import logging
import os
import pathlib
import re
import signal
import socket
import subprocess
import sys
import threading
import time
from typing import Callable

from ..config import (
    state_dir,
    web_host,
    web_host_is_explicit,
    web_port,
    webui_gadget_exposure_enabled,
)

LOG = logging.getLogger(__name__)


class WebUIService:
    """Manages the WebUI subprocess and inactivity auto-kill timer.

    Singleton construction is lock-protected.  Process lifecycle methods are
    intended for the TUI control path and timer callback; pid-file and socket
    probes remain best-effort observations, not inter-process locks.
    """

    _instance: WebUIService | None = None
    _lock = threading.Lock()

    def __new__(cls) -> WebUIService:
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init_service()
            return cls._instance

    def _init_service(self) -> None:
        self._process: subprocess.Popen | None = None
        self._timer: threading.Timer | None = None
        self._timeout_seconds = 600  # 10 minutes
        self._on_timeout_cb: Callable[[], None] | None = None
        self._start_time: float | None = None
        self._host = self.resolve_bind_host()
        self._port = web_port()
        self._startup_failure_reason: str | None = None
        self._last_start_command: list[str] = []
        self._last_returncode: int | None = None
        self._last_port_check_failed = False

    def set_timeout_callback(self, callback: Callable[[], None]) -> None:
        """Set a callback to be executed when the WebUI is auto-killed."""
        self._on_timeout_cb = callback

    def is_running(self) -> bool:
        """Check if the WebUI process is currently running."""
        if self._process is not None and self._process.poll() is None:
            return True

        pid = self._read_pid()
        if pid is None and self._port_is_open(self._host, self._port):
            pid = self._find_listener_pid(self._port)
            if pid is not None:
                self._write_pid(pid)
        if pid is None:
            return False

        if not self._pid_is_alive(pid):
            self._clear_pid_file()
            return False

        if not self._port_is_open(self._host, self._port):
            self._clear_pid_file()
            return False

        return True

    def resolve_bind_host(self) -> str:
        """Return the host the WebUI should bind to.

        Loopback is the default, so the TUI control path never opens the WebUI
        to a network by itself.  USB gadget access is opt-in and resolves to the
        gadget interface address, never to all interfaces.  An explicit
        `PHASMID_HOST` always wins, including an operator-chosen `0.0.0.0`.
        """
        if web_host_is_explicit():
            return web_host()
        if webui_gadget_exposure_enabled():
            gadget_ip = self._detect_usb_gadget_ipv4()
            if gadget_ip is not None:
                return gadget_ip
            LOG.warning(
                "PHASMID_WEBUI_EXPOSE_GADGET is set but no USB gadget address "
                "was detected; binding to %s instead",
                web_host(),
            )
        return web_host()

    def start(self, host: str | None = None, port: int | None = None) -> bool:
        """Start the WebUI subprocess.

        `host` defaults to :meth:`resolve_bind_host` and `port` to
        `config.web_port()`, so the TUI `w` key and the documented environment
        configuration cannot disagree about the bind address.
        """
        host = self.resolve_bind_host() if host is None else host
        port = web_port() if port is None else port
        self._startup_failure_reason = None
        self._last_returncode = None
        self._last_port_check_failed = False
        self._host = host
        self._port = port
        if self.is_running():
            return True

        env = os.environ.copy()
        env["PHASMID_HOST"] = host
        env["PHASMID_PORT"] = str(port)

        cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            "phasmid.web_server:app",
            "--host",
            host,
            "--port",
            str(port),
        ]
        self._last_start_command = cmd[:]
        log_path = self.log_file
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_fh = log_path.open("a", encoding="utf-8")

        try:
            self._process = subprocess.Popen(
                cmd,
                env=env,
                stdout=log_fh,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            self._start_time = time.time()
            self._write_pid(self._process.pid)
            if not self._wait_for_startup():
                self._last_returncode = self._process.poll() if self._process else None
                self._last_port_check_failed = True
                self._startup_failure_reason = self._build_startup_failure_reason()
                self._cleanup_failed_process()
                return False
            self.reset_timer()
            return True
        except Exception as exc:
            self._startup_failure_reason = (
                f"WebUI launch exception: {exc}. "
                f"Command: {' '.join(self._last_start_command)}. "
                f"Log file: {self.log_file}"
            )
            self._clear_pid_file()
            return False
        finally:
            log_fh.close()

    def stop(self) -> None:
        """Stop the WebUI subprocess and cancel the timer."""
        self._cancel_timer()
        pid = None
        if self._process and self._process.poll() is None:
            pid = self._process.pid
        else:
            pid = self._read_pid()
            if pid is None and self._port_is_open(self._host, self._port):
                pid = self._find_listener_pid(self._port)

        if pid is not None:
            self._terminate_pid(pid, sig=signal.SIGTERM)
            if not self._wait_for_shutdown(pid, timeout=4.0):
                LOG.warning(
                    "WebUI process did not stop after SIGTERM; forcing SIGKILL (pid=%s)",
                    pid,
                )
                self._terminate_pid(pid, sig=signal.SIGKILL)
                self._wait_for_shutdown(pid, timeout=1.5)

        self._process = None
        self._start_time = None
        self._clear_pid_file()

    def reset_timer(self) -> None:
        """Reset the inactivity timer if the WebUI is running."""
        self._cancel_timer()
        if self.is_running():
            self._timer = threading.Timer(self._timeout_seconds, self._handle_timeout)
            self._timer.daemon = True
            self._timer.start()

    def _cancel_timer(self) -> None:
        if self._timer:
            self._timer.cancel()
            self._timer = None

    def _handle_timeout(self) -> None:
        """Triggered when the inactivity timer expires."""
        if self.is_running():
            self.stop()
            if self._on_timeout_cb:
                self._on_timeout_cb()

    @property
    def uptime_seconds(self) -> float:
        """Return the number of seconds the WebUI has been running."""
        if self._start_time is None:
            return 0.0
        return time.time() - self._start_time

    @property
    def pid_file(self) -> pathlib.Path:
        return pathlib.Path(state_dir()) / "webui.pid"

    @property
    def log_file(self) -> pathlib.Path:
        try:
            return pathlib.Path(state_dir()) / "webui.log"
        except Exception as exc:
            LOG.debug("webui log path resolution failed: %s", exc)
            return pathlib.Path("/tmp/phasmid-webui.log")

    @property
    def startup_failure_reason(self) -> str | None:
        return self._startup_failure_reason

    def access_url(self) -> str:
        """Return the URL for the address the WebUI is actually bound to."""
        host = self._host
        if host == "0.0.0.0":
            host = self._detect_usb_gadget_ipv4() or "127.0.0.1"
        return f"http://{host}:{self._port}"

    def _wait_for_startup(self, timeout: float = 10.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if self._process is None:
                return False
            if self._process.poll() is not None:
                return False
            if self._port_is_open(self._host, self._port):
                return True
            time.sleep(0.1)
        return False

    def _cleanup_failed_process(self) -> None:
        if self._process and self._process.poll() is None:
            self._terminate_pid(self._process.pid, sig=signal.SIGTERM)
            if not self._wait_for_shutdown(self._process.pid, timeout=2.0):
                self._terminate_pid(self._process.pid, sig=signal.SIGKILL)
                self._wait_for_shutdown(self._process.pid, timeout=1.0)
        self._process = None
        self._start_time = None
        self._clear_pid_file()

    def _wait_for_shutdown(self, pid: int, timeout: float = 2.0) -> bool:
        deadline = time.time() + timeout
        while time.time() < deadline:
            if not self._pid_is_alive(pid) and not self._port_is_open(
                self._host, self._port
            ):
                return True
            time.sleep(0.1)
        return False

    def _terminate_pid(self, pid: int, sig: int = signal.SIGTERM) -> None:
        try:
            os.killpg(os.getpgid(pid), sig)
        except Exception as exc:
            LOG.debug("webui process group termination failed: %s", exc)
            try:
                os.kill(pid, sig)
            except Exception as fallback_exc:
                LOG.debug("webui process termination failed: %s", fallback_exc)

    def _write_pid(self, pid: int) -> None:
        self.pid_file.parent.mkdir(parents=True, exist_ok=True)
        self.pid_file.write_text(f"{pid}\n", encoding="utf-8")

    def _read_pid(self) -> int | None:
        try:
            raw = self.pid_file.read_text(encoding="utf-8").strip()
        except FileNotFoundError:
            return None
        except OSError:
            return None

        if not raw:
            return None

        try:
            return int(raw)
        except ValueError:
            return None

    def _clear_pid_file(self) -> None:
        try:
            self.pid_file.unlink()
        except FileNotFoundError:
            pass
        except OSError as exc:
            LOG.debug("webui pid file cleanup failed: %s", exc)

    def _pid_is_alive(self, pid: int) -> bool:
        status_path = pathlib.Path(f"/proc/{pid}/stat")
        if status_path.exists():
            try:
                stat_text = status_path.read_text(encoding="utf-8")
                parts = stat_text.split()
                if len(parts) >= 3 and parts[2] == "Z":
                    return False
            except Exception as exc:
                LOG.debug("webui process status probe failed: %s", exc)
        try:
            os.kill(pid, 0)
        except OSError:
            return False
        return True

    def _port_is_open(self, host: str, port: int) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.1)
            return sock.connect_ex((host, port)) == 0

    def _find_listener_pid(self, port: int) -> int | None:
        try:
            output = subprocess.check_output(
                ["lsof", "-tiTCP:%d" % port, "-sTCP:LISTEN"],
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
        except (FileNotFoundError, subprocess.CalledProcessError, OSError):
            return None

        if not output:
            return None

        first_line = output.splitlines()[0].strip()
        try:
            return int(first_line)
        except ValueError:
            return None

    def _build_startup_failure_reason(self) -> str:
        cmd = (
            " ".join(self._last_start_command) if self._last_start_command else "<none>"
        )
        return (
            "WebUI startup failed. "
            f"Command: {cmd}. "
            f"Return code: {self._last_returncode}. "
            f"Port check failed: {self._last_port_check_failed}. "
            f"Log file: {self.log_file}"
        )

    def _detect_usb_gadget_ipv4(self) -> str | None:
        candidates = ["usb0", *self._list_gadget_like_interfaces()]
        seen: set[str] = set()
        for iface in candidates:
            if iface in seen:
                continue
            seen.add(iface)
            ip = self._first_preferred_ipv4_on_interface(iface)
            if ip is not None:
                return ip
        return None

    def _list_gadget_like_interfaces(self) -> list[str]:
        try:
            output = subprocess.check_output(
                ["ip", "-o", "link", "show"],
                stderr=subprocess.DEVNULL,
                text=True,
            )
        except (FileNotFoundError, subprocess.CalledProcessError, OSError):
            return []

        names: list[str] = []
        for line in output.splitlines():
            m = re.match(r"^\d+:\s+([^:]+):", line)
            if not m:
                continue
            name = m.group(1).split("@", 1)[0]
            if name.startswith("enx"):
                names.append(name)
        return names

    def _first_preferred_ipv4_on_interface(self, iface: str) -> str | None:
        try:
            output = subprocess.check_output(
                ["ip", "-4", "-o", "addr", "show", "dev", iface],
                stderr=subprocess.DEVNULL,
                text=True,
            )
        except (FileNotFoundError, subprocess.CalledProcessError, OSError):
            return None

        private_candidates: list[str] = []
        other_candidates: list[str] = []
        for line in output.splitlines():
            m = re.search(r"\binet\s+(\d+\.\d+\.\d+\.\d+)/", line)
            if not m:
                continue
            ip = m.group(1)
            if ip.startswith("127.") or ip == "0.0.0.0":
                continue
            if (
                ip.startswith("10.")
                or ip.startswith("192.168.")
                or (ip.startswith("172.") and 16 <= int(ip.split(".")[1]) <= 31)
            ):
                private_candidates.append(ip)
            else:
                other_candidates.append(ip)
        if private_candidates:
            return private_candidates[0]
        if other_candidates:
            return other_candidates[0]
        return None
