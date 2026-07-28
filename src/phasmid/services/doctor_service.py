from __future__ import annotations

import os
import resource
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from ..config import (
    debug_enabled,
    doctor_recent_seconds,
    dummy_container_path,
    dummy_min_file_count,
    dummy_min_size_mb,
    dummy_occupancy_warn,
    dummy_profile_dir,
    state_dir,
)
from ..dummy_profile_eval import evaluate_dummy_profile, human_bytes
from ..luks_layer import LuksConfig, LuksLayer, LuksMode
from ..models.doctor import DoctorCheck, DoctorLevel, DoctorResult
from ..process_hardening import hardening_status
from ..volatile_state import check_volatile_state, volatile_state_path
from .profile_service import config_dir


def _check_dir_permissions(path: Path, label: str) -> DoctorCheck:
    if not path.exists():
        return DoctorCheck(
            name=label,
            level=DoctorLevel.INFO,
            message=f"{label} does not exist yet",
        )
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
        if mode & 0o077:
            return DoctorCheck(
                name=label,
                level=DoctorLevel.WARN,
                message=f"{label} is accessible to other users (mode {oct(mode)})",
                detail="Restrict with: chmod 700 " + str(path),
            )
        return DoctorCheck(
            name=label,
            level=DoctorLevel.OK,
            message=f"{label} permissions are restricted",
        )
    except OSError as exc:
        return DoctorCheck(
            name=label,
            level=DoctorLevel.WARN,
            message=f"Could not check {label} permissions: {exc}",
        )


def _check_file_permissions(path: Path, label: str) -> DoctorCheck:
    if not path.exists():
        return DoctorCheck(
            name=label,
            level=DoctorLevel.INFO,
            message=f"{label} does not exist yet",
        )
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
        if mode & 0o077:
            return DoctorCheck(
                name=label,
                level=DoctorLevel.WARN,
                message=f"{label} is readable by others (mode {oct(mode)})",
                detail="Restrict with: chmod 600 " + str(path),
            )
        return DoctorCheck(
            name=label,
            level=DoctorLevel.OK,
            message=f"{label} permissions are restricted",
        )
    except OSError as exc:
        return DoctorCheck(
            name=label,
            level=DoctorLevel.WARN,
            message=f"Could not check {label} permissions: {exc}",
        )


def _check_secure_random() -> DoctorCheck:
    try:
        import secrets

        _ = secrets.token_bytes(32)
        return DoctorCheck(
            name="Secure Randomness",
            level=DoctorLevel.OK,
            message="Secure randomness is available",
        )
    except Exception as exc:
        return DoctorCheck(
            name="Secure Randomness",
            level=DoctorLevel.FAIL,
            message=f"Secure randomness unavailable: {exc}",
        )


def _check_shell_history() -> DoctorCheck:
    shell = os.environ.get("SHELL", "")
    hist_vars = []
    if "bash" in shell:
        hist_vars.append("HISTFILE")
    if "zsh" in shell:
        hist_vars.append("HISTFILE")
    if "fish" in shell:
        hist_vars.append("fish_history")

    hist_file = os.environ.get("HISTFILE", "")
    if hist_file:
        hist_path = Path(hist_file).expanduser()
        if hist_path.exists():
            try:
                content = hist_path.read_text(encoding="utf-8", errors="ignore")
                if any(term in content for term in ("phasmid", "vault.bin")):
                    return DoctorCheck(
                        name="Shell History",
                        level=DoctorLevel.WARN,
                        message="Shell history contains recent Phasmid-related commands.",
                        detail="Clear history and prefer TUI passphrase input.",
                    )
            except OSError:
                pass
        return DoctorCheck(
            name="Shell History",
            level=DoctorLevel.WARN,
            message=f"Shell history is active ({hist_file}). "
            "CLI passphrase arguments may be recorded.",
            detail="Use the TUI to avoid passing passphrases as arguments.",
        )
    return DoctorCheck(
        name="Shell History",
        level=DoctorLevel.INFO,
        message="Shell history variable not detected. "
        "CLI passphrase arguments may still be recorded by some shells.",
    )


