import io
import ipaddress
import logging
import os
import secrets
import time
import urllib.parse
from pathlib import Path

from fastapi import (
    Depends,
    FastAPI,
    File,
    Form,
    Header,
    HTTPException,
    Request,
    UploadFile,
)
from fastapi.responses import (
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import strings as text
from .attempt_limiter import AttemptLimiter
from .audit import audit_event
from .capabilities import Capability, active_policy, capability_enabled
from .config import (
    AUDIT_LOG_NAME,
    allowed_web_hosts,
    audit_enabled,
    duress_mode_enabled,
    field_mode_enabled,
    max_upload_bytes,
    purge_confirmation_required,
    restricted_session_seconds,
    state_dir,
    ui_session_seconds,
    web_host,
    web_port,
    web_token_env,
)
from .crypto_boundary import ensure_crypto_self_tests
from .kdf_providers import hardware_binding_status
from .metadata import metadata_risk_report, scrub_metadata
from .passphrase_policy import check_store_passphrases
from .process_hardening import apply_process_hardening
from .restricted_actions import (
    DESTROY_FACE_PHRASE,
    DESTRUCTIVE_CLEAR_PHRASE,
    EMERGENCY_BRICK_PHRASE,
    INITIALIZE_CONTAINER_PHRASE,
    OVERWRITE_CONFIRMATION_PHRASE,
    RESTRICTED_ACTION_POLICIES,
    RESTRICTED_CONFIRMATION_PHRASE,
    RestrictedActionRejected,
    evaluate_restricted_action,
)
from .services.access_cue_service import access_cue_service
from .services.access_token_service import (
    ROLE_RECOVER,
    ROLE_STORE,
    access_token_service,
)
from .services.audit_service import build_audit_report
from .services.doctor_service import run_doctor_checks
from .services.guided_service import get_workflows
from .services.inspection_service import inspect_vessel
from .services.vessel_workflow_service import VesselWorkflowService
from .services.web_target_service import (
    LEGACY_CONTAINER_PATH,
    face_for_mode,
    forget_container_contents,
    forget_face_contents,
    resolve_web_container,
    resolve_web_vessel,
)
from .vault_core import PhasmidVault
from .volatile_state import require_volatile_state

app = FastAPI(title="Phasmid - Local Secure Interface")
LOG = logging.getLogger(__name__)
app.mount(
    "/static",
    StaticFiles(directory=str(Path(__file__).with_name("static"))),
    name="static",
)


@app.on_event("startup")
async def startup_self_tests():
    apply_process_hardening()
    require_volatile_state()
    ensure_crypto_self_tests()
    publish_web_token()


@app.on_event("shutdown")
async def shutdown_cleanup():
    clear_published_web_token()
    try:
        access_cue_service.close()
    except Exception as exc:
        LOG.error("Camera cleanup on shutdown failed: %s", exc)


templates = Jinja2Templates(directory=str(Path(__file__).with_name("templates")))

# Fallback container, used only until a Vessel exists on the device. The
# live target is resolved by services.web_target_service so that this
# interface and the operator console act on the same file.
vault = PhasmidVault(LEGACY_CONTAINER_PATH)
WEB_TOKEN = web_token_env() or secrets.token_urlsafe(32)
MAX_UPLOAD_BYTES = max_upload_bytes()
RATE_LIMIT_WINDOW = 60
RATE_LIMIT_MAX = 20
RESTRICTED_SESSION_COOKIE = "phasmid_restricted_session"
RESTRICTED_SESSION_TTL_SECONDS = restricted_session_seconds()
_restricted_sessions = {}
_access_attempts = AttemptLimiter()

UI_SESSION_COOKIE = "phasmid_ui_session"
UI_SESSION_TTL_SECONDS = ui_session_seconds()
_ui_sessions = {}
_unlock_attempts = AttemptLimiter()
WEB_TOKEN_FILE_NAME = "webui_token"
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})

ENTRY_TO_MODE = {
    "entry_1": access_cue_service.modes()[0],
    "entry_2": access_cue_service.modes()[1],
}
LEGACY_SELECTOR_TO_ENTRY = {
    "prof" + "ile_a": "entry_1",
    "prof" + "ile_b": "entry_2",
}
MODE_TO_ENTRY = {mode: entry for entry, mode in ENTRY_TO_MODE.items()}
ENTRY_LABELS = {
    "entry_1": "Entry 1",
    "entry_2": "Entry 2",
}
SECURITY_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate, max-age=0",
    "Pragma": "no-cache",
    "Expires": "0",
    "Content-Security-Policy": (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline'; "
        "style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data: blob:; "
        "connect-src 'self'; "
        "frame-ancestors 'none'; "
        "form-action 'self'; "
        "base-uri 'self'"
    ),
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "Referrer-Policy": "no-referrer",
    "Permissions-Policy": "camera=(self), microphone=(), geolocation=(), payment=(), usb=()",
    "Cross-Origin-Opener-Policy": "same-origin",
}


def _apply_security_headers(response):
    for name, value in SECURITY_HEADERS.items():
        response.headers[name] = value
    return response


def _host_header_allowed(request):
    """Reject a `Host` that is a DNS name rather than an address.

    DNS rebinding needs a name to rebind.  An address literal cannot be
    repointed at the WebUI mid-session, so accepting only address literals (plus
    `localhost` and any operator-configured name) closes the rebinding path
    without asking the operator for anything.
    """
    host = request.headers.get("host", "")
    if host.startswith("["):
        # RFC 7230 bracketed IPv6 literal, optionally followed by :port.
        end = host.find("]")
        hostname = host[1:end] if end != -1 else ""
    elif host.count(":") > 1:
        hostname = host  # bare IPv6 literal; tolerated even though unbracketed
    else:
        hostname = host.rsplit(":", 1)[0] if ":" in host else host
    hostname = hostname.strip().lower()
    if not hostname:
        return False
    if hostname in LOOPBACK_HOSTS:
        return True
    if hostname in allowed_web_hosts():
        return True
    try:
        ipaddress.ip_address(hostname)
    except ValueError:
        return False
    return True


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    if not _host_header_allowed(request):
        return _apply_security_headers(
            JSONResponse({"error": text.OPERATION_UNAVAILABLE}, status_code=400)
        )
    response = await call_next(request)
    return _apply_security_headers(response)


def display_entry_label(entry_id):
    return ENTRY_LABELS.get(entry_id, "Entry")


def active_vault() -> PhasmidVault:
    return resolve_web_container(vault)


def _other_mode(mode: str) -> str:
    others = [item for item in access_cue_service.modes() if item != mode]
    return others[0] if others else mode


def resolve_entry(entry_id):
    entry_id = LEGACY_SELECTOR_TO_ENTRY.get(entry_id, entry_id)
    if entry_id not in ENTRY_TO_MODE:
        raise ValueError(f"unsupported entry id: {entry_id}")
    return ENTRY_TO_MODE[entry_id]


def mode_to_entry(mode):
    return MODE_TO_ENTRY.get(mode)


def _plain_form_value(value, default=""):
    return value if isinstance(value, str) else default


def _client_id(request):
    return request.client.host if request.client else "unknown"


def _restricted_session_token(request):
    return request.cookies.get(RESTRICTED_SESSION_COOKIE, "")


