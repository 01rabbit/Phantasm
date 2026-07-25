import io
import logging
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
    audit_enabled,
    duress_mode_enabled,
    field_mode_enabled,
    max_upload_bytes,
    purge_confirmation_required,
    restricted_session_seconds,
    state_dir,
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
from .services.audit_service import build_audit_report
from .services.doctor_service import run_doctor_checks
from .services.guided_service import get_workflows
from .services.inspection_service import inspect_vessel
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


@app.on_event("shutdown")
async def shutdown_cleanup():
    try:
        access_cue_service.close()
    except Exception as exc:
        LOG.error("Camera cleanup on shutdown failed: %s", exc)


templates = Jinja2Templates(directory=str(Path(__file__).with_name("templates")))
vault = PhasmidVault("vault.bin")
WEB_TOKEN = web_token_env() or secrets.token_urlsafe(32)
MAX_UPLOAD_BYTES = max_upload_bytes()
RATE_LIMIT_WINDOW = 60
RATE_LIMIT_MAX = 20
RESTRICTED_SESSION_COOKIE = "phasmid_restricted_session"
RESTRICTED_SESSION_TTL_SECONDS = restricted_session_seconds()
_restricted_sessions = {}
_access_attempts = AttemptLimiter()

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


@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    response = await call_next(request)
    return _apply_security_headers(response)


def display_entry_label(entry_id):
    return ENTRY_LABELS.get(entry_id, "Entry")


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


def _ui_unlocked(request):
    return True