def _check_temp_dir() -> DoctorCheck:
    tmpdir = tempfile.gettempdir()
    p = Path(tmpdir)
    try:
        mode = stat.S_IMODE(p.stat().st_mode)
        if mode & 0o002:
            return DoctorCheck(
                name="Temporary Directory",
                level=DoctorLevel.WARN,
                message=f"Temporary directory {tmpdir} is world-writable",
                detail="Extracted files placed here may be accessible to other users.",
            )
        return DoctorCheck(
            name="Temporary Directory",
            level=DoctorLevel.OK,
            message=f"Temporary directory {tmpdir} permissions appear restricted",
        )
    except OSError:
        return DoctorCheck(
            name="Temporary Directory",
            level=DoctorLevel.INFO,
            message="Could not check temporary directory permissions",
        )


def _check_swap() -> DoctorCheck:
    if sys.platform == "linux":
        try:
            with open("/proc/swaps", "r") as f:
                lines = f.read().strip().splitlines()
            active = [ln for ln in lines[1:] if ln.strip()]
            if active:
                return DoctorCheck(
                    name="Swap",
                    level=DoctorLevel.WARN,
                    message="Swap is active. Sensitive data may be paged to disk.",
                    detail="Consider disabling swap or using encrypted swap.",
                )
            return DoctorCheck(
                name="Swap",
                level=DoctorLevel.OK,
                message="No active swap detected",
            )
        except OSError:
            pass
    return DoctorCheck(
        name="Swap",
        level=DoctorLevel.INFO,
        message="Swap status check not available on this platform (best effort)",
    )


def _check_scrollback() -> DoctorCheck:
    return DoctorCheck(
        name="Terminal Scrollback",
        level=DoctorLevel.INFO,
        message="Terminal scrollback may retain sensitive output. "
        "Clear scrollback after sensitive operations.",
    )


def _check_volatile_state() -> DoctorCheck:
    path = volatile_state_path()
    if path is None:
        return DoctorCheck(
            name="Volatile Key Store",
            level=DoctorLevel.INFO,
            message="PHASMID_TMPFS_STATE not configured (persistent state in use)",
        )
    ok, message = check_volatile_state(path)
    if ok:
        return DoctorCheck(
            name="Volatile Key Store",
            level=DoctorLevel.OK,
            message=f"Volatile state path accessible: {path}",
            detail=message,
        )
    return DoctorCheck(
        name="Volatile Key Store",
        level=DoctorLevel.FAIL,
        message=f"Volatile state path unavailable: {message}",
        detail="Ensure the tmpfs mount is in place before starting Phasmid.",
    )


def _check_process_hardening() -> DoctorCheck:
    status = hardening_status()
    if status is None:
        return DoctorCheck(
            name="Process Hardening",
            level=DoctorLevel.INFO,
            message="Process hardening has not been applied yet in this session",
        )
    applied = [k for k, v in status.as_dict().items() if v]
    skipped = [k for k, v in status.as_dict().items() if not v]
    if not skipped:
        return DoctorCheck(
            name="Process Hardening",
            level=DoctorLevel.OK,
            message="All process hardening steps applied",
        )
    return DoctorCheck(
        name="Process Hardening",
        level=DoctorLevel.INFO,
        message=f"Hardening partial: applied={applied}, skipped={skipped} "
        "(skipped steps are platform-dependent best-effort)",
    )


def _check_debug_logging() -> DoctorCheck:
    if debug_enabled():
        return DoctorCheck(
            name="Debug Logging",
            level=DoctorLevel.WARN,
            message="PHASMID_DEBUG is enabled. Verbose output may leak sensitive data.",
        )
    return DoctorCheck(
        name="Debug Logging",
        level=DoctorLevel.OK,
        message="Debug logging is not enabled",
    )


def _check_recent_documents_cache() -> DoctorCheck:
    """Best-effort check for recent-document artifact leakage.

    Threat model reference: docs/THREAT_MODEL.md (Attack Surfaces / local passive observer).
    """
    xbel = Path.home() / ".local" / "share" / "recently-used.xbel"
    if not xbel.exists():
        return DoctorCheck(
            name="Recent Documents Cache",
            level=DoctorLevel.INFO,
            message="Recent documents cache not found (unknown on this host).",
        )
    try:
        content = xbel.read_text(encoding="utf-8", errors="ignore").lower()
    except OSError as exc:
        return DoctorCheck(
            name="Recent Documents Cache",
            level=DoctorLevel.INFO,
            message=f"Could not inspect recent documents cache: {exc}",
        )
    if any(term in content for term in ("vault.bin", "phasmid")):
        return DoctorCheck(
            name="Recent Documents Cache",
            level=DoctorLevel.WARN,
            message="Recent documents cache contains Phasmid-related references.",
            detail="Clear recently-used entries before high-risk movement.",
        )
    return DoctorCheck(
        name="Recent Documents Cache",
        level=DoctorLevel.OK,
        message="No obvious Phasmid references in recent documents cache.",
    )