def web_token_path():
    return Path(state_dir()) / WEB_TOKEN_FILE_NAME


def publish_web_token():
    """Write the current access token to the state directory for local operators.

    The WebUI is started as a subprocess (TUI `w` key) or directly, so the
    operator has no other way to learn a per-process token.  The state directory
    already holds the local access key, so this does not widen the file-system
    trust boundary; it is written `0600` and removed at shutdown.
    """
    path = web_token_path()
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(WEB_TOKEN + "\n", encoding="utf-8")
        os.chmod(path, 0o600)
    except OSError as exc:
        LOG.error("Access token publication failed: %s", exc)


def clear_published_web_token():
    try:
        web_token_path().unlink()
    except FileNotFoundError:
        pass
    except OSError as exc:
        LOG.debug("Access token cleanup failed: %s", exc)


def _ui_session_token(request):
    return request.cookies.get(UI_SESSION_COOKIE, "")


def _create_ui_session(client_id, role: str = ROLE_STORE):
    token = secrets.token_urlsafe(32)
    _ui_sessions[token] = {
        "client_id": client_id,
        "expires_at": time.time() + UI_SESSION_TTL_SECONDS,
        "role": role,
    }
    return token


def _is_loopback_client(request):
    client = getattr(request, "client", None)
    host = getattr(client, "host", "") if client else ""
    return host in LOOPBACK_HOSTS


def _ui_unlock_required(request):
    """True when the caller must present the access token before seeing pages.

    A loopback peer is on the device itself, alongside the TUI that already has
    full local control, so requiring a token there buys nothing and costs the
    operator a step on every session.  Any other peer — a USB-tethered host, a
    gadget-interface neighbour, anything reached through an explicit
    `PHASMID_HOST` — is a separate machine and must authenticate.
    """
    return not _is_loopback_client(request)


def _ui_unlocked(request):
    """True when the caller may be served pages, status, and the camera stream.

    Page HTML carries the mutation token, so for a remote peer this is what
    keeps the token out of a response it can obtain without credentials.
    """
    if not _ui_unlock_required(request):
        return True
    token = _ui_session_token(request)
    if not token:
        return False
    session = _ui_sessions.get(token)
    if not session:
        return False
    if session["client_id"] != _client_id(request):
        return False
    if session["expires_at"] <= time.time():
        _ui_sessions.pop(token, None)
        return False
    return True


def require_ui_unlock(request: Request):
    if not _ui_unlocked(request):
        raise HTTPException(status_code=423, detail=text.UI_LOCKED)


def _ui_session_role(request) -> str:
    """Return the role the current caller's session was granted.

    A loopback peer skips `/unlock` entirely and is already fully trusted
    (same device as the TUI), so it gets the store role for free, matching
    the trust level it already has everywhere else. A remote peer whose
    session cannot be found - which `require_ui_unlock` should already have
    rejected by the time this is consulted - fails closed to the recover
    role rather than defaulting to full trust.
    """
    if not _ui_unlock_required(request):
        return ROLE_STORE
    session = _ui_sessions.get(_ui_session_token(request))
    if not session:
        return ROLE_RECOVER
    return str(session.get("role", ROLE_RECOVER))


def require_store_role(request: Request):
    # 404, not 403: a distinct status or message here would tell a
    # recover-role session (or anyone probing the URL bar) that a
    # higher-privileged tier exists at this route, even though they can never
    # reach it. `web_panic_trigger` already uses this same "wrong credential
    # looks identical to no such route" pattern for the same reason.
    if _ui_session_role(request) != ROLE_STORE:
        raise HTTPException(status_code=404)


def _create_restricted_session(client_id):
    token = secrets.token_urlsafe(32)
    _restricted_sessions[token] = {
        "client_id": client_id,
        "expires_at": time.time() + RESTRICTED_SESSION_TTL_SECONDS,
    }
    return token


def _restricted_session_valid(request):
    token = _restricted_session_token(request)
    if not token:
        return False
    session = _restricted_sessions.get(token)
    if not session:
        return False
    if session["client_id"] != _client_id(request):
        return False
    if session["expires_at"] <= time.time():
        _restricted_sessions.pop(token, None)
        return False
    return True


def _restricted_session_seconds_remaining(request):
    token = _restricted_session_token(request)
    if not token:
        return 0
    session = _restricted_sessions.get(token)
    if not session:
        return 0
    if session["client_id"] != _client_id(request):
        return 0
    remaining = int(session["expires_at"] - time.time())
    return remaining if remaining > 0 else 0


def require_restricted_confirmation(request: Request):
    if not _restricted_session_valid(request):
        raise HTTPException(
            status_code=403, detail=text.RESTRICTED_CONFIRMATION_REQUIRED
        )


def _require_restricted_when_field_mode(request):
    if field_mode_enabled() and not _restricted_session_valid(request):
        raise HTTPException(
            status_code=403, detail=text.RESTRICTED_CONFIRMATION_REQUIRED
        )


def require_capability(capability: Capability):
    if not capability_enabled(capability):
        raise HTTPException(status_code=403, detail=text.OPERATION_UNAVAILABLE)


def require_restricted_action(action_id, request, confirmation=""):
    policy = RESTRICTED_ACTION_POLICIES[action_id]
    try:
        evaluate_restricted_action(
            policy,
            capability_allowed=capability_enabled(policy.capability),
            restricted_confirmed=_restricted_session_valid(request),
            confirmation=confirmation,
        )
    except RestrictedActionRejected as exc:
        raise HTTPException(status_code=403, detail=exc.message) from exc


def _guard_page(request):
    if _ui_unlocked(request):
        return None
    return RedirectResponse(url="/unlock", status_code=303)


def _guard_store_page(request):
    """Like :func:`_guard_page`, but also confined to a store-role session.

    A recover-token session is unlocked - it just never reaches this page.
    A redirect or a distinct error here would still tell it (or anyone
    guessing at the URL bar) that a page exists that it cannot open, so a
    role mismatch raises the same 404 `require_store_role` raises for the
    API routes rather than returning anything route-shaped.
    """
    guard = _guard_page(request)
    if guard:
        return guard
    if _ui_session_role(request) != ROLE_STORE:
        raise HTTPException(status_code=404)
    return None


def require_web_token(x_phasmid_token: str = Header(default="")):
    if not secrets.compare_digest(x_phasmid_token, WEB_TOKEN):
        raise HTTPException(status_code=403, detail=text.INVALID_WEB_TOKEN)


_rate_limit: dict[str, list[float]] = {}


def enforce_rate_limit(request: Request):
    client = request.client.host if request.client else "unknown"
    key = f"{client}:{request.url.path}"
    now = time.time()
    bucket = [
        timestamp
        for timestamp in _rate_limit.get(key, [])
        if now - timestamp < RATE_LIMIT_WINDOW
    ]
    if len(bucket) >= RATE_LIMIT_MAX:
        raise HTTPException(status_code=429, detail=text.RATE_LIMIT_EXCEEDED)
    bucket.append(now)
    _rate_limit[key] = bucket


async def read_limited_upload(file: UploadFile):
    data = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(data) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail=text.UPLOAD_TOO_LARGE)
    return data