def require_ui_unlock(request: Request):
    if not _ui_unlocked(request):
        raise HTTPException(status_code=423, detail=text.UI_LOCKED)


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
    return RedirectResponse(url="/", status_code=303)


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
    context = {
        "request": request,
        "active": active,
        "web_token": WEB_TOKEN,
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


def _select_entry_for_store(entry_hint=None, overwrite=False):
    matched_entry = _matched_entry()
    if matched_entry:
        return matched_entry, False

    free_entry = _first_unbound_entry()
    if free_entry:
        return free_entry, True

    if overwrite and entry_hint in ENTRY_TO_MODE:
        return entry_hint, True

    return None, False


def _capture_entry_binding(mode):
    success, message = access_cue_service.capture_reference(mode)
    if not success:
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
    guard = _guard_page(request)
    if guard:
        return guard
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
    return templates.TemplateResponse(
        request=request,
        name="retrieve.html",
        context=_template_context(request, active="retrieve"),
    )


@app.get("/maintenance", response_class=HTMLResponse)
async def maintenance_page(request: Request):
    guard = _guard_page(request)
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
    guard = _guard_page(request)
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
    def stream():
        try:
            yield from access_cue_service.generate_frames()
        finally:
            try:
                access_cue_service.release_camera()
            except Exception as exc:
                LOG.error("Camera cleanup after stream disconnect failed: %s", exc)

    return StreamingResponse(
        stream(),
        media_type="multipart/x-mixed-replace; boundary=frame",
    )


@app.get("/status")
async def status(request: Request):
    return neutral_status()


@app.get(
    "/maintenance/entry_status",
    dependencies=[
        Depends(require_web_token),
        Depends(require_ui_unlock),
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
    "/register_key",
    dependencies=[Depends(require_web_token), Depends(require_ui_unlock)],
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
    "/store", dependencies=[Depends(require_web_token), Depends(require_ui_unlock)]
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
    except Exception:
        return {"error": text.STORE_OPERATION_FAILED}


@app.post(
    "/metadata/check",
    dependencies=[Depends(require_web_token), Depends(require_ui_unlock)],
)
async def metadata_check(request: Request, file: UploadFile = File(...)):
    enforce_rate_limit(request)
    require_capability(Capability.METADATA_CHECK)
    data = await read_limited_upload(file)
    return metadata_risk_report(file.filename, data)


@app.post(
    "/metadata/scrub",
    dependencies=[Depends(require_web_token), Depends(require_ui_unlock)],
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
    auth_sequence = access_cue_service.auth_sequence(length=1)
    if auth_sequence[0] == access_cue_service.match_none():
        _access_attempts.record_failure(attempt_scope)
        return {"error": text.NO_VALID_ENTRY_FOUND}

    for mode in access_cue_service.modes():
        result, filename, password_role = vault.retrieve_with_policy(
            password, auth_sequence, mode=mode
        )
        if result is None:
            continue

        audit_event(
            "payload_retrieved",
            entry="local_entry",
            filename=filename,
            bytes=len(result),
            source="web",
        )
        purge_applied = _purge_for_password_role(mode, password_role, source="web")
        if result is not None:
            # Release camera to save power and heat after successful retrieval
            access_cue_service.close()
        _access_attempts.record_success(attempt_scope)
        if not purge_applied:
            purge_applied = _maybe_auto_purge(mode, source="web")
        return create_file_response(
            result,
            filename or "protected-entry.bin",
            purge_applied=purge_applied,
        )

    audit_event("retrieve_failed", source="web")
    _access_attempts.record_failure(attempt_scope)
    return {"error": text.NO_VALID_ENTRY_FOUND}


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
    vault.purge_other_mode(mode)
    audit_event("restricted_local_update", accessed_entry="local_entry", source="web")
    return {"status": text.UNMATCHED_ENTRY_CLEARED}


@app.post(
    "/emergency/brick",
    dependencies=[Depends(require_web_token), Depends(require_ui_unlock)],
)
async def emergency_brick(request: Request, confirmation: str = Form(...)):
    enforce_rate_limit(request)
    require_restricted_action("clear_local_access_path", request, confirmation)
    vault.silent_brick()
    audit_event("access_path_cleared", source="web")
    return {"status": text.LOCAL_ACCESS_PATH_CLEARED}


@app.post(
    "/emergency/initialize",
    dependencies=[Depends(require_web_token), Depends(require_ui_unlock)],
)
async def emergency_initialize(request: Request, confirmation: str = Form(...)):
    enforce_rate_limit(request)
    require_restricted_action("initialize_container", request, confirmation)
    vault.format_container(rotate_access_key=True)
    success, message = access_cue_service.clear_references()
    if not success:
        return {"error": message}
    audit_event("container_reinitialized", source="web")
    return {"status": text.CONTAINER_INITIALIZED}


@app.post("/emergency/panic", dependencies=[Depends(require_web_token)])
async def web_panic_trigger(request: Request, secret_trigger: str = Form(...)):
    """Hidden endpoint for rapid local state destruction."""
    enforce_rate_limit(request)
    try:
        require_restricted_action("rapid_local_clear", request, secret_trigger)
    except HTTPException:
        raise HTTPException(status_code=404) from None
    vault.silent_brick()
    audit_event("access_path_cleared", source="web_panic")
    return {"status": text.CRITICAL_STATE_CLEARED}


@app.post(
    "/maintenance/rotate_token",
    dependencies=[Depends(require_web_token), Depends(require_ui_unlock)],
)
async def rotate_token(request: Request):
    enforce_rate_limit(request)
    require_capability(Capability.TOKEN_ROTATION)
    _require_restricted_when_field_mode(request)
    global WEB_TOKEN
    WEB_TOKEN = secrets.token_urlsafe(32)
    audit_event("web_token_rotated", source="web")
    return {"status": text.SESSION_TOKEN_ROTATED, "web_token": WEB_TOKEN}


@app.post(
    "/maintenance/reset_session",
    dependencies=[Depends(require_web_token), Depends(require_ui_unlock)],
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
    dependencies=[Depends(require_web_token), Depends(require_ui_unlock)],
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
    dependencies=[Depends(require_web_token), Depends(require_ui_unlock)],
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

    vault.purge_other_mode(accessed_mode)
    audit_event(
        "restricted_local_update",
        accessed_entry="local_entry",
        source=source,
        reason=reason,
    )
    return True


def _purge_for_password_role(accessed_mode, password_role, source):
    if password_role != PhasmidVault.PURGE_ROLE:
        return False
    vault.purge_other_mode(accessed_mode)
    audit_event(
        "restricted_local_update",
        accessed_entry="local_entry",
        source=source,
        reason="restricted_recovery",
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

_OPERATOR_DEPS = [Depends(require_web_token), Depends(require_ui_unlock)]


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
    print("[WEB] Mutating requests require X-Phasmid-Token from the served UI.")
    __import__("uvicorn").run(app, host=host, port=port)