def _check_thumbnail_cache() -> DoctorCheck:
    """Best-effort thumbnail cache leak check using Freedesktop Thumb::URI hints."""
    thumbs_dir = Path.home() / ".cache" / "thumbnails"
    if not thumbs_dir.exists():
        return DoctorCheck(
            name="Thumbnail Cache",
            level=DoctorLevel.INFO,
            message="Thumbnail cache not found (unknown on this host).",
        )
    inspected = 0
    try:
        for candidate in thumbs_dir.rglob("*.png"):
            inspected += 1
            if inspected > 500:
                break
            blob = candidate.read_bytes()
            lowered = blob.lower()
            if any(
                term in lowered for term in (b"thumb::uri", b"phasmid", b"vault.bin")
            ):
                return DoctorCheck(
                    name="Thumbnail Cache",
                    level=DoctorLevel.WARN,
                    message="Thumbnail cache may contain Phasmid-related file traces.",
                    detail="Consider clearing thumbnail cache for local hygiene.",
                )
    except OSError as exc:
        return DoctorCheck(
            name="Thumbnail Cache",
            level=DoctorLevel.INFO,
            message=f"Could not inspect thumbnail cache: {exc}",
        )
    return DoctorCheck(
        name="Thumbnail Cache",
        level=DoctorLevel.OK,
        message="No obvious Phasmid traces detected in thumbnail cache sample.",
    )


def _check_system_journal() -> DoctorCheck:
    """Best-effort systemd journal trace check; non-Linux returns unknown."""
    if sys.platform != "linux":
        return DoctorCheck(
            name="System Journal",
            level=DoctorLevel.INFO,
            message="System journal check is Linux-only (unknown on this platform).",
        )
    try:
        proc = subprocess.run(
            ["journalctl", "--user", "-n", "200", "--no-pager"],
            check=False,
            capture_output=True,
            text=True,
            timeout=3,
        )
    except (FileNotFoundError, subprocess.SubprocessError, OSError):
        return DoctorCheck(
            name="System Journal",
            level=DoctorLevel.INFO,
            message="System journal not accessible for inspection.",
        )
    content = (proc.stdout or "").lower()
    if any(term in content for term in ("phasmid", "vault.bin")):
        return DoctorCheck(
            name="System Journal",
            level=DoctorLevel.WARN,
            message="System journal contains recent Phasmid-related process traces.",
            detail="Review and prune logs as required by local policy.",
        )
    return DoctorCheck(
        name="System Journal",
        level=DoctorLevel.OK,
        message="No obvious Phasmid traces in recent user journal sample.",
    )


def _check_core_dumps() -> DoctorCheck:
    """Check whether process core dumps are disabled (`ulimit -c` equivalent)."""
    try:
        soft, _hard = resource.getrlimit(resource.RLIMIT_CORE)
    except (ValueError, OSError):
        return DoctorCheck(
            name="Core Dumps",
            level=DoctorLevel.INFO,
            message="Core dump limit could not be determined.",
        )
    if soft == 0:
        return DoctorCheck(
            name="Core Dumps",
            level=DoctorLevel.OK,
            message="Core dumps are disabled for this session.",
        )
    return DoctorCheck(
        name="Core Dumps",
        level=DoctorLevel.WARN,
        message=f"Core dump limit is non-zero ({soft}).",
        detail="Set `ulimit -c 0` for sensitive sessions.",
    )