def _template_context(request: Request, active="home", **extra):
    restricted_confirmed = _restricted_session_valid(request)
    ui_unlocked = _ui_unlocked(request)
    context = {
        "request": request,
        "active": active,
        # The mutation token is never rendered into a response that an
        # unauthenticated client can obtain; it is a CSRF token for an already
        # unlocked session, not the thing that establishes the session.
        "web_token": WEB_TOKEN if ui_unlocked else "",
        "ui_unlocked": ui_unlocked,
        # A loopback peer has no session to drop, so it is not offered Lock.
        "ui_unlock_required": _ui_unlock_required(request),
        # A recover-role session has nothing to gain from seeing a Store or
        # Maintenance nav link it cannot reach - showing one anyway would be
        # a dead end that still discloses those surfaces exist.
        "store_role": _ui_session_role(request) == ROLE_STORE,
        "max_upload_bytes": MAX_UPLOAD_BYTES,
        "purge_confirmation_required": purge_confirmation_required(),
        "duress_mode_enabled": duress_mode_enabled(),
        "field_mode": field_mode_enabled(),
        "deployment_mode": active_policy().name,
        "restricted_confirmed": restricted_confirmed,
        "restricted_session_seconds_remaining": (
            _restricted_session_seconds_remaining(request)
            if restricted_confirmed
            else 0
        ),
        "destructive_clear_phrase": DESTRUCTIVE_CLEAR_PHRASE,
        "initialize_container_phrase": INITIALIZE_CONTAINER_PHRASE,
        "emergency_brick_phrase": EMERGENCY_BRICK_PHRASE,
        "restricted_confirmation_phrase": RESTRICTED_CONFIRMATION_PHRASE,
        "overwrite_confirmation_phrase": OVERWRITE_CONFIRMATION_PHRASE,
        "destroy_face_phrase": DESTROY_FACE_PHRASE,
        "entries": [
            {"id": entry_id, "label": label} for entry_id, label in ENTRY_LABELS.items()
        ],
    }
    context.update(extra)
    return context


def _deceptive_path(original_path: str):
    """Provides a cover-story path when field mode is enabled."""
    if field_mode_enabled() and original_path:
        return "/usr/lib/firmware/updates/recovery_blob.bin"
    return original_path


def _raw_gate_status():
    return access_cue_service.status()


def neutral_status():
    raw = _raw_gate_status()
    matched_mode = raw.get("matched_mode")
    camera_ready = bool(raw.get("camera_ready"))
    camera_backend = raw.get("camera_backend", "unknown")
    if camera_ready and camera_backend in {"none", "unavailable", "unknown"}:
        camera_backend = "stream"

    if matched_mode == access_cue_service.match_ambiguous():
        object_state = "ambiguous"
    elif matched_mode in access_cue_service.auth_tokens():
        object_state = "matched"
    elif raw.get("object_detected"):
        object_state = "detected"
    else:
        object_state = "none"

    return {
        "camera_ready": camera_ready,
        "camera_backend": camera_backend,
        "last_camera_error": raw.get("last_camera_error"),
        "backend_warnings": raw.get("camera_backend_warnings", []),
        "stream_resolution": raw.get("stream_resolution", {"width": 0, "height": 0}),
        "fps_target": raw.get("fps_target", 0),
        "object_state": object_state,
        "device_state": "ready",
        "local_mode": True,
    }


def entry_management_status():
    raw = _raw_gate_status()
    registered = raw.get("registered_modes", {})
    current_entry = mode_to_entry(raw.get("matched_mode"))
    return {
        "entries": [
            {
                "id": entry_id,
                "label": label,
                "bound": bool(registered.get(ENTRY_TO_MODE[entry_id])),
                "matched": entry_id == current_entry,
            }
            for entry_id, label in ENTRY_LABELS.items()
        ],
        "object_state": neutral_status()["object_state"],
    }


def _first_unbound_entry():
    registered = _raw_gate_status().get("registered_modes", {})
    for entry_id, mode in ENTRY_TO_MODE.items():
        if not registered.get(mode):
            return entry_id
    return None


def _matched_entry():
    matched_mode = _raw_gate_status().get("matched_mode")
    if matched_mode in access_cue_service.auth_tokens():
        return mode_to_entry(matched_mode)
    return None


def _entry_needs_its_object_presented(entry_hint) -> bool:
    """Whether the chosen entry was refused only because its object is not in view.

    `_select_entry_for_store` returns nothing for two very different reasons,
    and conflating them sent an operator toward the replacement panel - a
    destructive path - when all they had to do was hold their object up again.
    With a valid hint there is only one way to reach None: the entry exists and
    is bound, and the camera is not currently matching it.

    This surfaced the moment the cue started requiring the object. While the
    reference template was the whole frame, the background satisfied the live
    match on its own, so this branch was effectively unreachable.
    """
    if entry_hint not in ENTRY_TO_MODE:
        return False
    mode = ENTRY_TO_MODE[entry_hint]
    return bool(_raw_gate_status().get("registered_modes", {}).get(mode))


def _select_entry_for_store(entry_hint=None, overwrite=False):
    """Resolve which entry a store operation targets.

    An explicit, valid ``entry_hint`` takes priority - the store page's
    visible entry selector lets an operator deliberately set up Entry 1 and
    Entry 2 in turn, rather than depending on whichever entry the camera
    happens to match or the dict-iteration order of the first unbound one.
    The object cue itself is still what actually authorizes the write: an
    already-bound entry is only reused when the camera currently matches it
    (or, for a deliberate replacement, when ``overwrite`` is set), so picking
    an entry from a menu can target a slot but can never substitute for
    presenting its object.
    """
    if entry_hint in ENTRY_TO_MODE:
        mode = ENTRY_TO_MODE[entry_hint]
        if not _raw_gate_status().get("registered_modes", {}).get(mode):
            return entry_hint, True
        if overwrite:
            return entry_hint, True
        if _matched_entry() == entry_hint:
            return entry_hint, False
        return None, False

    matched_entry = _matched_entry()
    if matched_entry:
        return matched_entry, False

    free_entry = _first_unbound_entry()
    if free_entry:
        return free_entry, True

    return None, False


# Capture failures an operator has to act on, rather than gate internals to
# mask. The generic message below is the right answer for anything that could
# describe a stored reference; these describe the frame the operator is holding
# up right now, and withholding them just leaves someone pressing a button that
# will never succeed. Reachable on the store page only, which the threat model
# already treats as a safe environment.
_ACTIONABLE_CAPTURE_MESSAGES = frozenset(
    {
        text.AI_GATE_SCENE_NOT_CAPTURED,
        text.AI_GATE_SCENE_CHANGED,
        text.AI_GATE_OBJECT_NOT_DISTINCT,
        text.AI_GATE_OBJECT_IS_THE_SCENE,
        text.AI_GATE_NO_FRAME,
    }
)


def _capture_entry_binding(mode):
    success, message = access_cue_service.capture_reference(mode)
    if not success:
        if message in _ACTIONABLE_CAPTURE_MESSAGES:
            return False, message
        return False, "Object binding failed. Retry capture."
    return True, message


def _image_entry_binding(mode, payload):
    """Bind from an uploaded image, masking gate internals like the camera path.

    Only the decode failure may pass through: it is decided before any
    comparison against stored references, so it reveals nothing about them.
    """
    success, message = access_cue_service.register_reference_from_image_bytes(
        mode, payload
    )
    if not success and message != text.AI_GATE_IMAGE_UNREADABLE:
        return False, "Object binding failed. Retry with a different image."
    return success, message


