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


def web_host_is_explicit() -> bool:
    """True when the operator set a non-empty `PHASMID_HOST`."""
    return bool(env_text("PHASMID_HOST", "").strip())


def webui_gadget_exposure_enabled() -> bool:
    """Opt-in WebUI exposure on the USB Ethernet gadget interface.

    When enabled the WebUI binds to the gadget interface address only, never to
    all interfaces.  Disabled by default so the WebUI stays loopback-only.
    """
    return env_flag("PHASMID_WEBUI_EXPOSE_GADGET", default=False)


def web_port() -> int:
    return env_int("PHASMID_PORT", 8000, minimum=1)


def web_token_env() -> str:
    return env_text("PHASMID_WEB_TOKEN", "").strip()


def store_token_env() -> str:
    """A fixed store-role WebUI token, pinned for reproducible demo runs.

    Mirrors ``web_token_env()``: set once, at process startup, so a live
    demo does not depend on remembering a value the TUI generated and
    showed exactly once.
    """
    return env_text("PHASMID_STORE_TOKEN", "").strip()


def recover_token_env() -> str:
    """A fixed recover-role WebUI token; see :func:`store_token_env`."""
    return env_text("PHASMID_RECOVER_TOKEN", "").strip()


def max_upload_bytes() -> int:
    return env_int("PHASMID_MAX_UPLOAD_BYTES", 25 * 1024 * 1024, minimum=1)


def restricted_session_seconds() -> int:
    return env_int("PHASMID_RESTRICTED_SESSION_SECONDS", 120, minimum=1)


def allowed_web_hosts() -> frozenset[str]:
    """Extra `Host` header values the WebUI accepts, beyond address literals.

    Address literals and loopback names are always accepted. Set this only when
    the operator reaches the WebUI by a DNS or mDNS name such as
    `phasmid.local`, which otherwise looks like a rebinding attempt.
    """
    raw = env_text("PHASMID_ALLOWED_HOSTS", "")
    return frozenset(part.strip().lower() for part in raw.split(",") if part.strip())


def ui_session_seconds() -> int:
    """Lifetime of an unlocked WebUI page session.

    The session is what gates page HTML, `/status`, and `/video_feed`, so it is
    deliberately shorter than an operator session at a desk and is re-established
    by re-entering the WebUI access token.
    """
    return env_int("PHASMID_UI_SESSION_SECONDS", 1800, minimum=1)


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


def _cue_ratio(name: str, default: float) -> float:
    raw = env_text(name, str(default))
    try:
        value = float(raw)
    except ValueError:
        return default
    if value < 0.0:
        return 0.0
    if value > 1.0:
        return 1.0
    return value


def cue_good_match_ratio() -> float:
    """Share of the reference template that has to be re-found to match.

    Tuning knob for the camera and lighting actually in front of the device:
    the counts these produce are capped by the absolute `min_good_matches`, so
    raising this can only ever make the cue stricter, and lowering it stops at
    `GOOD_MATCH_FLOOR`. Lower it if a bound object is refused when plainly
    present; raise it if something other than the object opens the cue.
    """
    return _cue_ratio("PHASMID_CUE_GOOD_MATCH_RATIO", 0.18)


def cue_inlier_ratio() -> float:
    """Share of the template whose geometry has to agree. See above."""
    return _cue_ratio("PHASMID_CUE_INLIER_RATIO", 0.15)


def cue_lowe_ratio() -> float:
    """How close a second-best descriptor may be before a match is discarded.

    Lowe's ratio test. Raising it admits more good matches, at the cost of
    admitting ambiguous ones - it loosens *what counts as the same feature*,
    which is the right knob when the object is recognisable but the light has
    moved since it was bound.

    It does not loosen geometry. A raised ratio that lets more matches through
    still has to survive RANSAC, so this alone will not rescue an object being
    shown at an angle it was not bound at.
    """
    return _cue_ratio("PHASMID_CUE_LOWE_RATIO", 0.75)


def cue_ransac_reprojection_px() -> float:
    """How far, in pixels, a correspondence may sit from the fitted geometry.

    RANSAC's reprojection tolerance. This is the knob for a cue that scores
    plenty of good matches and almost no inliers, which is what a *non-planar*
    object looks like when it is turned: the correspondences hold individually,
    but no single plane-to-plane transform explains them all, so they are
    discarded as outliers. Widening it admits mild perspective and mild depth.

    It is not a fix for a genuinely three-dimensional object seen from a new
    side. That needs the object bound from that side too, and this build binds
    one view per entry.
    """
    raw = env_text("PHASMID_CUE_RANSAC_PX", "5.0")
    try:
        value = float(raw)
    except ValueError:
        return 5.0
    if value < 1.0:
        return 1.0
    if value > 50.0:
        return 50.0
    return value


def camera_focus_mode() -> str:
    """What to do about the lens on a module that has a movable one.

    The Camera Module 3 family carries a motorised lens that picamera2 leaves
    where it powered up unless told otherwise. Pointed at an object on a desk,
    that is the wrong distance, and nothing anywhere reports it: an
    out-of-focus frame is a frame with very few corners in it, so the object
    fails to bind and fails to match, and every reading looks like a problem
    with the object.

    Values: `continuous` (default), `auto` for a single sweep at startup, `off`
    to leave the lens untouched, or a number of dioptres to park it at - 0 is
    infinity, 5.0 is roughly 20 cm. Ignored by fixed-focus modules, which have
    no lens control to set.
    """
    return env_text("PHASMID_CAMERA_FOCUS", "continuous").strip().lower()


def cue_debug_overlay_enabled() -> bool:
    """Draw the live cue scores on the camera preview.

    A bench setting, for the one question the badge cannot answer: not whether
    the object matches, but by how much. Aiming a camera is an iterative act -
    move it closer, turn the object, change the light - and doing that against
    a badge that only says yes or no means guessing which way to move.

    Off by default and deliberately not exposed in any UI. The preview is a
    capture-visible surface, and the scores say more about the mechanism than
    an operator under observation should be showing (CLM-05). This is for
    rehearsal with nobody watching, and it is the reason it is an environment
    variable rather than a button.
    """
    return env_flag("PHASMID_CUE_DEBUG", default=False)


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


def config_dir_override() -> str:
    return env_text("PHASMID_CONFIG_DIR", "").strip()