def _check_compressed_swap() -> DoctorCheck:
    """Check zswap/zram posture because compressed swap can retain sensitive pages."""
    if sys.platform != "linux":
        return DoctorCheck(
            name="Compressed Swap",
            level=DoctorLevel.INFO,
            message="Compressed swap check is Linux-only (unknown on this platform).",
        )
    try:
        zswap_flag = Path("/sys/module/zswap/parameters/enabled")
        zswap_enabled = zswap_flag.exists() and zswap_flag.read_text(
            encoding="utf-8", errors="ignore"
        ).strip().upper() in {"Y", "1"}
    except OSError:
        zswap_enabled = False
    zram_devices = list(Path("/sys/block").glob("zram*"))
    if zswap_enabled or zram_devices:
        return DoctorCheck(
            name="Compressed Swap",
            level=DoctorLevel.WARN,
            message="Compressed swap (zswap/zram) appears enabled.",
            detail="Disable compressed swap for stricter local artifact hygiene.",
        )
    return DoctorCheck(
        name="Compressed Swap",
        level=DoctorLevel.OK,
        message="No active zswap/zram indicators detected.",
    )


def _check_recent_file_activity(vault_path: Path) -> DoctorCheck:
    """Warn when vault atime/mtime imply very recent usage exposure."""
    if not vault_path.exists():
        return DoctorCheck(
            name="Recent File Activity",
            level=DoctorLevel.INFO,
            message="Vault file not present; recent activity check unavailable.",
        )
    try:
        st = vault_path.stat()
    except OSError as exc:
        return DoctorCheck(
            name="Recent File Activity",
            level=DoctorLevel.INFO,
            message=f"Could not inspect vault timestamps: {exc}",
        )
    now = time.time()
    threshold = doctor_recent_seconds()
    if now - max(st.st_mtime, st.st_atime) <= threshold:
        return DoctorCheck(
            name="Recent File Activity",
            level=DoctorLevel.WARN,
            message="Vault file timestamps indicate recent local use.",
            detail="Recent atime/mtime can reveal operational timing.",
        )
    return DoctorCheck(
        name="Recent File Activity",
        level=DoctorLevel.OK,
        message="Vault file timestamps are not recent.",
    )


def _check_vault_size_record(vault_path: Path) -> DoctorCheck:
    """Compare vault size against optional local baseline record.

    Baseline file: `<state_dir>/vault.size` (bytes as integer).
    """
    if not vault_path.exists():
        return DoctorCheck(
            name="Vault Size Record",
            level=DoctorLevel.INFO,
            message="Vault file not present; size baseline check unavailable.",
        )
    baseline_file = Path(state_dir()) / "vault.size"
    if not baseline_file.exists():
        return DoctorCheck(
            name="Vault Size Record",
            level=DoctorLevel.INFO,
            message="Vault size baseline is not recorded (unknown).",
        )
    try:
        expected = int(baseline_file.read_text(encoding="utf-8").strip())
        actual = vault_path.stat().st_size
    except (OSError, ValueError) as exc:
        return DoctorCheck(
            name="Vault Size Record",
            level=DoctorLevel.INFO,
            message=f"Vault size baseline could not be parsed: {exc}",
        )
    if actual != expected:
        return DoctorCheck(
            name="Vault Size Record",
            level=DoctorLevel.WARN,
            message=f"Vault size differs from baseline (expected {expected}, actual {actual}).",
            detail="Investigate unexpected container-size drift.",
        )
    return DoctorCheck(
        name="Vault Size Record",
        level=DoctorLevel.OK,
        message="Vault size matches local baseline record.",
    )