@app.get("/unlock", response_class=HTMLResponse)
async def unlock_page(request: Request, rejected: bool = False):
    if _ui_unlocked(request):
        return RedirectResponse(url="/", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="unlock.html",
        context=_template_context(
            request,
            active="lock",
            unlock_error=text.UI_ACCESS_TOKEN_REJECTED if rejected else "",
        ),
    )


@app.post("/unlock", response_class=HTMLResponse)
async def unlock_submit(request: Request, token: str = Form(default="")):
    enforce_rate_limit(request)
    attempt_scope = f"unlock:{_client_id(request)}"
    if not _unlock_attempts.check(attempt_scope).allowed:
        return templates.TemplateResponse(
            request=request,
            name="unlock.html",
            context=_template_context(
                request,
                active="lock",
                unlock_error=text.UI_ACCESS_TEMPORARILY_UNAVAILABLE,
            ),
            status_code=429,
        )

    # A role token (issued from the TUI, see access_token_service.py) grants
    # whichever surface its role is scoped to. The legacy shared WEB_TOKEN
    # still works and grants the store role, so a device with no role token
    # issued yet - or an operator not using the newer per-role tokens - is
    # not locked out.
    #
    # Once any role token is in use, WEB_TOKEN stops being able to mint a
    # session on its own. WEB_TOKEN is embedded as the CSRF mutation guard in
    # every unlocked page's HTML - including a recover-role session's -
    # because that is the only thing `require_web_token` has ever checked.
    # If it kept working here too, reading a recover-role session's page
    # source would hand over everything needed to open an independent,
    # full store-role session through this endpoint, defeating the entire
    # reason a narrower role exists. A device that has not adopted role
    # tokens yet has nothing narrower to defeat, so it is unaffected.
    role = access_token_service.verify(token)
    if (
        role is None
        and not access_token_service.issued_roles()
        and secrets.compare_digest(token, WEB_TOKEN)
    ):
        role = ROLE_STORE
    if role is None:
        _unlock_attempts.record_failure(attempt_scope)
        audit_event("ui_unlock_rejected", source="web")
        return RedirectResponse(url="/unlock?rejected=1", status_code=303)

    _unlock_attempts.record_success(attempt_scope)
    session_token = _create_ui_session(_client_id(request), role=role)
    response = RedirectResponse(url="/", status_code=303)
    response.set_cookie(
        UI_SESSION_COOKIE,
        session_token,
        max_age=UI_SESSION_TTL_SECONDS,
        httponly=True,
        samesite="strict",
    )
    audit_event("ui_unlocked", source="web")
    return response


@app.post("/lock")
async def lock_session(request: Request):
    """Drop the current page session without stopping the server."""
    enforce_rate_limit(request)
    _ui_sessions.pop(_ui_session_token(request), None)
    _restricted_sessions.pop(_restricted_session_token(request), None)
    response = RedirectResponse(url="/unlock", status_code=303)
    response.delete_cookie(UI_SESSION_COOKIE)
    response.delete_cookie(RESTRICTED_SESSION_COOKIE)
    audit_event("ui_locked", source="web")
    return response


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    guard = _guard_page(request)
    if guard:
        return guard
    return templates.TemplateResponse(
        request=request,
        name="home.html",
        context=_template_context(request, active="home"),
    )


@app.get("/store", response_class=HTMLResponse)
async def store_page(request: Request):
    guard = _guard_store_page(request)
    if guard:
        return guard
    access_cue_service.start()
    return templates.TemplateResponse(
        request=request,
        name="store.html",
        context=_template_context(request, active="store"),
    )


@app.get("/retrieve", response_class=HTMLResponse)
async def retrieve_page(request: Request):
    guard = _guard_page(request)
    if guard:
        return guard
    access_cue_service.start()
    return templates.TemplateResponse(
        request=request,
        name="retrieve.html",
        context=_template_context(request, active="retrieve"),
    )


@app.get("/maintenance", response_class=HTMLResponse)
async def maintenance_page(request: Request):
    guard = _guard_store_page(request)
    if guard:
        return guard
    restricted_confirmed = _restricted_session_valid(request)
    return templates.TemplateResponse(
        request=request,
        name="maintenance.html",
        context=_template_context(
            request,
            active="maintenance",
            restricted_confirmed=restricted_confirmed,
            audit_enabled="1" if audit_enabled() else "0",
            state_path=(
                state_dir()
                if (not field_mode_enabled() or restricted_confirmed)
                else ""
            ),
        ),
    )


@app.get("/maintenance/entries", response_class=HTMLResponse)
async def entry_management_page(request: Request):
    guard = _guard_store_page(request)
    if guard:
        return guard
    restricted_confirmed = _restricted_session_valid(request)
    return templates.TemplateResponse(
        request=request,
        name="entry_management.html",
        context=_template_context(
            request,
            active="maintenance",
            restricted_confirmed=restricted_confirmed,
        ),
    )


@app.get("/emergency", response_class=HTMLResponse)
async def emergency_page(request: Request):
    guard = _guard_page(request)
    if guard:
        return guard
    restricted_confirmed = _restricted_session_valid(request)
    return templates.TemplateResponse(
        request=request,
        name="emergency.html",
        context=_template_context(
            request, active="emergency", restricted_confirmed=restricted_confirmed
        ),
    )


