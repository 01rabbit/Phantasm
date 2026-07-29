"""Tests for the TUI layer, services, models, and CLI routing."""

from __future__ import annotations

import inspect
import signal
import sys
import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

# ---------------------------------------------------------------------------
# Banner
# ---------------------------------------------------------------------------


def test_banner_full_on_wide_terminal():
    from phasmid.tui.banner import (
        BANNER_FULL_MIN_WIDTH,
        FULL_BANNER,
        get_banner,
    )

    result = get_banner(BANNER_FULL_MIN_WIDTH)
    assert result == FULL_BANNER


def test_banner_compact_on_narrow_terminal():
    from phasmid.tui.banner import BANNER_FULL_MIN_WIDTH, COMPACT_BANNER, get_banner

    result = get_banner(BANNER_FULL_MIN_WIDTH - 1)
    assert result == COMPACT_BANNER


def test_banner_compact_flag_overrides_width():
    from phasmid.tui.banner import COMPACT_BANNER, get_banner

    result = get_banner(200, compact=True)
    assert result == COMPACT_BANNER


def test_full_banner_contains_phasmid():
    from phasmid.tui.banner import FULL_BANNER

    assert "Janus Eidolon System" in FULL_BANNER
    assert "LOCAL DISCLOSURE CONTROL" in FULL_BANNER


def test_compact_banner_contains_required_text():
    from phasmid.tui.banner import COMPACT_BANNER

    assert "PHASMID" in COMPACT_BANNER
    assert "Janus Eidolon System" in COMPACT_BANNER
    assert "LOCAL DISCLOSURE CONTROL" in COMPACT_BANNER


def test_webui_service_stop_uses_pid_file(tmp_path, monkeypatch):
    from phasmid import config
    from phasmid.services.webui_service import WebUIService

    monkeypatch.setattr(config, "DEFAULT_STATE_DIR", str(tmp_path))
    WebUIService._instance = None
    svc = WebUIService()
    svc.pid_file.parent.mkdir(parents=True, exist_ok=True)
    svc.pid_file.write_text("12345\n", encoding="utf-8")

    killed: list[int] = []
    waits: list[float] = []

    monkeypatch.setattr(svc, "_cancel_timer", lambda: None)
    monkeypatch.setattr(
        svc,
        "_terminate_pid",
        lambda pid, sig=None: killed.append(pid),
    )
    monkeypatch.setattr(
        svc,
        "_wait_for_shutdown",
        lambda pid, timeout=2.0: waits.append(timeout) or True,
    )

    svc.stop()

    assert killed == [12345]
    assert waits
    assert not svc.pid_file.exists()


def test_webui_service_start_fails_if_process_dies_before_port_opens(
    tmp_path, monkeypatch
):
    from phasmid import config
    from phasmid.services.webui_service import WebUIService

    monkeypatch.setattr(config, "DEFAULT_STATE_DIR", str(tmp_path))
    WebUIService._instance = None
    svc = WebUIService()

    class FakeProcess:
        pid = 4242

        def __init__(self):
            self.calls = 0

        def poll(self):
            self.calls += 1
            return 1 if self.calls > 1 else None

    fake_process = FakeProcess()

    monkeypatch.setattr("subprocess.Popen", lambda *args, **kwargs: fake_process)
    monkeypatch.setattr(svc, "_port_is_open", lambda host, port: False)
    monkeypatch.setattr(svc, "_terminate_pid", lambda pid: None)

    assert svc.start() is False
    assert svc._process is None
    assert not svc.pid_file.exists()
    assert svc.startup_failure_reason is not None
    assert "Command:" in svc.startup_failure_reason
    assert "Return code:" in svc.startup_failure_reason
    assert "Port check failed: True" in svc.startup_failure_reason
    assert str(svc.log_file) in svc.startup_failure_reason


def test_webui_service_start_uses_uvicorn_command_and_env(tmp_path, monkeypatch):
    from phasmid import config
    from phasmid.services.webui_service import WebUIService

    monkeypatch.setattr(config, "DEFAULT_STATE_DIR", str(tmp_path))
    monkeypatch.delenv("PHASMID_HOST", raising=False)
    monkeypatch.delenv("PHASMID_PORT", raising=False)
    monkeypatch.delenv("PHASMID_WEBUI_EXPOSE_GADGET", raising=False)
    WebUIService._instance = None
    svc = WebUIService()

    captured: dict[str, object] = {}

    class FakeProcess:
        pid = 5001

        def poll(self):
            return None

    def fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["env"] = kwargs["env"]
        captured["stdout"] = kwargs["stdout"]
        captured["stderr"] = kwargs["stderr"]
        return FakeProcess()

    monkeypatch.setattr("subprocess.Popen", fake_popen)
    monkeypatch.setattr(svc, "_wait_for_startup", lambda timeout=10.0: True)
    monkeypatch.setattr(svc, "reset_timer", lambda: None)

    assert svc.start() is True
    assert captured["cmd"] == [
        sys.executable,
        "-m",
        "uvicorn",
        "phasmid.web_server:app",
        "--host",
        "127.0.0.1",
        "--port",
        "8000",
    ]
    env = captured["env"]
    assert env["PHASMID_HOST"] == "127.0.0.1"
    assert env["PHASMID_PORT"] == "8000"


def test_webui_service_start_failure_cleans_pid_and_preserves_log(
    tmp_path, monkeypatch
):
    from phasmid import config
    from phasmid.services.webui_service import WebUIService

    monkeypatch.setattr(config, "DEFAULT_STATE_DIR", str(tmp_path))
    WebUIService._instance = None
    svc = WebUIService()

    class FakeProcess:
        pid = 6002

        def poll(self):
            return 2

    monkeypatch.setattr("subprocess.Popen", lambda *args, **kwargs: FakeProcess())
    monkeypatch.setattr(svc, "_wait_for_startup", lambda timeout=10.0: False)
    monkeypatch.setattr(svc, "_terminate_pid", lambda pid, sig=None: None)

    assert svc.start() is False
    assert not svc.pid_file.exists()
    assert svc.log_file.exists()


def test_webui_service_stop_escalates_to_sigkill_when_sigterm_times_out(
    tmp_path, monkeypatch
):
    from phasmid import config
    from phasmid.services.webui_service import WebUIService

    monkeypatch.setattr(config, "DEFAULT_STATE_DIR", str(tmp_path))
    WebUIService._instance = None
    svc = WebUIService()
    svc.pid_file.parent.mkdir(parents=True, exist_ok=True)
    svc.pid_file.write_text("45678\n", encoding="utf-8")

    calls: list[tuple[int, int | None]] = []
    waits = {"n": 0}

    monkeypatch.setattr(svc, "_cancel_timer", lambda: None)

    def fake_terminate(pid, sig=None):
        calls.append((pid, sig))

    def fake_wait(pid, timeout=2.0):
        waits["n"] += 1
        return waits["n"] > 1

    monkeypatch.setattr(svc, "_terminate_pid", fake_terminate)
    monkeypatch.setattr(svc, "_wait_for_shutdown", fake_wait)

    svc.stop()

    assert len(calls) == 2
    assert calls[0][0] == 45678
    assert calls[0][1] == signal.SIGTERM
    assert calls[1][0] == 45678
    assert calls[1][1] == signal.SIGKILL
    assert not svc.pid_file.exists()
    assert svc._process is None
    assert svc.uptime_seconds == 0.0


def test_webui_service_stop_is_idempotent(tmp_path, monkeypatch):
    from phasmid import config
    from phasmid.services.webui_service import WebUIService

    monkeypatch.setattr(config, "DEFAULT_STATE_DIR", str(tmp_path))
    WebUIService._instance = None
    svc = WebUIService()
    monkeypatch.setattr(svc, "_cancel_timer", lambda: None)
    monkeypatch.setattr(svc, "_wait_for_shutdown", lambda pid, timeout=2.0: True)
    monkeypatch.setattr(svc, "_terminate_pid", lambda pid, sig=None: None)

    svc.stop()
    svc.stop()

    assert svc._process is None
    assert not svc.pid_file.exists()


def test_webui_service_startup_wait_default_is_hardware_safe():
    from phasmid.services.webui_service import WebUIService

    defaults = WebUIService._wait_for_startup.__defaults__
    assert defaults is not None
    assert defaults[0] >= 10.0