def _check_luks_statuses() -> list[DoctorCheck]:
    cfg = LuksConfig.from_env()
    mode_value = cfg.mode.value
    checks: list[DoctorCheck] = []
    if cfg.mode == LuksMode.DISABLED:
        checks.append(
            DoctorCheck(
                name="LUKS Mode",
                level=DoctorLevel.INFO,
                message="[DISABLED] LUKS mode is disabled",
            )
        )
        checks.append(
            DoctorCheck(
                name="LUKS cryptsetup",
                level=DoctorLevel.INFO,
                message="[DISABLED] skipped because LUKS mode is disabled",
            )
        )
        checks.append(
            DoctorCheck(
                name="Local container path",
                level=DoctorLevel.INFO,
                message="[DISABLED] skipped because LUKS mode is disabled",
            )
        )
        checks.append(
            DoctorCheck(
                name="Local container mount state",
                level=DoctorLevel.INFO,
                message="[DISABLED] skipped because LUKS mode is disabled",
            )
        )
        checks.append(
            DoctorCheck(
                name="LUKS key-store tmpfs",
                level=DoctorLevel.INFO,
                message="[DISABLED] skipped because LUKS mode is disabled",
            )
        )
        return checks

    if mode_value in {LuksMode.FILE_CONTAINER.value, LuksMode.PARTITION.value}:
        checks.append(
            DoctorCheck(
                name="LUKS Mode",
                level=DoctorLevel.OK,
                message=f"LUKS mode configured: {mode_value}",
            )
        )
    else:
        checks.append(
            DoctorCheck(
                name="LUKS Mode",
                level=DoctorLevel.FAIL,
                message=f"Invalid LUKS mode value: {mode_value}",
            )
        )

    if shutil.which("cryptsetup"):
        checks.append(
            DoctorCheck(
                name="LUKS cryptsetup",
                level=DoctorLevel.OK,
                message="cryptsetup is available",
            )
        )
    else:
        checks.append(
            DoctorCheck(
                name="LUKS cryptsetup",
                level=DoctorLevel.WARN,
                message="cryptsetup is not available",
            )
        )

    if cfg.mode == LuksMode.FILE_CONTAINER:
        exists = Path(cfg.container_path).exists()
        checks.append(
            DoctorCheck(
                name="Local container path",
                level=DoctorLevel.OK if exists else DoctorLevel.WARN,
                message=(
                    "local container file is reachable"
                    if exists
                    else "local container file is not reachable"
                ),
            )
        )
    else:
        exists = Path(cfg.container_path).exists()
        checks.append(
            DoctorCheck(
                name="Local container path",
                level=DoctorLevel.OK if exists else DoctorLevel.WARN,
                message=(
                    "local container partition path is reachable"
                    if exists
                    else "local container partition path is not reachable"
                ),
            )
        )

    status = LuksLayer(cfg).status()
    checks.append(
        DoctorCheck(
            name="Local container mount state",
            level=DoctorLevel.OK,
            message=(
                "local container is mounted"
                if status.mounted
                else "local container is unmounted"
            ),
        )
    )

    tmpfs_ok = False
    if sys.platform == "linux":
        try:
            probe = subprocess.run(
                ["findmnt", "-n", "-o", "FSTYPE", "/run/phasmid"],
                check=False,
                capture_output=True,
                text=True,
                timeout=2,
            )
            tmpfs_ok = probe.returncode == 0 and probe.stdout.strip() == "tmpfs"
        except Exception:
            tmpfs_ok = False
    checks.append(
        DoctorCheck(
            name="LUKS key-store tmpfs",
            level=DoctorLevel.OK if tmpfs_ok else DoctorLevel.WARN,
            message=(
                "LUKS key-store path is tmpfs-backed"
                if tmpfs_ok
                else "LUKS key-store path is not confirmed as tmpfs-backed"
            ),
        )
    )
    return checks


_DUMMY_ADVISORY_ENV = (
    "PHASMID_DUMMY_PROFILE_DIR",
    "PHASMID_DUMMY_CONTAINER_PATH",
)


def _dummy_advisory_configured() -> bool:
    """True when the operator has pointed the advisory at their own material.

    A variable set to an empty or blank string counts as unset. Blanking a
    variable is how an operator turns a setting off, and ``Path("")`` is the
    current working directory, which exists everywhere - taking it as a
    configured path would silently measure whatever directory the console was
    launched from and report its size as the container's.
    """
    return any(os.environ.get(name, "").strip() for name in _DUMMY_ADVISORY_ENV)


