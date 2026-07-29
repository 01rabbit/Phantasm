"""Neutral user-visible wording shared by local interfaces."""

OPERATION_UNAVAILABLE = "operation unavailable"
OPERATION_REJECTED = "operation rejected"
RESTRICTED_CONFIRMATION_REQUIRED = "restricted confirmation required"
CONFIRMATION_REJECTED = "confirmation rejected"
UI_LOCKED = "ui locked"
INVALID_WEB_TOKEN = "invalid web token"
RATE_LIMIT_EXCEEDED = "rate limit exceeded"
UPLOAD_TOO_LARGE = "upload too large"
ACCESS_TEMPORARILY_UNAVAILABLE = "Access temporarily unavailable."

CONFIRMATION_REJECTED_DISPLAY = "Confirmation rejected."
RESTRICTED_CONFIRMATION_ACCEPTED = "Restricted confirmation accepted."
RESTRICTED_CONFIRMATION_RETRY = (
    "Restricted confirmation required. Please confirm local control and retry."
)

NO_OPEN_LOCAL_ENTRY = "No open local entry is available."
NO_OPEN_LOCAL_ENTRY_WITH_REPLACEMENT = (
    "No open local entry is available. Confirm replacement to continue."
)
ENTRY_ALREADY_BOUND = "Entry already has a bound object. Confirm replacement first."
ACCESS_PASSWORD_REQUIRED = "Access password must not be empty."
PASSWORDS_MUST_DIFFER = "Access and restricted recovery passwords must be different."
REPLACEMENT_CONFIRMATION_REQUIRED = "Replacement confirmation required."
STORE_OPERATION_FAILED = "Store operation failed."

OBJECT_BOUND_TO_ENTRY = "Object bound to protected entry."
PROTECTED_ENTRY_SAVED = "Protected entry saved."
AMBIGUOUS_OBJECT_MATCH = "Ambiguous object match."
NO_VALID_ENTRY_FOUND = "No valid entry found."

UNMATCHED_ENTRY_CLEARED = "Unmatched local entry cleared."
LOCAL_ACCESS_PATH_CLEARED = "Local access path cleared. Close this session."
CONTAINER_INITIALIZED = "Local container initialized. Protected entries are empty."
CRITICAL_STATE_CLEARED = "Critical state cleared."

# UI Status and Feedback
UI_UNLOCKED = "UI unlocked."
UI_LOCKED_FEEDBACK = "UI locked."
UI_ACCESS_TOKEN_REQUIRED = "Enter the local access token to continue."
UI_ACCESS_TOKEN_REJECTED = "Access token rejected."
UI_ACCESS_TEMPORARILY_UNAVAILABLE = "Local interface temporarily unavailable."
UI_FACE_LOCK_DISABLED = "Face UI lock is disabled."
UI_FACE_ENROLLMENT_DISABLED = "Face enrollment is disabled for this session."
RESTRICTED_CONFIRMATION_REQUIRED_UI = (
    "Restricted confirmation required. Please confirm local control and retry."
)
NO_LOCAL_EVENT_LOG = "No local event log is available."
SESSION_TOKEN_ROTATED = "Session token rotated."
LOCAL_SESSION_COUNTERS_RESET = "Local session counters reset."

# CLI Feedback
CLI_OBJECT_BOUND = "Object access cue registered."
CLI_OBJECT_MATCHED = "[LOCAL] Bound object matched."
CLI_AMBIGUOUS_MATCH = "[LOCAL] Ambiguous object match detected."
CLI_NO_MATCH_TIMEOUT = "[LOCAL] No bound object match detected within timeout."
CLI_ERROR_NO_INPUT = "[!] Error: No input file specified."
CLI_ERROR_OUTPUT_REQUIRED = "[!] Error: Output path required."
CLI_ERROR_CAMERA_UNAVAILABLE = "[!] Error: Camera feed did not become available."
CLI_INIT_SUCCESS = "[+] Local container initialized. Ready for protected entries."

# AI Gate Neutral Wording
AI_GATE_ACTIVE = "PHANTASM: ACTIVE"
AI_GATE_MATCH = "MATCH"
AI_GATE_AMBIGUOUS = "AMBIG"
AI_GATE_OBJECT_MATCHED = "Object cue matched"
AI_GATE_OBJECT_DETECTED = "Bound object detected in frame"
AI_GATE_AMBIGUOUS_CUE = "Ambiguous object cue"
AI_GATE_CUES_TOO_SIMILAR = "Access cues are too similar"
AI_GATE_NO_MATCH = "No object cue match"
AI_GATE_PRESENT_OBJECT = "Present a bound object to continue"
AI_GATE_IMAGE_TOO_SIMPLE = "Image too simple. Use a textured object."
AI_GATE_IMAGE_UNREADABLE = "Image file could not be read. Use a standard image format."
AI_GATE_NO_FRAME = "No frame."
AI_GATE_SAVE_FAILED = "Failed to save reference template."
AI_GATE_CLEAR_FAILED = "Failed to clear object bindings."
AI_GATE_CUES_CLEARED = "Object bindings cleared."

# Dual-approval flow (neutral wording)
DUAL_APPROVAL_NOT_ENABLED = "Dual authorization is not enabled for this action."
DUAL_APPROVAL_SUPERVISOR_NOT_CONFIGURED = "Supervisor passphrase is not configured."
DUAL_APPROVAL_REQUEST_CREATED = (
    "Authorization request created. Supervisor must authorize within the time limit."
)
DUAL_APPROVAL_REQUEST_NOT_FOUND = (
    "No pending authorization request found for this action."
)
DUAL_APPROVAL_REQUEST_EXPIRED = "Authorization request has expired. Request again."
DUAL_APPROVAL_GRANT_EXPIRED = "Authorization has expired. Request again."
DUAL_APPROVAL_WRONG_PASSPHRASE = "Authorization rejected: passphrase did not match."
DUAL_APPROVAL_GRANTED = "Authorization accepted."
DUAL_APPROVAL_CONSUMED = "Authorization used. Action may proceed."
DUAL_APPROVAL_ALREADY_PENDING = (
    "An authorization request is already pending for this action."
)
DUAL_APPROVAL_SUPERVISOR_SET = "Supervisor passphrase configured."
DUAL_APPROVAL_SUPERVISOR_CLEARED = "Supervisor passphrase cleared."
DUAL_APPROVAL_SUPERVISOR_CLEAR_FAILED = "Failed to clear supervisor passphrase."