def _bind_host_service(tmp_path, monkeypatch):
    """Build a fresh WebUIService with a clean bind-host environment."""
    from phasmid import config
    from phasmid.services.webui_service import WebUIService

    monkeypatch.setattr(config, "DEFAULT_STATE_DIR", str(tmp_path))
    monkeypatch.delenv("PHASMID_HOST", raising=False)
    monkeypatch.delenv("PHASMID_PORT", raising=False)
    monkeypatch.delenv("PHASMID_WEBUI_EXPOSE_GADGET", raising=False)
    WebUIService._instance = None
    return WebUIService()


def test_webui_service_resolves_loopback_by_default(tmp_path, monkeypatch):
    svc = _bind_host_service(tmp_path, monkeypatch)
    monkeypatch.setattr(svc, "_detect_usb_gadget_ipv4", lambda: "10.55.0.10")

    assert svc.resolve_bind_host() == "127.0.0.1"


def test_webui_service_gadget_opt_in_binds_interface_address_not_all_interfaces(
    tmp_path, monkeypatch
):
    svc = _bind_host_service(tmp_path, monkeypatch)
    monkeypatch.setenv("PHASMID_WEBUI_EXPOSE_GADGET", "1")
    monkeypatch.setattr(svc, "_detect_usb_gadget_ipv4", lambda: "10.55.0.10")

    assert svc.resolve_bind_host() == "10.55.0.10"


def test_webui_service_gadget_opt_in_falls_back_to_loopback_without_gadget(
    tmp_path, monkeypatch
):
    svc = _bind_host_service(tmp_path, monkeypatch)
    monkeypatch.setenv("PHASMID_WEBUI_EXPOSE_GADGET", "1")
    monkeypatch.setattr(svc, "_detect_usb_gadget_ipv4", lambda: None)

    assert svc.resolve_bind_host() == "127.0.0.1"


def test_webui_service_explicit_host_env_wins(tmp_path, monkeypatch):
    svc = _bind_host_service(tmp_path, monkeypatch)
    monkeypatch.setenv("PHASMID_HOST", "10.55.0.1")
    monkeypatch.setenv("PHASMID_WEBUI_EXPOSE_GADGET", "1")
    monkeypatch.setattr(svc, "_detect_usb_gadget_ipv4", lambda: "10.55.0.10")

    assert svc.resolve_bind_host() == "10.55.0.1"