@app.get("/video_feed", dependencies=[Depends(require_ui_unlock)])
async def video_feed():
    # generate_frames() releases the camera itself once every caller of it
    # has exited - including this one, when the browser disconnects. It must
    # not be released again here: the TUI's own background object-cue
    # matcher is typically another concurrent caller of the same
    # generate_frames(), reading the same shared camera, and an unconditional
    # release on every WebUI disconnect used to tear down the camera out from
    # under it. The matcher's next read then silently produced no frame, so
    # it stopped updating its match state and stayed frozen at whatever it
    # last was - a viewer closing this tab could leave Recover accepting
    # anything, or refusing everything, until the whole console was
    # restarted. See AIGate.generate_frames() / _finish_camera_consumer().
    #
    # start() is a no-op once the background matcher thread is already
    # running; it only matters right after a successful Retrieve released
    # the camera to save power (see the `/retrieve` handler) and no TUI
    # Vessel Open has happened since to bring it back.
    access_cue_service.start()
    return StreamingResponse(
        access_cue_service.generate_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/status", dependencies=[Depends(require_ui_unlock)])
async def status(request: Request):
    return neutral_status()


@app.get(
    "/maintenance/entry_status",
    dependencies=[
        Depends(require_web_token),
        Depends(require_ui_unlock),
        Depends(require_store_role),
        Depends(require_restricted_confirmation),
    ],
)
async def entry_status(request: Request, entry_id: str = "entry_1"):
    enforce_rate_limit(request)
    require_capability(Capability.ENTRY_MAINTENANCE)
    if entry_id not in ENTRY_TO_MODE:
        return {"error": "Unknown local entry."}
    status_data = entry_management_status()
    selected = next(item for item in status_data["entries"] if item["id"] == entry_id)
    return {
        "label": selected["label"],
        "bound": selected["bound"],
        "matched": selected["matched"],
    }


@app.post(
    "/restricted/confirm",
    dependencies=[Depends(require_web_token), Depends(require_ui_unlock)],
)
async def restricted_confirm(request: Request, confirmation: str = Form(...)):
    enforce_rate_limit(request)
    if confirmation != RESTRICTED_CONFIRMATION_PHRASE:
        return {"error": text.CONFIRMATION_REJECTED_DISPLAY}
    token = _create_restricted_session(_client_id(request))
    response = JSONResponse(
        {
            "status": text.RESTRICTED_CONFIRMATION_ACCEPTED,
            "expires_in": RESTRICTED_SESSION_TTL_SECONDS,
        }
    )
    response.set_cookie(
        RESTRICTED_SESSION_COOKIE,
        token,
        max_age=RESTRICTED_SESSION_TTL_SECONDS,
        httponly=True,
        samesite="strict",
    )
    audit_event("restricted_confirmation_accepted", source="web")
    return response


@app.post(
    "/register_scene",
    dependencies=[
        Depends(require_web_token),
        Depends(require_ui_unlock),
        Depends(require_store_role),
    ],
)
async def register_scene(request: Request):
    """Record the empty scene, with the object out of frame.

    Binding an object needs to know what the view looks like without it: ORB
    describes whatever texture is in the frame, so a reference taken straight
    from a tripod is mostly the wall behind the object and matches that wall
    with the object taken away. Held in memory and consumed by the next
    `/register_key`, never persisted.
    """
    enforce_rate_limit(request)
    # No-op when already running; the scene shot is often the first thing an
    # operator does after opening the page, before any frame has been served.
    access_cue_service.start()
    success, message = access_cue_service.capture_scene()
    if not success:
        return {"error": message}
    audit_event("access_scene_captured", entry="local_entry", source="web")
    return {"status": message}


@app.post(
    "/register_key",
    dependencies=[
        Depends(require_web_token),
        Depends(require_ui_unlock),
        Depends(require_store_role),
    ],
)
async def register_key(
    request: Request,
    entry_hint: str = Form(default=""),
    replace: bool = Form(False),
    reference_image: UploadFile | None = File(default=None),
):
    enforce_rate_limit(request)
    if replace and not _restricted_session_valid(request):
        return {"error": text.RESTRICTED_CONFIRMATION_REQUIRED_UI}
    entry_id = (
        entry_hint
        if entry_hint in ENTRY_TO_MODE
        else _matched_entry() or _first_unbound_entry()
    )
    if entry_id is None:
        return {
            "error": text.NO_OPEN_LOCAL_ENTRY,
            "overwrite_required": True,
            "entries": list(ENTRY_LABELS.values()),
        }

    mode = resolve_entry(entry_id)
    if (
        entry_hint in ENTRY_TO_MODE
        and not replace
        and _raw_gate_status()["registered_modes"].get(mode)
    ):
        return {"error": text.ENTRY_ALREADY_BOUND}

    if reference_image is not None and reference_image.filename:
        payload = await read_limited_upload(reference_image)
        success, message = _image_entry_binding(mode, payload)
        binding_source = "image_file"
    else:
        success, message = _capture_entry_binding(mode)
        binding_source = "camera"
    if success:
        audit_event(
            "image_key_registered",
            entry="local_entry",
            source="web",
            binding_source=binding_source,
        )
        return {
            "status": text.OBJECT_BOUND_TO_ENTRY,
            "entry_state": "updated" if replace else "created",
        }
    return {"error": message}


@app.post(
    "/store",
    dependencies=[
        Depends(require_web_token),
        Depends(require_ui_unlock),
        Depends(require_store_role),
    ],
)
async def store(
    request: Request,
    file: UploadFile = File(...),
    password: str = Form(...),
    secondary_passphrase: str = Form(default=""),
    restricted_recovery_password: str = Form(default=""),
    local_note_label: str = Form(default=""),
    entry_hint: str = Form(default=""),
    overwrite: bool = Form(False),
    overwrite_confirmation: str = Form(default=""),
):
    enforce_rate_limit(request)
    data = await read_limited_upload(file)
    orig_filename = file.filename

    try:
        if not password:
            return {"error": text.ACCESS_PASSWORD_REQUIRED}
        effective_secondary_passphrase = (
            secondary_passphrase or restricted_recovery_password
        )
        passphrase_check = check_store_passphrases(
            password,
            effective_secondary_passphrase,
        )
        if not passphrase_check.ok:
            return {"error": passphrase_check.message}
        if overwrite and overwrite_confirmation != OVERWRITE_CONFIRMATION_PHRASE:
            return {"error": text.REPLACEMENT_CONFIRMATION_REQUIRED}
        if overwrite and not _restricted_session_valid(request):
            return {"error": text.RESTRICTED_CONFIRMATION_REQUIRED_UI}

        entry_id, needs_capture = _select_entry_for_store(
            entry_hint=entry_hint, overwrite=overwrite
        )
        if entry_id is None:
            if _entry_needs_its_object_presented(entry_hint):
                # Deliberately no `overwrite_required`: nothing is in the way,
                # so offering to replace an entry here would invite an operator
                # to destroy the very thing they are trying to add to.
                return {"error": text.ENTRY_OBJECT_NOT_PRESENT}
            return {
                "error": text.NO_OPEN_LOCAL_ENTRY_WITH_REPLACEMENT,
                "overwrite_required": True,
                "entries": [
                    {"id": item_id, "label": label}
                    for item_id, label in ENTRY_LABELS.items()
                ],
            }

        mode = resolve_entry(entry_id)
        if needs_capture or overwrite:
            success, message = _capture_entry_binding(mode)
            if not success:
                return {"error": message}

        vessel_path = resolve_web_vessel()
        if vessel_path is not None:
            # Same entry point the TUI uses, so the file lands in the Vessel's
            # face namespace and shows up in Audit and VESSEL STATUS. Writing
            # through PhasmidVault directly would overwrite that namespace and
            # destroy whatever the face already held.
            VesselWorkflowService().add_payload(
                vessel_path,
                orig_filename or "protected-entry.bin",
                data,
                password,
                restricted_passphrase=effective_secondary_passphrase or None,
                selector=face_for_mode(mode),
                cue_sequence=access_cue_service.sequence_for_mode(mode),
            )
        else:
            vault.store(
                password,
                data,
                access_cue_service.sequence_for_mode(mode),
                filename=orig_filename,
                mode=mode,
                restricted_recovery_password=effective_secondary_passphrase or None,
            )
        audit_event(
            "payload_stored",
            entry="local_entry",
            filename=orig_filename,
            bytes=len(data),
            label_present=bool(local_note_label),
            source="web",
        )
        entry_state = (
            "replaced" if overwrite else "created" if needs_capture else "updated"
        )
        return {
            "success": True,
            "message": text.PROTECTED_ENTRY_SAVED,
            "entry_state": entry_state,
        }
    except (ValueError, FileNotFoundError, PermissionError, RuntimeError):
        # Expected: rejected passphrase, unknown selector, missing container,
        # limiter, or the camera not being ready. Not worth a traceback, and
        # those messages carry the container path.
        return {"error": text.STORE_OPERATION_FAILED}
    except Exception:
        # Anything else is a fault. The operator is still told nothing
        # specific, but swallowing it entirely left whoever has to debug the
        # device with no signal at all.
        LOG.exception("Store failed")
        return {"error": text.STORE_OPERATION_FAILED}


@app.post(
    "/metadata/check",
    dependencies=[
        Depends(require_web_token),
        Depends(require_ui_unlock),
        Depends(require_store_role),
    ],
)
async def metadata_check(request: Request, file: UploadFile = File(...)):
    enforce_rate_limit(request)
    require_capability(Capability.METADATA_CHECK)
    data = await read_limited_upload(file)
    return metadata_risk_report(file.filename, data)


@app.post(
    "/metadata/scrub",
    dependencies=[
        Depends(require_web_token),
        Depends(require_ui_unlock),
        Depends(require_store_role),
    ],
)
async def metadata_scrub(request: Request, file: UploadFile = File(...)):
    enforce_rate_limit(request)
    require_capability(Capability.METADATA_REDUCE)
    data = await read_limited_upload(file)
    result = scrub_metadata(file.filename, data)
    if not result["success"]:
        return JSONResponse(
            {"error": result["message"], "limitation": result["limitation"]},
            status_code=422,
        )
    safe_filename = urllib.parse.quote("metadata_reduced_payload.bin")
    return StreamingResponse(
        io.BytesIO(result["data"]),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{safe_filename}",
            "X-Result-Filename": safe_filename,
        },
    )


