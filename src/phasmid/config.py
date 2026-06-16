import logging
import os

LOG = logging.getLogger(__name__)

DEFAULT_STATE_DIR = ".state"
STATE_BLOB_NAME = "store.bin"
STATE_KEY_NAME = "lock.bin"
VAULT_KEY_NAME = "access.bin"
PANIC_TOKEN_NAME = "signal.key"
PANIC_TRIGGER_NAME = "signal.trigger"
AUDIT_LOG_NAME = "events.log"
AUDIT_AUTH_NAME = "events.auth"
ROLE_STATE_NAME = "roles.bin"

# LUKS layer configuration
PHASMID_LUKS_MODE = os.getenv("PHASMID_LUKS_MODE", "disabled")
PHASMID_LUKS_CONTAINER = os.getenv("PHASMID_LUKS_CONTAINER", "/opt/phasmid/luks.img")
PHASMID_LUKS_MOUNT_POINT = os.getenv("PHASMID_LUKS_MOUNT_POINT", "/mnt/phasmid-vault")
PHASMID_LUKS_ITER_TIME_MS = int(os.getenv("PHASMID_LUKS_ITER_TIME_MS", "2000"))


def env_text(name: str, default: str = "") -> str:
    value = os.environ.get(name)
    if value is None:
        return default
    return str(value)


def env_int(name: str, default: int, minimum: int | None = None) -> int:
    raw = env_text(name, str(default))
    try:
        value = int(raw)
    except ValueError:
        value = default
    if minimum is not None:
        return max(minimum, value)
    return value


def state_dir() -> str:
    tmpfs = tmpfs_state_dir()
    if tmpfs:
        return tmpfs
    return env_text("PHASMID_STATE_DIR", DEFAULT_STATE_DIR)


def ensure_state_dir(path: str | None = None) -> str:
    resolved = path or state_dir()
    os.makedirs(resolved, mode=0o700, exist_ok=True)
    try:
        os.chmod(resolved, 0o700)
    except OSError as exc:
        LOG.debug("state directory permission update failed: %s", exc)
    return resolved


def tmpfs_state_dir() -> str | None:
    value = env_text("PHASMID_TMPFS_STATE", "").strip()
    return value or None


def env_flag(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.lower() not in {"0", "false", "off", "no", ""}


def purge_confirmation_required() -> bool:
    return env_flag("PHASMID_PURGE_CONFIRMATION", default=True)


def duress_mode_enabled() -> bool:
    return env_flag("PHASMID_DURESS_MODE", default=False)


def field_mode_enabled() -> bool:
    return env_flag("PHASMID_FIELD_MODE", default=False)


def experimental_object_model_enabled() -> bool:
    return env_flag("PHASMID_EXPERIMENTAL_OBJECT_MODEL", default=False)


def object_model_path() -> str:
    return env_text("PHASMID_OBJECT_MODEL_PATH", "").strip()


def passphrase_min_length() -> int:
    return env_int("PHASMID_MIN_PASSPHRASE_LENGTH", 10, minimum=1)


def access_max_failures() -> int:
    return env_int("PHASMID_ACCESS_MAX_FAILURES", 5, minimum=1)


def access_lockout_seconds() -> int:
    return env_int("PHASMID_ACCESS_LOCKOUT_SECONDS", 60, minimum=1)


def dual_approval_enabled() -> bool:
    return env_flag("PHASMID_DUAL_APPROVAL", default=False)


def web_host() -> str:
    return env_text("PHASMID_HOST", "127.0.0.1")


def web_port() -> int:
    return env_int("PHASMID_PORT", 8000, minimum=1)


def web_token_env() -> str:
    return env_text("PHASMID_WEB_TOKEN", "").strip()


def max_upload_bytes() -> int:
    return env_int("PHASMID_MAX_UPLOAD_BYTES", 25 * 1024 * 1024, minimum=1)


def restricted_session_seconds() -> int:
    return env_int("PHASMID_RESTRICTED_SESSION_SECONDS", 120, minimum=1)


def audit_enabled() -> bool:
    return env_flag("PHASMID_AUDIT", default=False)


def audit_filename_mode() -> str:
    return env_text("PHASMID_AUDIT_FILENAMES", "").strip().lower()


def profile_name() -> str:
    return env_text("PHASMID_PROFILE", "standard").strip().lower()


def hardware_secret_file() -> str:
    return env_text("PHASMID_HARDWARE_SECRET_FILE", "").strip()


def hardware_secret_value() -> str:
    return env_text("PHASMID_HARDWARE_SECRET", "")


def hardware_secret_prompt_enabled() -> bool:
    return env_text("PHASMID_HARDWARE_SECRET_PROMPT", "") == "1"


def state_secret() -> str:
    return env_text("PHASMID_STATE_SECRET", "")


def debug_enabled() -> bool:
    return env_flag("PHASMID_DEBUG", default=False)


def doctor_recent_seconds() -> int:
    return env_int("PHASMID_DOCTOR_RECENT_SECONDS", 86400, minimum=1)


def dummy_min_size_mb() -> int:
    return env_int("PHASMID_DUMMY_MIN_SIZE_MB", 50, minimum=0)


def dummy_min_file_count() -> int:
    return env_int("PHASMID_DUMMY_MIN_FILE_COUNT", 20, minimum=0)


def dummy_occupancy_warn() -> float:
    raw = env_text("PHASMID_DUMMY_OCCUPANCY_WARN", "0.10")
    try:
        value = float(raw)
    except ValueError:
        value = 0.10
    if value < 0.0:
        return 0.0
    return value


def dummy_profile_dir() -> str:
    return env_text("PHASMID_DUMMY_PROFILE_DIR", ".state/dummy_profile")


def dummy_container_path() -> str:
    return env_text("PHASMID_DUMMY_CONTAINER_PATH", "vault.bin")


def recognition_mode() -> str:
    mode = env_text("PHASMID_RECOGNITION_MODE", "strict").strip().lower()
    if mode in {"strict", "coercion_safe", "demo"}:
        return mode
    return "strict"


def true_unlock_threshold() -> float:
    raw = env_text("PHASMID_TRUE_UNLOCK_THRESHOLD", "0.85")
    try:
        value = float(raw)
    except ValueError:
        value = 0.85
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def dummy_fallback_threshold() -> float:
    raw = env_text("PHASMID_DUMMY_FALLBACK_THRESHOLD", "0.40")
    try:
        value = float(raw)
    except ValueError:
        value = 0.40
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def display_enabled() -> bool:
    return env_flag("PHASMID_ENABLE_DISPLAY", default=False)


def tui_dark_enabled() -> bool:
    return env_flag("PHASMID_DARK", default=False)


def tui_light_enabled() -> bool:
    return env_flag("PHASMID_LIGHT", default=False)


def context_profile_name() -> str:
    name = env_text("PHASMID_CONTEXT_PROFILE", "travel").strip().lower()
    return name or "travel"


def standby_hotkey() -> str:
    key = env_text("PHASMID_STANDBY_HOTKEY", "ctrl+s").strip().lower()
    return key or "ctrl+s"


def allow_no_object_binding() -> bool:
    return env_flag("PHASMID_ALLOW_NO_OBJECT_BINDING", default=False)