def test_tui_toggle_webui_binds_loopback_not_all_interfaces(tmp_path, monkeypatch):
    """Regression: the `w` key must not expose the WebUI on every interface.

    This drives the real TUI control path (`action_toggle_webui` ->
    `WebUIService.start()` with no arguments) and asserts the host handed to
    uvicorn, because that is the bind address operators actually get.
    """
    from phasmid.tui.app import PhasmidApp

    svc = _bind_host_service(tmp_path, monkeypatch)
    captured: dict[str, object] = {}

    class FakeProcess:
        pid = 7003

        def poll(self):
            return None

    def fake_popen(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["env"] = kwargs["env"]
        return FakeProcess()

    monkeypatch.setattr("subprocess.Popen", fake_popen)
    monkeypatch.setattr(svc, "is_running", lambda: False)
    monkeypatch.setattr(svc, "_wait_for_startup", lambda timeout=10.0: True)
    monkeypatch.setattr(svc, "reset_timer", lambda: None)

    app = PhasmidApp()
    assert app.webui_svc is svc
    notified: list[str] = []
    monkeypatch.setattr(
        app, "notify", lambda message, **kwargs: notified.append(message)
    )
    monkeypatch.setattr(app, "_refresh_webui_status", lambda: None)

    app.action_toggle_webui()

    cmd = captured["cmd"]
    assert cmd[cmd.index("--host") + 1] == "127.0.0.1"
    assert "0.0.0.0" not in cmd
    assert captured["env"]["PHASMID_HOST"] == "127.0.0.1"
    assert notified
    assert "http://127.0.0.1:8000" in notified[0]
    assert "0.0.0.0" not in notified[0]


def test_webui_service_access_url_reports_bound_host(tmp_path, monkeypatch):
    svc = _bind_host_service(tmp_path, monkeypatch)
    monkeypatch.setattr(svc, "_detect_usb_gadget_ipv4", lambda: "10.55.0.10")

    assert svc.access_url() == "http://127.0.0.1:8000"

    svc._host = "10.55.0.10"
    assert svc.access_url() == "http://10.55.0.10:8000"


def test_tui_success_notification_uses_access_url_when_available(monkeypatch):
    from phasmid.tui.app import PhasmidApp

    app = PhasmidApp()
    monkeypatch.setattr(app.webui_svc, "is_running", lambda: False)
    monkeypatch.setattr(app.webui_svc, "start", lambda: True)
    monkeypatch.setattr(app.webui_svc, "access_url", lambda: "http://10.55.0.10:8000")
    notified: list[str] = []
    monkeypatch.setattr(
        app, "notify", lambda message, **kwargs: notified.append(message)
    )
    monkeypatch.setattr(app, "_refresh_webui_status", lambda: None)

    app.action_toggle_webui()

    assert notified
    assert notified[0] == "WebUI active at http://10.55.0.10:8000"


def test_detect_usb_gadget_ipv4_prefers_private_ip(tmp_path, monkeypatch):
    from phasmid import config
    from phasmid.services.webui_service import WebUIService

    monkeypatch.setattr(config, "DEFAULT_STATE_DIR", str(tmp_path))
    WebUIService._instance = None
    svc = WebUIService()

    monkeypatch.setattr(
        "subprocess.check_output",
        lambda cmd, **kwargs: (
            "2: usb0    inet 100.64.1.2/24 brd 100.64.1.255 scope global usb0\n"
            "2: usb0    inet 10.55.0.10/24 brd 10.55.0.255 scope global usb0\n"
        ),
    )

    assert svc._first_preferred_ipv4_on_interface("usb0") == "10.55.0.10"


def test_no_tui_webui_success_string_hardcodes_localhost():
    from phasmid.tui.screens.base import OperatorScreen
    from phasmid.tui.screens.home import HomeScreen

    assert "127.0.0.1:8000" not in OperatorScreen._WEBUI_WARNING_FALLBACK
    source = inspect.getsource(HomeScreen.compose)
    assert "127.0.0.1:8000" not in source


def test_camera_frame_source_prefers_picamera2(monkeypatch):
    from phasmid.camera_frame_source import CameraFrameSource

    source = CameraFrameSource(frame_size=(320, 240))

    def fake_picam():
        source.backend = "picamera2"
        return True

    called = {"opencv": False}

    def fake_cv():
        called["opencv"] = True
        return False

    monkeypatch.setattr(source, "_open_picamera2", fake_picam)
    monkeypatch.setattr(source, "_open_opencv", fake_cv)
    source.open()

    assert source.backend == "picamera2"
    assert called["opencv"] is False


def test_camera_frame_source_falls_back_to_opencv(monkeypatch):
    from phasmid.camera_frame_source import CameraFrameSource

    source = CameraFrameSource(frame_size=(320, 240))

    monkeypatch.setattr(source, "_open_picamera2", lambda: False)

    def fake_cv():
        source.backend = "opencv"
        return True

    monkeypatch.setattr(source, "_open_opencv", fake_cv)
    source.open()

    assert source.backend == "opencv"


def test_prepare_frame_for_jpeg_keeps_rgb888_without_conversion(monkeypatch):
    import numpy as np

    from phasmid.camera_frame_source import CameraFrameSource

    source = CameraFrameSource(frame_size=(320, 240))
    frame = np.zeros((2, 2, 3), dtype=np.uint8)
    calls = {"n": 0}

    def fake_cvt_color(img, code):
        calls["n"] += 1
        return img

    monkeypatch.setattr("cv2.cvtColor", fake_cvt_color)
    out = source._prepare_frame_for_jpeg(frame, source_format="RGB888")

    assert out is frame
    assert calls["n"] == 0
    assert source._last_rgb_to_bgr_applied is False


def test_prepare_frame_for_jpeg_keeps_bgr_without_conversion(monkeypatch):
    import numpy as np

    from phasmid.camera_frame_source import CameraFrameSource

    source = CameraFrameSource(frame_size=(320, 240))
    frame = np.zeros((2, 2, 3), dtype=np.uint8)

    def fail_cvt_color(img, code):
        raise AssertionError("unexpected conversion")

    monkeypatch.setattr("cv2.cvtColor", fail_cvt_color)
    out = source._prepare_frame_for_jpeg(frame, source_format="BGR")

    assert out is frame
    assert source._last_rgb_to_bgr_applied is False


def test_prepare_frame_for_jpeg_supports_rgba_family(monkeypatch):
    import numpy as np

    from phasmid.camera_frame_source import CameraFrameSource

    source = CameraFrameSource(frame_size=(320, 240))
    frame = np.zeros((2, 2, 4), dtype=np.uint8)
    calls = {"n": 0}

    def fake_cvt_color(img, code):
        calls["n"] += 1
        return img[:, :, :3]

    monkeypatch.setattr("cv2.cvtColor", fake_cvt_color)
    out = source._prepare_frame_for_jpeg(frame, source_format="XRGB8888")

    assert out.shape == (2, 2, 3)
    assert calls["n"] == 1
    assert source._last_rgb_to_bgr_applied is True


def test_camera_frame_source_clears_stale_error_after_backend_recovers():
    from phasmid.camera_frame_source import CameraFrameSource

    source = CameraFrameSource(frame_size=(320, 240))
    source.state.last_error = "OpenCV VideoCapture(0) open failed"
    source.state.active_backend = "unavailable"
    source.backend = "unavailable"
    source.state.ready = False

    source.state.active_backend = "picamera2"
    source.state.last_error = None
    source.state.last_frame_at = time.time()
    source.state.ready = True
    status = source.status()

    assert status["ready"] is True
    assert status["backend"] == "picamera2"
    assert status["last_error"] is None


def test_camera_frame_source_mark_frame_yielded_sets_ready():
    from phasmid.camera_frame_source import CameraFrameSource

    source = CameraFrameSource(frame_size=(320, 240))
    source.state.active_backend = "picamera2"
    source.state.ready = False
    source.mark_frame_yielded()
    status = source.status()

    assert status["ready"] is True
    assert status["frames_yielded"] >= 1


def test_camera_frame_source_mark_frame_yielded_sets_stream_backend_if_unknown():
    from phasmid.camera_frame_source import CameraFrameSource

    source = CameraFrameSource(frame_size=(320, 240))
    source.state.active_backend = "none"
    source.backend = "none"
    source.mark_frame_yielded()
    status = source.status()

    assert status["ready"] is True
    assert status["backend"] == "stream"
    assert status["backend"] != "none"


def test_camera_frame_source_status_not_none_when_ready_and_yielded():
    from phasmid.camera_frame_source import CameraFrameSource

    source = CameraFrameSource(frame_size=(320, 240))
    source.state.active_backend = "none"
    source.state.ready = True
    source.state.frames_yielded = 1
    source.state.last_frame_at = time.time()

    status = source.status()
    assert status["backend"] != "none"
    assert status["ready"] is True


def test_camera_frame_source_close_calls_picamera2_stop_close_and_opencv_release():
    from phasmid.camera_frame_source import CameraFrameSource

    class FakePicam:
        def __init__(self):
            self.stopped = 0
            self.closed = 0

        def stop(self):
            self.stopped += 1

        def close(self):
            self.closed += 1

    class FakeCap:
        def __init__(self):
            self.released = 0

        def release(self):
            self.released += 1

    source = CameraFrameSource(frame_size=(320, 240))
    picam = FakePicam()
    cap = FakeCap()
    source.picam2 = picam
    source.cap = cap
    source.backend = "picamera2"
    source.state.active_backend = "picamera2"
    source.state.ready = True

    source.close()

    assert picam.stopped == 1
    assert picam.closed == 1
    assert cap.released == 1
    assert source.backend == "none"
    assert source.state.ready is False


def test_camera_frame_source_close_is_idempotent():
    from phasmid.camera_frame_source import CameraFrameSource

    source = CameraFrameSource(frame_size=(320, 240))
    source.close()
    source.close()
    assert source.backend == "none"
    assert source.state.ready is False


def test_ai_gate_generate_frames_yields_placeholder_when_camera_unavailable(tmp_path):
    from phasmid.ai_gate import AIGate

    gate = AIGate(reference_dir=str(tmp_path))

    def no_frame():
        gate._stop_event.set()
        return False, None

    gate.camera.read = no_frame  # type: ignore[assignment]
    chunk = next(gate.generate_frames())

    assert b"Content-Type: image/jpeg" in chunk
    assert len(chunk) > 64


def test_ai_gate_generate_frames_yields_mjpeg_when_frame_exists(tmp_path):
    import numpy as np

    from phasmid.ai_gate import AIGate

    gate = AIGate(reference_dir=str(tmp_path))
    frame = np.zeros((gate.FRAME_SIZE[1], gate.FRAME_SIZE[0], 3), dtype=np.uint8)
    calls = {"n": 0}

    def one_frame():
        calls["n"] += 1
        if calls["n"] == 1:
            return True, frame
        gate._stop_event.set()
        return False, None

    gate.camera.read = one_frame  # type: ignore[assignment]
    chunk = next(gate.generate_frames())

    assert b"Content-Type: image/jpeg" in chunk
    assert len(chunk) > 64


def test_ai_gate_shared_camera_survives_one_of_two_consumers_closing(tmp_path):
    """The camera is only released once every generate_frames() caller is gone.

    The TUI's background matcher thread and a WebUI /video_feed request both
    call generate_frames() concurrently on the one shared camera. A browser
    tab disconnecting must not tear the camera down from under the matcher
    thread that is still reading it - that used to freeze the matcher's
    match state at whatever it last was, letting Recover keep succeeding (or
    failing) regardless of what was actually in front of the camera.
    """
    import numpy as np

    from phasmid.ai_gate import AIGate

    gate = AIGate(reference_dir=str(tmp_path))
    frame = np.zeros((gate.FRAME_SIZE[1], gate.FRAME_SIZE[0], 3), dtype=np.uint8)
    gate.camera.read = lambda: (True, frame)  # type: ignore[assignment]
    close_calls = {"n": 0}
    gate.camera.close = lambda: close_calls.__setitem__(  # type: ignore[assignment]
        "n", close_calls["n"] + 1
    )

    consumer_a = gate.generate_frames()
    consumer_b = gate.generate_frames()
    next(consumer_a)
    next(consumer_b)
    assert gate._camera_consumers == 2

    consumer_a.close()
    assert gate._camera_consumers == 1
    assert close_calls["n"] == 0

    consumer_b.close()
    assert gate._camera_consumers == 0
    assert close_calls["n"] == 1


def test_ai_gate_stream_frame_is_horizontally_flipped(tmp_path):
    import numpy as np

    from phasmid.ai_gate import AIGate

    gate = AIGate(reference_dir=str(tmp_path))
    frame = np.zeros((3, 4, 3), dtype=np.uint8)
    frame[:, 0, :] = [255, 0, 0]
    flipped = gate._prepare_stream_frame(frame)

    assert (flipped[:, -1, :] == [255, 0, 0]).all()
    assert (flipped[:, 0, :] == [0, 0, 0]).all()


def test_ai_gate_status_includes_camera_backend_fields(tmp_path):
    from phasmid.ai_gate import AIGate

    gate = AIGate(reference_dir=str(tmp_path))
    gate.camera.backend = "picamera2"
    gate.camera.last_error = "none"
    status = gate.get_status()

    assert "camera_backend" in status
    assert "last_camera_error" in status
    assert "stream_resolution" in status
    assert "fps_target" in status
    assert "camera_ready" in status


def test_frontend_clears_unavailable_on_camera_feed_load():
    template_path = Path("src/phasmid/templates/base.html")
    source = template_path.read_text(encoding="utf-8")
    assert "cameraFeed.addEventListener('load'" in source
    assert "Active (stream)" in source


# ---------------------------------------------------------------------------
# Profile service
# ---------------------------------------------------------------------------


def test_profile_config_path_uses_platformdirs():
    from phasmid.services.profile_service import config_dir

    p = config_dir()
    assert isinstance(p, Path)
    assert "phasmid" in str(p).lower()


def test_profile_save_and_load(tmp_path, monkeypatch):
    from phasmid.services import profile_service

    monkeypatch.setattr(profile_service, "config_dir", lambda: tmp_path)

    from phasmid.models.profile import Profile
    from phasmid.services.profile_service import load_profile, save_profile

    p = Profile(name="test", container_size="256M", default_vessel_dir="/tmp/vessels")
    save_profile(p)

    loaded = load_profile("test")
    assert loaded.name == "test"
    assert loaded.container_size == "256M"
    assert loaded.default_vessel_dir == "/tmp/vessels"


def test_profile_does_not_store_secrets():
    from phasmid.models.profile import Profile

    p = Profile()
    assert not p.has_secrets()
    d = p.to_dict()
    for forbidden in Profile.FORBIDDEN_KEYS:
        assert forbidden not in d


def test_profile_load_returns_default_if_missing(tmp_path, monkeypatch):
    from phasmid.services import profile_service

    monkeypatch.setattr(profile_service, "config_dir", lambda: tmp_path)

    from phasmid.services.profile_service import load_profile

    p = load_profile("nonexistent")
    assert p.name == "nonexistent"


def test_profile_list(tmp_path, monkeypatch):
    from phasmid.services import profile_service

    monkeypatch.setattr(profile_service, "config_dir", lambda: tmp_path)

    from phasmid.models.profile import Profile
    from phasmid.services.profile_service import list_profiles, save_profile

    save_profile(Profile(name="alpha"))
    save_profile(Profile(name="beta"))
    names = list_profiles()
    assert "alpha" in names
    assert "beta" in names


# ---------------------------------------------------------------------------
# Vessel service
# ---------------------------------------------------------------------------


def test_vessel_register_and_list(tmp_path, monkeypatch):
    from phasmid.services import profile_service
    from phasmid.services import vessel_service as vs_mod

    monkeypatch.setattr(profile_service, "config_dir", lambda: tmp_path)
    monkeypatch.setattr(vs_mod, "config_dir", lambda: tmp_path)

    from phasmid.services.vessel_service import list_vessels, register_vessel

    vessel_file = tmp_path / "test.vessel"
    vessel_file.write_bytes(b"\x00" * 1024)

    register_vessel(vessel_file)
    vessels = list_vessels()
    names = [v.name for v in vessels]
    assert "test.vessel" in names


def test_vessel_filename_warning_detecting_revealing_terms():
    from phasmid.services.vessel_service import check_filename_warnings

    warnings = check_filename_warnings("secret_data.vessel")
    assert any("secret" in w.lower() for w in warnings)


def test_vessel_filename_no_warning_for_neutral_name():
    from phasmid.services.vessel_service import check_filename_warnings

    warnings = check_filename_warnings("travel.vessel")
    assert not warnings


def test_vessel_redact_path():
    from phasmid.services.vessel_service import redact_path

    home = Path.home()
    long_path = home / "a" / "b" / "c" / "test.vessel"
    result = redact_path(long_path)
    assert "test.vessel" in result
    assert str(home) not in result or "~" in result


# ---------------------------------------------------------------------------
# Inspection service
# ---------------------------------------------------------------------------


def test_inspection_service_returns_structured_result(tmp_path):
    import secrets

    from phasmid.services.inspection_service import InspectionService

    vessel = tmp_path / "test.vessel"
    vessel.write_bytes(secrets.token_bytes(65536))

    svc = InspectionService()
    result = svc.inspect(vessel)

    assert result.ok
    assert result.fields
    labels = [f.label for f in result.fields]
    assert "File" in labels
    assert "Size" in labels
    assert "Header" in labels
    assert "Entropy" in labels


def test_inspection_service_on_missing_file(tmp_path):
    from phasmid.services.inspection_service import InspectionService

    svc = InspectionService()
    result = svc.inspect(tmp_path / "does_not_exist.vessel")
    assert not result.ok
    assert result.error


def test_inspection_no_recognized_header_for_random_data(tmp_path):
    import secrets

    from phasmid.services.inspection_service import InspectionService

    vessel = tmp_path / "rand.vessel"
    vessel.write_bytes(secrets.token_bytes(65536))
    svc = InspectionService()
    result = svc.inspect(vessel)
    header_field = next((f for f in result.fields if f.label == "Header"), None)
    assert header_field is not None
    assert "no recognized header" in header_field.value.lower()


class VesselSummaryPanelEntropyCacheTests(unittest.TestCase):
    def test_entropy_is_cached_until_vessel_stat_changes(self):
        from src.phasmid.models.vessel import VesselMeta
        from src.phasmid.tui.widgets.status_panel import VesselSummaryPanel

        def inspection_result(value: str):
            return SimpleNamespace(
                ok=True,
                fields=[
                    SimpleNamespace(
                        label="Entropy",
                        value=value,
                        note="7.99 bits/byte",
                    )
                ],
            )

        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "sample.vessel"
            path.write_bytes(b"a" * 128)
            vessel = VesselMeta(path=path)
            panel = VesselSummaryPanel(vessel)

            with mock.patch(
                "src.phasmid.tui.widgets.status_panel.InspectionService"
            ) as service_cls:
                service_cls.return_value.inspect.side_effect = [
                    inspection_result("high / random-like"),
                    inspection_result("moderate"),
                ]

                first = panel._get_entropy(vessel)
                second = panel._get_entropy(vessel)
                path.write_bytes(b"b" * 256)
                third = panel._get_entropy(vessel)

        self.assertEqual(first, "high / random-like  [dim](7.99 bits/byte)[/dim]")
        self.assertEqual(second, first)
        self.assertEqual(third, "moderate  [dim](7.99 bits/byte)[/dim]")
        self.assertEqual(service_cls.return_value.inspect.call_count, 2)


# ---------------------------------------------------------------------------
# Doctor service
# ---------------------------------------------------------------------------


def test_doctor_returns_structured_result():
    from phasmid.models.doctor import DoctorLevel
    from phasmid.services.doctor_service import DoctorService

    svc = DoctorService()
    result = svc.run()
    assert result.checks
    assert result.disclaimer
    for check in result.checks:
        assert isinstance(check.level, DoctorLevel)
        assert check.name
        assert check.message


def test_doctor_result_overall_level():
    from phasmid.models.doctor import DoctorCheck, DoctorLevel, DoctorResult

    r = DoctorResult(
        checks=[
            DoctorCheck("a", DoctorLevel.OK, "ok"),
            DoctorCheck("b", DoctorLevel.WARN, "warn"),
        ]
    )
    assert r.overall_level == DoctorLevel.WARN

    r2 = DoctorResult(
        checks=[
            DoctorCheck("a", DoctorLevel.OK, "ok"),
            DoctorCheck("b", DoctorLevel.FAIL, "fail"),
        ]
    )
    assert r2.overall_level == DoctorLevel.FAIL

    r3 = DoctorResult(
        checks=[
            DoctorCheck("a", DoctorLevel.OK, "ok"),
        ]
    )
    assert r3.overall_level == DoctorLevel.OK


# ---------------------------------------------------------------------------
# Audit service
# ---------------------------------------------------------------------------


def test_audit_report_has_required_sections():
    from phasmid.services.audit_service import AuditService

    svc = AuditService()
    report = svc.get_report()
    titles = [s.title for s in report.sections]
    assert "System Position" in titles
    assert "Cryptographic Controls" in titles
    assert "Operational Controls" in titles
    assert "Known Limitations" in titles
    assert "Non-Claims" in titles


def test_audit_system_position_content():
    from phasmid.services.audit_service import AuditService

    svc = AuditService()
    report = svc.get_report()
    pos = next(s for s in report.sections if s.title == "System Position")
    keys = [e.key for e in pos.entries]
    assert "Status" in keys
    status_entry = next(e for e in pos.entries if e.key == "Status")
    assert "research-grade prototype" in status_entry.value


# ---------------------------------------------------------------------------
# Guided service
# ---------------------------------------------------------------------------


def test_guided_service_returns_all_workflows():
    from phasmid.services.guided_service import GuidedService

    svc = GuidedService()
    workflows = svc.get_workflows()
    ids = [wf.id for wf in workflows]
    assert "coerced_disclosure" in ids
    assert "headerless_inspection" in ids
    assert "multiple_faces" in ids
    assert "safety_checklist" in ids


def test_guided_workflows_no_forbidden_terms():
    from phasmid.services.guided_service import GuidedService

    svc = GuidedService()
    forbidden = {
        "real secret",
        "fake secret",
        "decoy",
        "hidden truth",
        "production-grade",
        "military-grade",
        "forensic-proof",
        "coercion-proof",
        "undetectable",
        "unbreakable",
        "guaranteed safe",
        "impossible to discover",
    }
    for wf in svc.get_workflows():
        text = (
            wf.title
            + " "
            + wf.description
            + " "
            + " ".join(s.text + " " + s.detail for s in wf.steps)
        ).lower()
        for term in forbidden:
            assert (
                term not in text
            ), f"Forbidden term '{term}' found in workflow '{wf.id}'"


# ---------------------------------------------------------------------------
# TUI import smoke test
# ---------------------------------------------------------------------------


def test_tui_app_imports_successfully():
    from phasmid.tui.app import PhasmidApp

    assert PhasmidApp is not None


def test_all_screens_importable():
    from phasmid.tui.screens import (
        AboutScreen,
        AuditScreen,
        CreateVesselScreen,
        DoctorScreen,
        FaceManagerScreen,
        GuidedScreen,
        HomeScreen,
        InspectVesselScreen,
        OpenVesselScreen,
        SettingsScreen,
    )

    for cls in [
        HomeScreen,
        AboutScreen,
        AuditScreen,
        DoctorScreen,
        GuidedScreen,
        InspectVesselScreen,
        CreateVesselScreen,
        OpenVesselScreen,
        FaceManagerScreen,
        SettingsScreen,
    ]:
        assert cls is not None


def test_all_widgets_importable():
    from phasmid.tui.widgets import (
        EventLog,
        VesselSummaryPanel,
        VesselTable,
        WarningBox,
    )

    for cls in [VesselSummaryPanel, VesselTable, EventLog, WarningBox]:
        assert cls is not None


# ---------------------------------------------------------------------------
# CLI routing
# ---------------------------------------------------------------------------


def test_cli_entry_point_is_main():
    """Verify pyproject.toml wires phasmid = phasmid.cli:main."""
    import importlib

    mod = importlib.import_module("phasmid.cli")
    assert callable(getattr(mod, "main", None))


def test_cli_parser_no_args_routes_to_tui(monkeypatch):
    """phasmid with no subcommand should trigger TUI."""
    from phasmid.cli import _build_tui_parser

    parser = _build_tui_parser()
    args = parser.parse_args([])
    assert args.command is None


def test_cli_parser_guided_subcommand(monkeypatch):
    from phasmid.cli import _build_tui_parser

    parser = _build_tui_parser()
    args = parser.parse_args(["guided"])
    assert args.command == "guided"


def test_cli_parser_audit_subcommand():
    from phasmid.cli import _build_tui_parser

    parser = _build_tui_parser()
    args = parser.parse_args(["audit"])
    assert args.command == "audit"


def test_cli_parser_doctor_subcommand():
    from phasmid.cli import _build_tui_parser

    parser = _build_tui_parser()
    args = parser.parse_args(["doctor"])
    assert args.command == "doctor"


def test_cli_parser_doctor_no_tui_flag():
    from phasmid.cli import _build_tui_parser

    parser = _build_tui_parser()
    args = parser.parse_args(["doctor", "--no-tui"])
    assert args.command == "doctor"
    assert args.no_tui is True


def test_cli_parser_open_with_vessel():
    from phasmid.cli import _build_tui_parser

    parser = _build_tui_parser()
    args = parser.parse_args(["open", "travel.vessel"])
    assert args.command == "open"
    assert args.vessel == "travel.vessel"


def test_cli_parser_open_no_tui():
    from phasmid.cli import _build_tui_parser

    parser = _build_tui_parser()
    args = parser.parse_args(["open", "travel.vessel", "--no-tui", "--face", "face_b"])
    assert args.command == "open"
    assert args.no_tui is True
    assert args.face == "face_b"


def test_cli_parser_create_with_vessel():
    from phasmid.cli import _build_tui_parser

    parser = _build_tui_parser()
    args = parser.parse_args(["create", "new.vessel"])
    assert args.command == "create"
    assert args.vessel == "new.vessel"


def test_cli_parser_create_non_interactive_flags():
    from phasmid.cli import _build_tui_parser

    parser = _build_tui_parser()
    args = parser.parse_args(["create", "new.vessel", "--no-tui", "--size", "1G"])
    assert args.command == "create"
    assert args.no_tui is True
    assert args.size == "1G"


def test_cli_parser_store_with_vessel():
    from phasmid.cli import _build_tui_parser

    parser = _build_tui_parser()
    args = parser.parse_args(["store", "travel.vessel", "--input", "note.txt"])
    assert args.command == "store"
    assert args.vessel == "travel.vessel"
    assert args.file == "note.txt"


def test_create_vessel_screen_uses_shared_workflow(monkeypatch):
    from types import SimpleNamespace

    from phasmid.tui.screens.create_vessel import CreateVesselScreen

    screen = CreateVesselScreen(initial_path="travel.vessel")
    notifications = []
    fake_warning = SimpleNamespace(update=lambda _value: None)

    created = {}

    class FakeWorkflow:
        def create_vessel(self, path, size, label=""):
            created["path"] = path
            created["size"] = size
            created["label"] = label
            return SimpleNamespace(vessel_path=Path("/tmp/travel.vessel"), size_bytes=8)

    class FakeVesselService:
        def register(self, path):
            created["registered"] = path

    monkeypatch.setattr(screen, "_workflow", FakeWorkflow())
    monkeypatch.setattr(screen, "_svc", FakeVesselService())
    monkeypatch.setattr(
        CreateVesselScreen,
        "app",
        property(
            lambda self: SimpleNamespace(
                notify=lambda *args, **kwargs: notifications.append((args, kwargs))
            )
        ),
    )
    monkeypatch.setattr(
        screen, "dismiss", lambda: created.setdefault("dismissed", True)
    )
    monkeypatch.setattr(
        screen,
        "query_one",
        lambda selector, _type=None: {
            "#vessel-path": SimpleNamespace(value="~/travel.vessel"),
            "#vessel-size": SimpleNamespace(value="512M"),
            "#vessel-label": SimpleNamespace(value="travel"),
            "#warning-area": fake_warning,
        }[selector],
    )

    screen._attempt_create()

    assert created["path"] == str(Path("~/travel.vessel").expanduser())
    assert created["size"] == "512M"
    assert created["label"] == "travel"
    assert created["registered"] == Path("/tmp/travel.vessel")
    assert created["dismissed"] is True
    assert notifications


def test_open_vessel_screen_recover_does_not_select_a_face(monkeypatch):
    """Recover File must resolve the face from the passphrase, not a menu.

    An operator asked to unlock the vessel under duress should not have to
    name which face out loud, or pick one from a screen, before anything is
    checked - either already tells an onlooker that more than one face
    exists. Recover File hides the face selector (see
    _sync_field_visibility) and passes selector=None so the passphrase (and
    object cue) decide which face answers; bookkeeping for "which face was
    reached" only happens afterward, from the result.
    """
    from phasmid.tui.screens.open_vessel import OpenVesselScreen

    screen = OpenVesselScreen(vessel_path="travel.vessel")
    events = []

    class FakeWorkflow:
        def open_vessel(self, path, face_id="face_a"):
            events.append(("open", path, face_id))

        def resolve_face_id(self, selector):
            return {"dummy": "face_a", "secret": "face_b"}[selector]

        def retrieve_file(
            self,
            path,
            passphrase,
            output_path=None,
            selector=None,
            use_attempt_limiter=False,
        ):
            events.append(("retrieve", path, passphrase, output_path, selector))
            return SimpleNamespace(
                bytes_retrieved=4, output_path=Path("/tmp/out.bin"), mode="secret"
            )

    monkeypatch.setattr(screen, "_workflow", FakeWorkflow())
    monkeypatch.setattr(
        "phasmid.tui.screens.open_vessel.access_cue_service.start", lambda: None
    )
    monkeypatch.setattr(
        "phasmid.tui.screens.open_vessel.access_cue_service.close", lambda: None
    )
    monkeypatch.setattr(
        OpenVesselScreen,
        "app",
        property(
            lambda self: SimpleNamespace(
                notify=lambda *args, **kwargs: events.append(("notify", args, kwargs))
            )
        ),
    )
    monkeypatch.setattr(screen, "dismiss", lambda: events.append(("dismiss",)))
    monkeypatch.setattr(
        screen,
        "query_one",
        lambda selector, _type=None: {
            "#vessel-path": SimpleNamespace(value="travel.vessel"),
            "#face-select": SimpleNamespace(value="face_a"),
            "#operation-select": SimpleNamespace(value="retrieve"),
            "#input-file": SimpleNamespace(value=""),
            "#output-file": SimpleNamespace(value="/tmp/out.bin"),
            "#passphrase": SimpleNamespace(value="passphrase"),
            "#restricted-passphrase": SimpleNamespace(value=""),
        }[selector],
    )

    screen._attempt_open()

    # No pre-emptive open_vessel with a face the operator never chose - only
    # the post-hoc bookkeeping call, using the face the passphrase actually
    # resolved to (mode "secret" -> "face_b"), not the face-select widget's
    # untouched default ("face_a").
    assert events.count(("open", "travel.vessel", "face_b")) == 1
    assert ("open", "travel.vessel", "face_a") not in events
    assert ("retrieve", "travel.vessel", "passphrase", "/tmp/out.bin", None) in events
    assert ("dismiss",) in events


def test_open_vessel_screen_sync_field_visibility_hides_face_for_recover_and_list(
    monkeypatch,
):
    """Add/Remove show the face selector and restricted passphrase; List/Recover don't."""
    from phasmid.tui.screens.open_vessel import OpenVesselScreen

    screen = OpenVesselScreen(vessel_path="travel.vessel")

    class FakeWidget:
        def __init__(self, value=None):
            self.value = value
            self.display = True

    widgets = {
        "#operation-select": FakeWidget(value="retrieve"),
        "#face-select-label": FakeWidget(),
        "#face-select": FakeWidget(),
        "#input-file-label": FakeWidget(),
        "#input-file": FakeWidget(),
        "#output-file-label": FakeWidget(),
        "#output-file": FakeWidget(),
        "#restricted-passphrase-label": FakeWidget(),
        "#restricted-passphrase": FakeWidget(),
    }
    monkeypatch.setattr(
        screen, "query_one", lambda selector, _type=None: widgets[selector]
    )

    for operation, face_expected, output_expected in (
        ("retrieve", False, True),
        ("list", False, False),
        ("add", True, False),
        ("remove", True, False),
    ):
        widgets["#operation-select"].value = operation
        screen._sync_field_visibility()
        assert widgets["#face-select-label"].display is face_expected
        assert widgets["#face-select"].display is face_expected
        assert widgets["#input-file-label"].display is face_expected
        assert widgets["#input-file"].display is face_expected
        assert widgets["#restricted-passphrase-label"].display is face_expected
        assert widgets["#restricted-passphrase"].display is face_expected
        assert widgets["#output-file-label"].display is output_expected
        assert widgets["#output-file"].display is output_expected


def test_face_manager_screen_uses_shared_workflow(monkeypatch):
    from textual.widgets import DataTable

    from phasmid.tui.screens.face_manager import FaceManagerScreen

    vessel = SimpleNamespace(
        path=Path("/tmp/travel.vessel"), name="travel.vessel", faces=[]
    )
    screen = FaceManagerScreen(vessel=vessel)
    events = []

    class FakeWorkflow:
        def create_face(self, path, face_id, label=""):
            events.append(("create_face", path, face_id, label))
            return SimpleNamespace(
                vessel=SimpleNamespace(
                    path=Path("/tmp/travel.vessel"),
                    name="travel.vessel",
                    faces=[
                        SimpleNamespace(
                            face_id=face_id,
                            label=label or "Disclosure Face 2",
                            status="available",
                            file_count=0,
                            occupancy=0,
                            last_accessed="",
                            dummy_profile=SimpleNamespace(
                                plausibility_level="LOW",
                                plausibility_score=0,
                                dummy_file_count=0,
                                occupancy_ratio=0.0,
                                dummy_total_size=0,
                                file_type_distribution={},
                            ),
                        )
                    ],
                ),
                face=SimpleNamespace(face_id=face_id),
            )

        def inspect_dummy_profile(self, path, face_id="face_a"):
            events.append(("inspect_plausibility", path, face_id))
            return SimpleNamespace(
                vessel=vessel,
                face=SimpleNamespace(face_id=face_id),
                profile=SimpleNamespace(
                    plausibility_level="LOW",
                    plausibility_score=12,
                    dummy_file_count=0,
                    occupancy_ratio=0.0,
                    dummy_total_size=0,
                    file_type_distribution={},
                ),
                recommended_action="Generate a broader local baseline before field use.",
            )

    monkeypatch.setattr(screen, "_workflow", FakeWorkflow())
    monkeypatch.setattr(
        FaceManagerScreen,
        "app",
        property(
            lambda self: SimpleNamespace(
                notify=lambda *args, **kwargs: events.append(("notify", args, kwargs))
            )
        ),
    )

    table = SimpleNamespace(
        clear=lambda: events.append(("clear",)),
        add_row=lambda *args: events.append(("row", args)),
    )
    monkeypatch.setattr(
        screen,
        "query_one",
        lambda selector, _type=None: {
            "#face-id": SimpleNamespace(value="face_b"),
            "#new-label": SimpleNamespace(value="travel"),
            "#plausibility-summary": SimpleNamespace(
                update=lambda value: events.append(("summary", value))
            ),
            DataTable: table,
        }[selector],
    )

    screen.on_button_pressed(
        SimpleNamespace(button=SimpleNamespace(id="add-label-btn"))
    )
    screen.on_button_pressed(
        SimpleNamespace(button=SimpleNamespace(id="inspect-plausibility-btn"))
    )

    assert ("create_face", Path("/tmp/travel.vessel"), "face_b", "travel") in events
    assert ("inspect_plausibility", Path("/tmp/travel.vessel"), "face_b") in events


def test_cli_parser_inspect_with_vessel():
    from phasmid.cli import _build_tui_parser

    parser = _build_tui_parser()
    args = parser.parse_args(["inspect", "travel.vessel"])
    assert args.command == "inspect"
    assert args.vessel == "travel.vessel"


def test_cli_parser_close_with_vessel():
    from phasmid.cli import _build_tui_parser

    parser = _build_tui_parser()
    args = parser.parse_args(["close", "travel.vessel"])
    assert args.command == "close"
    assert args.vessel == "travel.vessel"


def test_cli_parser_face_create():
    from phasmid.cli import _build_tui_parser

    parser = _build_tui_parser()
    args = parser.parse_args(
        ["face", "create", "travel.vessel", "--face", "face_b", "--label", "travel"]
    )
    assert args.command == "face"
    assert args.face_command == "create"
    assert args.vessel == "travel.vessel"
    assert args.face == "face_b"
    assert args.label == "travel"


def test_cli_parser_file_add():
    from phasmid.cli import _build_tui_parser

    parser = _build_tui_parser()
    args = parser.parse_args(
        ["file", "add", "travel.vessel", "--face", "face_b", "--input", "note.txt"]
    )
    assert args.command == "file"
    assert args.file_command == "add"
    assert args.vessel == "travel.vessel"
    assert args.face == "face_b"
    assert args.file == "note.txt"


def test_cli_parser_file_retrieve_with_object_image():
    from phasmid.cli import _build_tui_parser

    parser = _build_tui_parser()
    args = parser.parse_args(
        [
            "file",
            "retrieve",
            "travel.vessel",
            "--face",
            "face_b",
            "--output",
            "/tmp/out.bin",
            "--object-image",
            "object.png",
        ]
    )
    assert args.command == "file"
    assert args.file_command == "retrieve"
    assert args.output == "/tmp/out.bin"
    assert args.object_image == "object.png"


def test_cli_parser_dummy_generate():
    from phasmid.cli import _build_tui_parser

    parser = _build_tui_parser()
    args = parser.parse_args(
        [
            "dum" + "my",
            "generate",
            "travel.vessel",
            "--face",
            "face_b",
            "--target-occupancy",
            "20%",
        ]
    )
    assert args.command == "dummy"
    assert args.plausibility_command == "generate"
    assert args.vessel == "travel.vessel"
    assert args.face == "face_b"
    assert args.target_occupancy == "20%"


def test_cli_parser_emergency_destroy_face():
    from phasmid.cli import _build_tui_parser

    parser = _build_tui_parser()
    args = parser.parse_args(
        [
            "emergency",
            "destroy-face",
            "travel.vessel",
            "--face",
            "face_b",
            "--object-image",
            "object.png",
            "--confirm",
            "DESTROY FACE",
        ]
    )
    assert args.command == "emergency"
    assert args.emergency_command == "destroy-face"
    assert args.face == "face_b"
    assert args.object_image == "object.png"
    assert args.confirm == "DESTROY FACE"


# ---------------------------------------------------------------------------
# Vessel model
# ---------------------------------------------------------------------------


def test_vessel_size_human():
    from pathlib import Path

    from phasmid.models.vessel import VesselMeta

    v = VesselMeta(path=Path("/tmp/t.vessel"), size_bytes=512 * 1024 * 1024)
    assert "512" in v.size_human
    assert "MiB" in v.size_human


def test_vessel_meta_defaults_name_from_path():
    from phasmid.models.vessel import VesselMeta

    v = VesselMeta(path=Path("/tmp/travel.vessel"))
    assert v.name == "travel.vessel"


# ---------------------------------------------------------------------------
# Simple Operator <-> Expert navigation
# ---------------------------------------------------------------------------


def test_expert_controls_have_back_binding():
    """Expert controls must offer a way back, not only Quit.

    Every other pushed screen binds `escape` to `dismiss`; the Expert console
    was the one exception, which made entering it one-way for the session.
    """
    from phasmid.tui.screens.home import HomeScreen

    bindings = {(b.key, b.action) for b in HomeScreen.BINDINGS}
    assert ("escape", "dismiss") in bindings
    # `q` still quits, matching the rest of the TUI.
    assert ("q", "quit") in bindings


def test_expert_entry_refreshes_simple_home_on_return(monkeypatch):
    """Returning from Expert controls refreshes the protected storage list."""
    from phasmid.tui.screens.home import HomeScreen
    from phasmid.tui.screens.simple_home import SimpleHomeScreen

    screen = SimpleHomeScreen.__new__(SimpleHomeScreen)
    refreshed: list[bool] = []
    monkeypatch.setattr(SimpleHomeScreen, "_selected_path", lambda self: "")
    monkeypatch.setattr(
        SimpleHomeScreen, "_refresh_table", lambda self: refreshed.append(True)
    )

    pushed: dict = {}

    class FakeApp:
        def push_screen(self, screen_obj, callback=None):
            pushed["screen"] = screen_obj
            pushed["callback"] = callback

    monkeypatch.setattr(SimpleHomeScreen, "app", property(lambda self: FakeApp()))

    screen.action_expert()

    assert isinstance(pushed["screen"], HomeScreen)
    assert pushed["callback"] is not None, "no return callback: list would go stale"
    pushed["callback"](None)
    assert refreshed == [True]


def test_key_name_brackets_survive_rich_markup_parsing():
    """`[x]` in a user-facing string is Rich markup, not a literal key name.

    Unescaped, Rich strips the bracketed key name entirely instead of
    rendering it, so operators never see which key to press. Every string
    that names a key in brackets must escape it (`\\[x]`) so the plain
    rendered text still contains the key name.
    """
    from rich.text import Text

    from phasmid.tui.screens.base import OperatorScreen

    samples = [
        (OperatorScreen._WEBUI_WARNING_FALLBACK, "[w]"),
        (
            "Normal controls are ready. Press \\[e] Expert for diagnostics "
            "and technical detail.",
            "[e]",
        ),
        (
            "[bold]Choose an action:[/bold]  \\[o] Open selected   "
            "\\[n] New protected storage   \\[g] Guided help\n"
            "[dim]Advanced diagnostics and forensic detail are available "
            "under \\[e] Expert.[/dim]",
            "[o]",
        ),
        (
            "[bold]No protected storage found.[/bold]\n"
            "Press \\[n] to create one, or \\[g] for guided help.",
            "[n]",
        ),
        (
            "[yellow]! SYSTEM: 7 WARN — press \\[d] to review[/yellow]",
            "[d]",
        ),
    ]
    for markup, key in samples:
        plain = Text.from_markup(markup).plain
        assert key in plain, f"key name {key!r} stripped from: {plain!r}"


def test_all_tui_screens_mount_and_keep_key_names(tmp_path, monkeypatch):
    """Push every screen through the real app and inspect what it renders.

    Reading source strings misses two classes of regression that only show
    up once Textual actually renders a screen: CSS that fails to parse (a
    `border:` referencing an auto-contrast variable like `$text-muted` is
    invalid, even though the identical variable is fine for `color:`, so
    the screen raises `StylesheetParseError` and never mounts at all), and
    a "Press [x]" instruction whose bracketed key name Rich silently
    stripped. Both classes previously escaped review because the affected
    screens (Silent Standby, the context-profile selector) were never
    actually pushed.
    """
    import asyncio
    import re

    from textual.widgets import Label, Static

    from phasmid import config

    monkeypatch.setattr(config, "DEFAULT_STATE_DIR", str(tmp_path))

    from phasmid.tui.app import PhasmidApp
    from phasmid.tui.screens.about import AboutScreen
    from phasmid.tui.screens.audit import AuditScreen
    from phasmid.tui.screens.context_profile_selector import (
        ContextProfileSelectorScreen,
    )
    from phasmid.tui.screens.create_vessel import CreateVesselScreen
    from phasmid.tui.screens.doctor import DoctorScreen
    from phasmid.tui.screens.face_manager import FaceManagerScreen
    from phasmid.tui.screens.guided import GuidedScreen
    from phasmid.tui.screens.home import HomeScreen
    from phasmid.tui.screens.inspect_vessel import InspectVesselScreen
    from phasmid.tui.screens.luks_screen import LuksScreen
    from phasmid.tui.screens.open_vessel import OpenVesselScreen
    from phasmid.tui.screens.settings import SettingsScreen
    from phasmid.tui.screens.simple_home import SimpleHomeScreen
    from phasmid.tui.screens.standby import StandbyScreen

    screens = [
        ("SimpleHome", SimpleHomeScreen),
        ("Home", HomeScreen),
        ("Create", CreateVesselScreen),
        ("Faces", FaceManagerScreen),
        ("Audit", AuditScreen),
        ("Doctor", DoctorScreen),
        ("Settings", SettingsScreen),
        ("Inspect", InspectVesselScreen),
        ("Open", OpenVesselScreen),
        ("Luks", LuksScreen),
        ("Guided", GuidedScreen),
        ("About", AboutScreen),
        ("Standby", StandbyScreen),
        ("ContextProfile", ContextProfileSelectorScreen),
    ]
    stripped_key_fingerprint = re.compile(r"[Pp]ress\s{2,}|PRESS\s{2,}")

    async def scan() -> list[str]:
        failures: list[str] = []
        app = PhasmidApp(initial_screen="home")
        async with app.run_test(size=(140, 60)) as pilot:
            await pilot.pause()
            for name, screen_cls in screens:
                try:
                    await app.push_screen(screen_cls())
                except Exception as exc:  # noqa: BLE001 - want every screen's failure
                    failures.append(f"{name} failed to mount: {exc!r}")
                    continue
                await pilot.pause()
                widgets = list(app.screen.query(Static)) + list(app.screen.query(Label))
                for widget in widgets:
                    try:
                        text = widget.visual.plain
                    except Exception:  # noqa: BLE001 - not every widget renders text
                        continue
                    for line in text.splitlines():
                        if stripped_key_fingerprint.search(line):
                            failures.append(
                                f"{name} {widget.id!r}: stripped key name in {line!r}"
                            )
                await app.pop_screen()
                await pilot.pause()
        return failures

    failures = asyncio.run(scan())
    assert not failures, "\n".join(failures)


def test_simple_home_clears_empty_state_once_a_vessel_exists(monkeypatch):
    """The empty-state text must be replaced, not just set.

    `_refresh_table` only ever assigned the "No protected storage found"
    copy, and never restored the default. After the first Vessel was created
    the panel kept telling the operator there was no storage while the table
    directly above it listed one - the two contradicted each other on screen,
    on the screen shown immediately after the demo's create step.
    """
    from phasmid.tui.screens.simple_home import SimpleHomeScreen

    screen = SimpleHomeScreen.__new__(SimpleHomeScreen)
    screen._profile = SimpleNamespace(default_vessel_dir=None)
    screen._initial_vessel_path = None

    updates: list[str] = []
    table = SimpleNamespace(
        clear=lambda: None,
        add_row=lambda *args, **kwargs: None,
        move_cursor=lambda **kwargs: None,
    )
    panel = SimpleNamespace(update=updates.append)

    def fake_query_one(self, selector, _type=None):
        return table if selector == "#storage-table" else panel

    monkeypatch.setattr(SimpleHomeScreen, "query_one", fake_query_one)

    vessel = SimpleNamespace(
        name="travel.vessel",
        is_open=False,
        size_human="64.0 MiB",
        faces=[],
        path="/home/demo/Documents/travel.vessel",
    )

    screen._svc = SimpleNamespace(list_all=lambda _dir: [])
    screen._refresh_table()
    assert "No protected storage found" in updates[-1]

    screen._svc = SimpleNamespace(list_all=lambda _dir: [vessel])
    screen._refresh_table()
    assert "No protected storage found" not in updates[-1]
    assert "Choose an action" in updates[-1]


def test_plausibility_generation_runs_off_the_event_loop():
    """Generation must not be called inline from the button handler.

    Measured at roughly four minutes for a 64 MiB Vessel at 15% occupancy on
    a Pi Zero 2 W. Inline, that froze the entire console for the duration
    with no progress shown, which reads as a crash.
    """
    from phasmid.tui.screens.face_manager import FaceManagerScreen

    handler = inspect.getsource(FaceManagerScreen.on_button_pressed)
    assert "generate_dummy_profile" not in handler, (
        "generate_dummy_profile is called inline from on_button_pressed; "
        "it must be dispatched to a worker"
    )

    worker_source = inspect.getsource(FaceManagerScreen._run_generation)
    assert "generate_dummy_profile" in worker_source
    assert "thread=True" in inspect.getsource(FaceManagerScreen)


def test_standby_retracts_the_webui(monkeypatch):
    """Silent Standby must take the WebUI down with the local screen.

    Concealing the console while the WebUI keeps serving leaves the whole
    operator surface reachable from a tethered machine over the USB gadget,
    so the sealed state would be sealed on the device only.
    """
    from phasmid.tui.app import PhasmidApp

    app = PhasmidApp.__new__(PhasmidApp)
    stopped: list[bool] = []

    app.webui_svc = SimpleNamespace(
        is_running=lambda: True,
        stop=lambda: stopped.append(True),
    )
    app.standby = SimpleNamespace(
        is_active=lambda: True,
        trigger_standby=lambda: None,
    )
    monkeypatch.setattr(PhasmidApp, "_refresh_webui_status", lambda self: None)
    monkeypatch.setattr(
        PhasmidApp, "push_screen", lambda self, screen, callback=None: None
    )

    app.action_trigger_standby()

    assert stopped == [True], "standby left the WebUI serving"


def test_webui_cannot_be_exposed_from_a_sealed_state():
    """`w` is app-level and stays live on the Standby screen."""
    from phasmid.tui.app import PhasmidApp

    app = PhasmidApp.__new__(PhasmidApp)
    started: list[bool] = []

    app.webui_svc = SimpleNamespace(
        is_running=lambda: False,
        start=lambda: started.append(True) or True,
    )
    app.standby = SimpleNamespace(is_active=lambda: False)

    app.action_toggle_webui()

    assert started == [], "sealed state re-exposed the WebUI"


def test_expert_footer_shows_every_binding_at_the_documented_minimum_width():
    """The Expert footer silently loses bindings on a narrow terminal.

    Footer cells sit at fixed offsets rather than being compressed to fit,
    so anything past the terminal width is simply not drawn - with no
    ellipsis or other sign that the row is incomplete. `w` (WebUI) is an
    app-level binding appended after the screen's own, which puts the
    control for an exposed network interface last in the row and first to
    disappear. At 100 columns `l`, `?`, `q` and `w` were all off-screen.

    MIN_WIDTH is the measured threshold. It is asserted from both sides so
    that adding a binding to HomeScreen fails here and forces the number in
    the runbook to be updated rather than silently going stale.
    """
    import asyncio

    from textual.widgets._footer import FooterKey

    MIN_WIDTH = 123

    async def offscreen_at(width: int) -> list[str]:
        from phasmid.tui.app import PhasmidApp
        from phasmid.tui.screens.home import HomeScreen

        app = PhasmidApp(initial_screen="home")
        async with app.run_test(size=(width, 50)) as pilot:
            await pilot.pause()
            await app.push_screen(HomeScreen())
            await pilot.pause()
            return [
                key.key_display
                for key in app.screen.query(FooterKey)
                if key.region.x + key.region.width > width or key.region.width <= 0
            ]

    assert asyncio.run(offscreen_at(MIN_WIDTH)) == [], (
        f"Expert footer is incomplete at the documented minimum of "
        f"{MIN_WIDTH} columns"
    )
    assert asyncio.run(offscreen_at(MIN_WIDTH - 1)) != [], (
        f"the footer now fits below {MIN_WIDTH} columns; lower the documented "
        f"minimum in docs/submissions/Phasmid_Demo_Runbook.md"
    )


def test_luks_binding_is_hidden_while_the_luks_layer_is_disabled():
    """A binding for a switched-off subsystem should not cost footer columns.

    LUKS mode is disabled by default and `action_luks_panel` does nothing
    but say so, yet `l LUKS` occupied eight columns of a row that was
    already overflowing. Hiding it is what brings the full footer within
    123 columns instead of 131.
    """
    from phasmid.tui.screens.home import HomeScreen

    screen = HomeScreen.__new__(HomeScreen)

    with mock.patch("phasmid.tui.screens.home.PHASMID_LUKS_MODE", "disabled"):
        # Textual reads False as "disabled and not shown"; None would keep the
        # cell and only grey it, freeing no columns.
        assert screen.check_action("luks_panel", ()) is False

    with mock.patch("phasmid.tui.screens.home.PHASMID_LUKS_MODE", "enabled"):
        assert screen.check_action("luks_panel", ()) is True

    assert screen.check_action("open_vessel", ()) is True


def test_standby_clears_pending_notifications(monkeypatch):
    """Toasts outlive the screen that raised them.

    Textual renders notifications on the app's overlay rather than on the
    screen, so they survive the push to Standby and sit on top of it.
    Exposing the WebUI notifies with a 30 second timeout, and that message
    carries the access URL and the token - which would then be shown in
    plain text on the one screen whose entire purpose is to display nothing
    sensitive.
    """
    from phasmid.tui.app import PhasmidApp

    app = PhasmidApp.__new__(PhasmidApp)
    cleared: list[bool] = []

    app.webui_svc = SimpleNamespace(is_running=lambda: False, stop=lambda: None)
    app.standby = SimpleNamespace(is_active=lambda: True, trigger_standby=lambda: None)
    monkeypatch.setattr(PhasmidApp, "_refresh_webui_status", lambda self: None)
    monkeypatch.setattr(
        PhasmidApp, "clear_notifications", lambda self: cleared.append(True)
    )
    monkeypatch.setattr(
        PhasmidApp, "push_screen", lambda self, screen, callback=None: None
    )

    app.action_trigger_standby()

    assert cleared == [True], "standby left the WebUI token toast on screen"


def test_webui_binding_is_hidden_once_sealed():
    """`w` is app-level, so it is offered on the Standby screen too."""
    from phasmid.tui.app import PhasmidApp

    app = PhasmidApp.__new__(PhasmidApp)

    app.standby = SimpleNamespace(is_active=lambda: False)
    assert app.check_action("toggle_webui", ()) is False

    app.standby = SimpleNamespace(is_active=lambda: True)
    assert app.check_action("toggle_webui", ()) is True
    assert app.check_action("quit", ()) is True