@app.post(
    "/retrieve", dependencies=[Depends(require_web_token), Depends(require_ui_unlock)]
)
async def retrieve(request: Request, password: str = Form(...)):
    enforce_rate_limit(request)
    attempt_scope = f"web:{_client_id(request)}"
    if not _access_attempts.check(attempt_scope).allowed:
        return {"error": text.ACCESS_TEMPORARILY_UNAVAILABLE}
    _resume_cue_matching()
    auth_sequence = access_cue_service.auth_sequence(length=1)
    if auth_sequence[0] == access_cue_service.match_none():
        _access_attempts.record_failure(attempt_scope)
        return {"error": text.NO_VALID_ENTRY_FOUND}

    vessel_path = resolve_web_vessel()
    result: bytes | None
    for mode in access_cue_service.modes():
        if vessel_path is not None:
            try:
                payload, retrieval = VesselWorkflowService().retrieve_payload(
                    vessel_path,
                    password,
                    selector=face_for_mode(mode),
                    cue_sequence=auth_sequence,
                )
            except (ValueError, FileNotFoundError, PermissionError, RuntimeError):
                # Expected control flow: wrong password, no bound object
                # matched, nothing stored, the limiter refusing, or the camera
                # not being ready - RuntimeError is what the object-binding
                # path raises for an unavailable frame, which is an ordinary
                # state here, not a fault. Try the next mode, exactly as a
                # None result did before.
                continue
            except Exception:
                # Anything else is a fault, not an authentication outcome.
                # Falling through silently would make a broken container or a
                # bad state file look identical to a mistyped password.
                LOG.exception("Vessel-backed retrieval failed unexpectedly")
                continue
            result, filename, password_role = (
                payload,
                retrieval.filename,
                retrieval.password_role,
            )
        else:
            result, filename, password_role = vault.retrieve_with_policy(
                password, auth_sequence, mode=mode
            )
        if result is None:
            continue

        if password_role == PhasmidVault.PURGE_ROLE:
            # The pre-Vessel container stores the same payload under both a
            # read credential and a destroy credential, so this slot decrypts.
            # It must not be handed back: the destroy password ends an entry,
            # it does not open one, and 0.6.0 settled that it ends *this* entry
            # rather than the other. Both halves of the old behaviour - the
            # disclosure and the direction - were the wrong way round.
            _clear_accessed_entry(mode, source="web")
            _access_attempts.record_success(attempt_scope)
            return {"error": text.NO_VALID_ENTRY_FOUND}

        audit_event(
            "payload_retrieved",
            entry="local_entry",
            filename=filename,
            bytes=len(result),
            source="web",
        )
        # Release camera to save power and heat after successful retrieval.
        access_cue_service.close()
        _access_attempts.record_success(attempt_scope)
        purge_applied = _maybe_auto_purge(mode, source="web")
        return create_file_response(
            result,
            filename or "protected-entry.bin",
            purge_applied=purge_applied,
        )

    if _destroyed_by_password(auth_sequence, password, vessel_path):
        # The credential was correct, so this is not a failed attempt: an
        # operator who has just cleared one entry still has to be able to open
        # the one they intend to show, and a lockout here would take that away
        # at the worst possible moment. The response below is nevertheless the
        # same one a mistyped password produces - that is the point of it.
        _access_attempts.record_success(attempt_scope)
        return {"error": text.NO_VALID_ENTRY_FOUND}

    audit_event("retrieve_failed", source="web")
    _access_attempts.record_failure(attempt_scope)
    return {"error": text.NO_VALID_ENTRY_FOUND}


def _destroyed_by_password(auth_sequence, password: str, vessel_path) -> bool:
    """Clear the presented entry when *password* is its destroy password.

    The whole point of this path is that nothing on screen distinguishes it.
    A password that opens an entry opens it; a password that ends it ends it;
    both look identical to whoever is watching, and to whoever is being made to
    type. That is the answer to "they will just make you enter the password" -
    the password they can compel is not the only one there is.

    Deliberately reached only after the ordinary retrieval has already failed,
    so an access password can never be shadowed by this, and scoped to the
    entry whose object is in front of the camera, so one entry's destroy
    password can never reach the other.
    """
    if vessel_path is None:
        return False
    matched_mode = _raw_gate_status().get("matched_mode")
    if matched_mode not in access_cue_service.auth_tokens():
        return False
    # `auth_sequence` carries the match *token*, `matched_mode` the mode it
    # belongs to - two different vocabularies, so they are compared through
    # the mapping rather than against each other.
    expected = access_cue_service.sequence_for_mode(str(matched_mode), length=1)
    if not auth_sequence or list(auth_sequence[:1]) != list(expected):
        return False

    try:
        VesselWorkflowService().destroy_face(
            vessel_path,
            password,
            selector=face_for_mode(str(matched_mode)),
            camera_object=True,
            confirmation=DESTROY_FACE_PHRASE,
        )
    except (ValueError, FileNotFoundError, PermissionError, RuntimeError):
        # Overwhelmingly "that was not the destroy password", which is the
        # ordinary case: this runs on every failed retrieval.
        return False
    except Exception:
        LOG.exception("Password-triggered destruction failed unexpectedly")
        return False

    audit_event(
        "restricted_local_update",
        accessed_entry="local_entry",
        source="web",
        reason="destroy_password",
    )
    return True


