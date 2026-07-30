# Phasmid Configuration Reference

This document is the single source of truth for runtime environment variables.
All `PHASMID_*` reads are centralized in `src/phasmid/config.py`.

## Environment Variables

| Variable | Type | Default | Scope | Behavior | Equivalent Setting |
|---|---|---|---|---|---|
| `PHASMID_STATE_DIR` | path | `.state` | CLI/WebUI/TUI | Base local state directory when tmpfs override is not set | `config.state_dir()` |
| `PHASMID_TMPFS_STATE` | path | unset | CLI/WebUI/TUI | Overrides state directory with volatile path (intended tmpfs). The Vessel registry's sealed Face detail (`vessel_registry.bin`) lives here, so it becomes volatile too — consistent with the object-cue references, which already do | `config.tmpfs_state_dir()` |
| `PHASMID_FIELD_MODE` | bool | `false` | WebUI/TUI/CLI messaging | Reduces capture-visible detail in standard surfaces, including collapsing the TUI's cross-Face file total to `-` | `config.field_mode_enabled()` |
| `PHASMID_EXPERIMENTAL_OBJECT_MODEL` | bool | `false` | Object cue gate | Enables experimental local object-model support layer | `config.experimental_object_model_enabled()` |
| `PHASMID_OBJECT_MODEL_PATH` | path | unset | Object cue gate | Path to explicitly provisioned local model file | `config.object_model_path()` |
| `PHASMID_PURGE_CONFIRMATION` | bool | `true` | Restricted actions | Requires explicit typed confirmation for destructive flow | `config.purge_confirmation_required()` |
| `PHASMID_DURESS_MODE` | bool | `false` | WebUI behavior | Enables restricted-recovery related behavior gates | `config.duress_mode_enabled()` |
| `PHASMID_DUAL_APPROVAL` | bool | `false` | Restricted actions | Enables dual-passphrase approval workflow | `config.dual_approval_enabled()` |
| `PHASMID_MIN_PASSPHRASE_LENGTH` | int (>=1) | `10` | Store/init passphrase policy | Minimum accepted passphrase length | `config.passphrase_min_length()` |
| `PHASMID_ACCESS_MAX_FAILURES` | int (>=1) | `5` | Access limiter | Failure count threshold before lockout | `config.access_max_failures()` |
| `PHASMID_ACCESS_LOCKOUT_SECONDS` | int (>=1) | `60` | Access limiter | Lockout duration after threshold exceeded | `config.access_lockout_seconds()` |
| `PHASMID_WEB_TOKEN` | string | random per process | WebUI access and mutations | Fixed access token if provided; else generated at startup. Presented at `/unlock` by non-loopback peers to open a page session, and sent as `X-Phasmid-Token` on mutations | `config.web_token_env()` |
| `PHASMID_STORE_TOKEN` | string | unset | WebUI role login | Pins the store-role access token to a fixed value for a reproducible demo, instead of one issued from the TUI (which shows the raw value once and never again). While set, the store role cannot be issued or revoked from the TUI's Access Tokens screen | `config.store_token_env()` |
| `PHASMID_RECOVER_TOKEN` | string | unset | WebUI role login | Same as `PHASMID_STORE_TOKEN`, for the recover role | `config.recover_token_env()` |
| `PHASMID_UI_SESSION_SECONDS` | int (>=1) | `1800` | WebUI page session | Lifetime of an unlocked WebUI page session | `config.ui_session_seconds()` |
| `PHASMID_ALLOWED_HOSTS` | comma-separated names | empty | WebUI `Host` validation | Extra `Host` header names accepted beyond address literals and `localhost`; each listed name reopens DNS rebinding for that name | `config.allowed_web_hosts()` |
| `PHASMID_HOST` | host string | `127.0.0.1` | WebUI server | Bind host for WebUI process; overrides gadget exposure when set | `config.web_host()` |
| `PHASMID_WEBUI_EXPOSE_GADGET` | bool | `false` | WebUI server | Binds the USB gadget interface address (`usb0`/`enx*`) instead of loopback; never binds all interfaces | `config.webui_gadget_exposure_enabled()` |
| `PHASMID_PORT` | int (>=1) | `8000` | WebUI server | Bind port for WebUI process | `config.web_port()` |
| `PHASMID_MAX_UPLOAD_BYTES` | int (>=1) | `26214400` | WebUI store/metadata | Upload size ceiling in bytes | `config.max_upload_bytes()` |
| `PHASMID_RESTRICTED_SESSION_SECONDS` | int (>=1) | `120` | WebUI restricted session | Restricted confirmation session TTL | `config.restricted_session_seconds()` |
| `PHASMID_AUDIT` | bool | `false` | Audit logging | Enables optional audit event logging | `config.audit_enabled()` |
| `PHASMID_AUDIT_FILENAMES` | enum (`hash` or unset) | unset | Audit logging | If `hash`, stores filename hash instead of presence-only marker | `config.audit_filename_mode()` |
| `PHASMID_PROFILE` | enum (`standard`, `field`, `maintenance`) | `standard` | Capability policy | Selects capability set and maintenance quietness | `config.profile_name()` |
| `PHASMID_HARDWARE_SECRET_FILE` | path | unset | KDF external factor | Adds file-backed secret material to KDF secret set | `config.hardware_secret_file()` |
| `PHASMID_HARDWARE_SECRET` | string | unset | KDF external factor | Adds env-supplied secret material to KDF secret set | `config.hardware_secret_value()` |
| `PHASMID_HARDWARE_SECRET_PROMPT` | bool-like (`1` enabled) | unset | KDF external factor | Prompts operator for extra key material | `config.hardware_secret_prompt_enabled()` |
| `PHASMID_STATE_SECRET` | string | unset | Local state encryption | Overrides local state key with environment-derived secret | `config.state_secret()` |
| `PHASMID_DEBUG` | bool | `false` | Diagnostics | Enables debug-mode warning in doctor output | `config.debug_enabled()` |
| `PHASMID_DOCTOR_RECENT_SECONDS` | int (>=1) | `86400` | Doctor | Window for “recent vault activity” warning | `config.doctor_recent_seconds()` |
| `PHASMID_DUMMY_MIN_SIZE_MB` | int (>=0) | `50` | Doctor plausibility advisory | Minimum baseline size for local disclosure-face dataset | `config.dummy_min_size_mb()` |
| `PHASMID_DUMMY_MIN_FILE_COUNT` | int (>=0) | `20` | Doctor plausibility advisory | Minimum baseline file count for local disclosure-face dataset | `config.dummy_min_file_count()` |
| `PHASMID_DUMMY_OCCUPANCY_WARN` | float (>=0) | `0.10` | Doctor plausibility advisory | Warn when disclosure-face size ratio falls below threshold | `config.dummy_occupancy_warn()` |
| `PHASMID_DUMMY_PROFILE_DIR` | path | `.state/dummy_profile` | Doctor plausibility advisory | Local path scanned for disclosure-face plausibility baseline | `config.dummy_profile_dir()` |
| `PHASMID_DUMMY_CONTAINER_PATH` | path | `vault.bin` | Doctor plausibility advisory | Local container path used for occupancy ratio baseline | `config.dummy_container_path()` |
| `PHASMID_RECOGNITION_MODE` | enum (`strict`, `coercion_safe`, `demo`) | `strict` | Object cue routing | Selects ambiguity/failure handling policy for object-cue unlock routing | `config.recognition_mode()` |
| `PHASMID_TRUE_UNLOCK_THRESHOLD` | float (`0.0`-`1.0`) | `0.85` | Object cue routing | Confidence threshold for direct unlock path | `config.true_unlock_threshold()` |
| `PHASMID_DUMMY_FALLBACK_THRESHOLD` | float (`0.0`-`1.0`) | `0.40` | Object cue routing | Confidence floor used by demo fallback routing policy | `config.dummy_fallback_threshold()` |
| `PHASMID_ENABLE_DISPLAY` | bool | `false` | Bridge UI simulator | Enables OpenCV preview window for display simulator | `config.display_enabled()` |
| `PHASMID_DARK` | bool | `false` | TUI theming | Optional dark theme selection flag | `config.tui_dark_enabled()` |
| `PHASMID_LIGHT` | bool | `false` | TUI theming | Optional light theme selection flag | `config.tui_light_enabled()` |