def _check_dummy_profile_plausibility() -> list[DoctorCheck]:
    """Advisory over material the operator points this at.

    PHASMID_DUMMY_PROFILE_DIR and PHASMID_DUMMY_CONTAINER_PATH are operator
    settings (docs/CONFIGURATION.md). Pointed at material the operator
    prepared, these report its volume - size, file count, occupancy against
    the container - which is worth knowing before relying on it.

    Left at their defaults they point at paths no operation writes, so every
    check warned on every device forever and the warnings could not be acted
    on. Unconfigured now reports "not configured" rather than a deficiency:
    an advisory nobody asked for is not a finding.

    Whether the advisory is wanted is decided by the environment variables,
    not by whether the default paths happen to exist. The container default
    is the literal ``vault.bin``, which is also the CLI's default vessel name
    and the WebUI's legacy fallback, so any device that has ever stored a
    file without naming a Vessel has that path - testing for it would hand
    the whole warning storm back to an operator who never asked for this.

    Volume is all this measures. Whether the material is convincing is not
    something the tool can judge, and it does not claim to.
    """
    if not _dummy_advisory_configured():
        return [
            DoctorCheck(
                name=name,
                level=DoctorLevel.INFO,
                message="not configured",
                detail=(
                    "Set PHASMID_DUMMY_PROFILE_DIR and "
                    "PHASMID_DUMMY_CONTAINER_PATH to have this advisory "
                    "report on material you prepared. Material disclosed "
                    "under pressure is supplied by the operator; this checks "
                    "its volume, not whether it is convincing."
                ),
            )
            for name in (
                "Dummy Profile Size",
                "Dummy Profile File Count",
                "Dummy Profile Occupancy Ratio",
                "Dummy Profile Size Distribution",
                "Dummy Profile Plausibility",
            )
        ]

    evaluation = evaluate_dummy_profile(
        dummy_profile_dir=dummy_profile_dir(),
        container_path=dummy_container_path(),
        min_size_mb=dummy_min_size_mb(),
        min_file_count=dummy_min_file_count(),
        occupancy_warn_threshold=dummy_occupancy_warn(),
    )
    warning_level = DoctorLevel.WARN if evaluation.warnings else DoctorLevel.OK
    ratio_pct = evaluation.occupancy_ratio * 100.0

    checks = [
        DoctorCheck(
            name="Dummy Profile Size",
            level=warning_level,
            message=(
                f"dummy profile size: {human_bytes(evaluation.dummy_size_bytes)}; "
                f"container size: {human_bytes(evaluation.container_size_bytes)}"
            ),
        ),
        DoctorCheck(
            name="Dummy Profile File Count",
            level=warning_level,
            message=f"dummy profile file count: {evaluation.file_count}",
        ),
        DoctorCheck(
            name="Dummy Profile Occupancy Ratio",
            level=warning_level,
            message=f"occupancy ratio: {ratio_pct:.2f}%",
        ),
        DoctorCheck(
            name="Dummy Profile Size Distribution",
            level=DoctorLevel.INFO,
            message=(
                "file size distribution: "
                f"min={human_bytes(evaluation.min_file_size)}, "
                f"p50={human_bytes(evaluation.p50_file_size)}, "
                f"max={human_bytes(evaluation.max_file_size)}"
            ),
        ),
    ]
    if evaluation.warnings:
        checks.append(
            DoctorCheck(
                name="Dummy Profile Plausibility",
                level=DoctorLevel.WARN,
                message="Prepared material is below the configured volume thresholds",
                detail="; ".join(evaluation.warnings),
            )
        )
    else:
        checks.append(
            DoctorCheck(
                name="Dummy Profile Plausibility",
                level=DoctorLevel.OK,
                message="Prepared material meets the configured volume thresholds",
                detail="Volume only. Whether the material is convincing is not assessed here.",
            )
        )
    return checks


def run_doctor_checks(output_dir: str | None = None) -> DoctorResult:
    cfg = config_dir()
    vault_path = Path("vault.bin")
    checks = [
        _check_dir_permissions(cfg, "Configuration directory"),
        _check_dir_permissions(cfg / "profiles", "Profile directory"),
        _check_temp_dir(),
    ]

    if output_dir:
        checks.append(
            _check_dir_permissions(Path(output_dir).expanduser(), "Output directory")
        )

    checks += [
        _check_secure_random(),
        _check_volatile_state(),
    ]

    checks += _check_luks_statuses()
    checks += _check_dummy_profile_plausibility()

    checks += [
        _check_process_hardening(),
        _check_recent_documents_cache(),
        _check_thumbnail_cache(),
        _check_system_journal(),
        _check_core_dumps(),
        _check_compressed_swap(),
        _check_shell_history(),
        _check_recent_file_activity(vault_path),
        _check_vault_size_record(vault_path),
        _check_swap(),
        _check_scrollback(),
        _check_debug_logging(),
    ]

    return DoctorResult(checks=checks)


class DoctorService:
    def run(self, output_dir: str | None = None) -> DoctorResult:
        return run_doctor_checks(output_dir)