@app.post(
    "/destroy_face",
    dependencies=[Depends(require_web_token), Depends(require_ui_unlock)],
)
async def destroy_face(
    request: Request,
    password: str = Form(...),
    confirmation: str = Form(...),
):
    """Clear the entry whose object is presented, using its destroy password.

    Deliberately not role-gated to `store`: a recover-scoped session can
    decrypt and destroy but can never reach Face setup, and destroying under
    duress is exactly what the narrower session is for.

    Which entry is cleared is decided by the object in front of the camera, not
    by a selector - naming the entry in a form field would put "there are two of
    them" on screen at the moment someone is watching. The caller must hold the
    object of the entry they are clearing and know that entry's destroy
    password, which is a different credential from its access password.
    """
    enforce_rate_limit(request)
    attempt_scope = f"web:{_client_id(request)}"
    if not _access_attempts.check(attempt_scope).allowed:
        return {"error": text.ACCESS_TEMPORARILY_UNAVAILABLE}

    _resume_cue_matching()
    auth_sequence = access_cue_service.auth_sequence(length=1)
    matched_mode = _raw_gate_status().get("matched_mode")
    if (
        auth_sequence[0] == access_cue_service.match_none()
        or matched_mode not in access_cue_service.auth_tokens()
    ):
        # Actionable and safe to say: it describes the frame the operator is
        # holding up right now, not anything about what is stored.
        _access_attempts.record_failure(attempt_scope)
        return {"error": text.DESTROY_FACE_NO_OBJECT}

    require_restricted_action("destroy_face", request, confirmation)

    vessel_path = resolve_web_vessel()
    if vessel_path is None:
        return {"error": text.OPERATION_REJECTED}

    try:
        VesselWorkflowService().destroy_face(
            vessel_path,
            password,
            selector=face_for_mode(str(matched_mode)),
            camera_object=True,
            confirmation=DESTROY_FACE_PHRASE,
        )
    except (ValueError, FileNotFoundError, PermissionError, RuntimeError):
        # A wrong destroy password, an entry that was never set up, and an
        # object that stopped matching between the two checks all land here and
        # all read the same. Telling them apart would say which of the two
        # entries the caller just proved they can reach.
        _access_attempts.record_failure(attempt_scope)
        return {"error": text.OPERATION_REJECTED}
    except Exception:
        LOG.exception("Face destruction failed unexpectedly")
        return {"error": text.OPERATION_REJECTED}

    _access_attempts.record_success(attempt_scope)
    audit_event(
        "restricted_local_update",
        accessed_entry="local_entry",
        source="web",
        reason="explicit_destroy",
    )
    return {"status": text.DESTROY_FACE_DONE}


@app.post(
    "/purge_other",
    dependencies=[Depends(require_web_token), Depends(require_ui_unlock)],
)
async def purge_other(
    request: Request,
    accessed_entry: str = Form(default=""),
    legacy_selector: str = Form(default=""),
    confirmation: str = Form(...),
):
    enforce_rate_limit(request)
    require_restricted_action("clear_unmatched_entry", request, confirmation)
    entry_id = _plain_form_value(accessed_entry) or LEGACY_SELECTOR_TO_ENTRY.get(
        _plain_form_value(legacy_selector),
        _plain_form_value(legacy_selector),
    )
    mode = resolve_entry(entry_id)
    active_vault().purge_other_mode(mode)
    forget_face_contents(_other_mode(mode))
    audit_event("restricted_local_update", accessed_entry="local_entry", source="web")
    return {"status": text.UNMATCHED_ENTRY_CLEARED}


@app.post(
    "/emergency/brick",
    dependencies=[Depends(require_web_token), Depends(require_ui_unlock)],
)
async def emergency_brick(request: Request, confirmation: str = Form(...)):
    enforce_rate_limit(request)
    require_restricted_action("clear_local_access_path", request, confirmation)
    active_vault().silent_brick()
    forget_container_contents()
    audit_event("access_path_cleared", source="web")
    return {"status": text.LOCAL_ACCESS_PATH_CLEARED}


@app.post(
    "/emergency/initialize",
    dependencies=[Depends(require_web_token), Depends(require_ui_unlock)],
)
async def emergency_initialize(request: Request, confirmation: str = Form(...)):
    enforce_rate_limit(request)
    require_restricted_action("initialize_container", request, confirmation)
    active_vault().format_container(rotate_access_key=True)
    forget_container_contents()
    success, message = access_cue_service.clear_references()
    if not success:
        return {"error": message}
    audit_event("container_reinitialized", source="web")
    return {"status": text.CONTAINER_INITIALIZED}


@app.post("/emergency/panic", dependencies=[Depends(require_web_token)])
async def web_panic_trigger(request: Request, secret_trigger: str = Form(...)):
    """Hidden endpoint for rapid local state destruction.

    Authorization is the page session plus the mutation token.  The trigger
    phrase is a typo guard, not a credential: it is a public constant in
    `restricted_actions.py`.  A locked caller gets the same 404 as a wrong
    phrase so the route stays concealed.
    """
    enforce_rate_limit(request)
    try:
        if not _ui_unlocked(request):
            raise HTTPException(status_code=423, detail=text.UI_LOCKED)
        require_restricted_action("rapid_local_clear", request, secret_trigger)
    except HTTPException:
        raise HTTPException(status_code=404) from None
    active_vault().silent_brick()
    forget_container_contents()
    audit_event("access_path_cleared", source="web_panic")
    return {"status": text.CRITICAL_STATE_CLEARED}


@app.post(
    "/maintenance/rotate_token",
    dependencies=[
        Depends(require_web_token),
        Depends(require_ui_unlock),
        Depends(require_store_role),
    ],
)
async def rotate_token(request: Request):
    enforce_rate_limit(request)
    require_capability(Capability.TOKEN_ROTATION)
    _require_restricted_when_field_mode(request)
    global WEB_TOKEN
    WEB_TOKEN = secrets.token_urlsafe(32)
    publish_web_token()
    audit_event("web_token_rotated", source="web")
    return {"status": text.SESSION_TOKEN_ROTATED, "web_token": WEB_TOKEN}


@app.post(
    "/maintenance/reset_session",
    dependencies=[
        Depends(require_web_token),
        Depends(require_ui_unlock),
        Depends(require_store_role),
    ],
)
async def reset_session(request: Request):
    enforce_rate_limit(request)
    require_capability(Capability.SESSION_RESET)
    _require_restricted_when_field_mode(request)
    _rate_limit.clear()
    _restricted_sessions.pop(_restricted_session_token(request), None)
    return {"status": text.LOCAL_SESSION_COUNTERS_RESET}


@app.get(
    "/maintenance/diagnostics",
    dependencies=[
        Depends(require_web_token),
        Depends(require_ui_unlock),
        Depends(require_store_role),
    ],
)
async def diagnostics(request: Request):
    enforce_rate_limit(request)
    status_data = neutral_status()
    device_state = (
        "active"
        if status_data["device_state"] == "ready"
        else status_data["device_state"]
    )
    data = {
        "device_state": device_state,
        "camera_ready": status_data["camera_ready"],
        "object_state": status_data["object_state"],
        "local_mode": status_data["local_mode"],
        "restricted_confirmation_active": _restricted_session_valid(request),
    }
    restricted = _restricted_session_valid(request)
    if (not field_mode_enabled() or restricted) and capability_enabled(
        Capability.DIAGNOSTICS_DETAIL
    ):
        binding_status = hardware_binding_status().to_dict()
        data.update(
            {
                "sensor_link": status_data["object_state"] != "none",
                "hardware_binding": binding_status,
                "state_directory": state_dir(),
                "storage_node": _deceptive_path(state_dir()),
                "audit_enabled": audit_enabled(),
                "upload_limit_bytes": MAX_UPLOAD_BYTES,
            }
        )
    return data


@app.get(
    "/maintenance/logs",
    dependencies=[
        Depends(require_web_token),
        Depends(require_ui_unlock),
        Depends(require_store_role),
    ],
)
async def export_logs(request: Request):
    enforce_rate_limit(request)
    require_capability(Capability.AUDIT_EXPORT)
    _require_restricted_when_field_mode(request)
    path = Path(state_dir()) / AUDIT_LOG_NAME
    if not path.exists():
        return JSONResponse({"error": text.NO_LOCAL_EVENT_LOG}, status_code=404)
    data = path.read_bytes()
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/jsonl",
        headers={"Content-Disposition": "attachment; filename=phasmid-events.jsonl"},
    )


def _maybe_auto_purge(accessed_mode, source):
    reason = None
    if duress_mode_enabled() and accessed_mode == access_cue_service.modes()[0]:
        reason = "duress_access"
    elif not purge_confirmation_required():
        reason = "confirmation_disabled"

    if reason is None:
        return False

    active_vault().purge_other_mode(accessed_mode)
    forget_face_contents(_other_mode(accessed_mode))
    audit_event(
        "restricted_local_update",
        accessed_entry="local_entry",
        source=source,
        reason=reason,
    )
    return True


#: How long to let the matcher settle after restarting it. The background
#: thread needs a camera open and a few consecutive frames before it will
#: report a match, so reading the gate the instant after `start()` always says
#: "no object". Short enough that it is not a pause anyone waits through, and
#: paid only when the matcher was found stopped.
CUE_RESTART_SETTLE_SECONDS = 3.0

#: How long to wait for the restarted camera to hand over any frame at all.
CUE_RESTART_FRAME_SECONDS = 1.0


def _resume_cue_matching() -> None:
    """Bring the matcher back if a previous retrieval released the camera.

    A successful retrieval calls `access_cue_service.close()` to save power and
    heat. Everything that then asks "is the bound object present?" is answered
    "no" - not because the object is absent, but because nothing is looking.
    The retrieve page restarts it on its next `/video_feed` request, so whether
    the answer was true depended on whether the browser had reconnected its
    preview yet.

    Costs nothing when the matcher is already running, which is the normal
    case: `start()` is a no-op and this returns immediately.
    """
    if access_cue_service.matching_active:
        return
    access_cue_service.start()
    try:
        service = VesselWorkflowService()
        # Gated on a frame arriving first, so a device with no camera at all
        # answers immediately instead of standing still for the settle time on
        # every single call.
        if not service.wait_for_camera_frame(timeout=CUE_RESTART_FRAME_SECONDS):
            return
        service.wait_for_reference_match(timeout=CUE_RESTART_SETTLE_SECONDS)
    except Exception:
        LOG.exception("Resuming object-cue matching failed")


def _clear_accessed_entry(accessed_mode, source):
    """Clear the entry whose destroy password was just used.

    Named for what it does, because its predecessor did the opposite:
    `_purge_for_password_role` cleared the *other* entry and handed this one's
    contents back. That predates the rule 0.6.0 settled on - a destroy password
    ends the entry it belongs to, and never discloses - and only ever ran on
    the pre-Vessel container, so the two paths disagreed with each other in the
    same endpoint.
    """
    active_vault().purge_mode(accessed_mode)
    forget_face_contents(accessed_mode)
    audit_event(
        "restricted_local_update",
        accessed_entry="local_entry",
        source=source,
        reason="destroy_password",
    )
    return True


def create_file_response(content, filename, purge_applied=False):
    safe_filename = urllib.parse.quote("retrieved_payload.bin")
    return StreamingResponse(
        io.BytesIO(content),
        media_type="application/octet-stream",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{safe_filename}",
            "X-Result-Filename": safe_filename,
        },
    )


# ── Operator Console pages ────────────────────────────────────────────────

_OPERATOR_DEPS = [
    Depends(require_web_token),
    Depends(require_ui_unlock),
    Depends(require_store_role),
]


@app.get("/operator/doctor", response_class=HTMLResponse, dependencies=_OPERATOR_DEPS)
async def operator_doctor(request: Request):
    guard = _guard_page(request)
    if guard:
        return guard
    result = run_doctor_checks()
    checks = [
        {
            "level": c.level.value.lower(),
            "name": c.name,
            "message": c.message,
            "detail": c.detail or "",
        }
        for c in result.checks
    ]
    return templates.TemplateResponse(
        request=request,
        name="operator_doctor.html",
        context=_template_context(request, active="operator-doctor", checks=checks),
    )


@app.get("/operator/audit", response_class=HTMLResponse, dependencies=_OPERATOR_DEPS)
async def operator_audit(request: Request):
    guard = _guard_page(request)
    if guard:
        return guard
    report = build_audit_report()
    sections = [
        {
            "title": s.title,
            "entries": [{"key": e.key, "value": e.value} for e in s.entries],
        }
        for s in report.sections
    ]
    return templates.TemplateResponse(
        request=request,
        name="operator_audit.html",
        context=_template_context(request, active="operator-audit", sections=sections),
    )


@app.get("/operator/guided", response_class=HTMLResponse, dependencies=_OPERATOR_DEPS)
async def operator_guided(request: Request):
    guard = _guard_page(request)
    if guard:
        return guard
    workflows = [
        {
            "id": w.id,
            "title": w.title,
            "description": w.description,
            "steps": [
                {"number": s.number, "text": s.text, "detail": s.detail}
                for s in w.steps
            ],
        }
        for w in get_workflows()
    ]
    return templates.TemplateResponse(
        request=request,
        name="operator_guided.html",
        context=_template_context(
            request, active="operator-guided", workflows=workflows
        ),
    )


@app.get("/operator/inspect", response_class=HTMLResponse, dependencies=_OPERATOR_DEPS)
async def operator_inspect_get(request: Request):
    guard = _guard_page(request)
    if guard:
        return guard
    return templates.TemplateResponse(
        request=request,
        name="operator_inspect.html",
        context=_template_context(request, active="operator-inspect", result=None),
    )


@app.post("/operator/inspect", response_class=HTMLResponse, dependencies=_OPERATOR_DEPS)
async def operator_inspect_post(
    request: Request,
    file: UploadFile = File(...),
):
    guard = _guard_page(request)
    if guard:
        return guard
    import tempfile as _tmpfile

    suffix = "".join(
        c for c in (file.filename or "upload") if c.isalnum() or c in "._-"
    )[-64:]
    with _tmpfile.NamedTemporaryFile(delete=False, suffix="_" + suffix) as tmp:
        tmp.write(await file.read())
        tmp_path = tmp.name
    try:
        inspection = inspect_vessel(tmp_path)
    finally:
        Path(tmp_path).unlink()
    result: dict[str, object] | None = None
    if inspection.error:
        result = {"error": inspection.error, "fields": [], "notes": []}
    else:
        result = {
            "error": None,
            "fields": [
                {"label": f.label, "value": f.value, "note": f.note or ""}
                for f in inspection.fields
            ],
            "notes": inspection.notes,
        }
    return templates.TemplateResponse(
        request=request,
        name="operator_inspect.html",
        context=_template_context(request, active="operator-inspect", result=result),
    )


if __name__ == "__main__":
    host = web_host()
    port = web_port()
    print(f"[WEB] Starting on http://{host}:{port}")
    print("[WEB] Pages require a local access token; open /unlock to enter it.")
    print(f"[WEB] Access token is readable at {web_token_path()} while running.")
    __import__("uvicorn").run(app, host=host, port=port)
