# Phasmid Specification

## 1. Overview

Phasmid is a field-evaluation prototype for local-only coercion-aware storage. It stores encrypted payloads in `vault.bin` and requires a password plus a camera-recognized physical object cue before recovery.

The project is intended for USB gadget mode or localhost access. It is not a replacement for full-disk encryption, hardware-backed key storage, audited classified-data handling, or a complete solution to compelled disclosure.

## 2. Features

- Initialize an encrypted container.
- Store protected entries in an internal two-slot container model.
- Register and verify camera-based physical object cues.
- Encrypt and retrieve payloads.
- Support normal access and restricted recovery behavior.
- Clear local state through restricted owner-controlled actions.
- Operate from a CLI or local WebUI v2.
- Optionally write a minimal audit log.

## 3. Repository Layout

| Path | Purpose |
| --- | --- |
| `main.py` | Local CLI launcher |
| `src/phasmid/cli.py` | CLI implementation |
| `src/phasmid/vault_core.py` | Encrypted container logic |
| `src/phasmid/ai_gate.py` | Camera input and object-cue orchestration |
| `src/phasmid/camera_frame_source.py` | OpenCV camera capture lifecycle |
| `src/phasmid/object_cue_matcher.py` | ORB-based object-cue matching logic |
| `src/phasmid/object_cue_store.py` | Encrypted object-cue reference persistence |
| `src/phasmid/face_sample_matcher.py` | Face sample extraction and template comparison |
| `src/phasmid/local_state_crypto.py` | Shared AES-GCM helper for local state blobs and templates |
| `src/phasmid/web_server.py` | FastAPI Web UI/API |
| `src/phasmid/bridge_ui.py` | OpenCV status UI |
| `src/phasmid/emergency_daemon.py` | Panic trigger watcher and local access-path clear flow |
| `src/phasmid/audit.py` | Optional audit log |
| `src/phasmid/config.py` | Shared state names and runtime policy |
| `src/phasmid/templates/` | WebUI v2 server-rendered templates |
| `scripts/bench_kdf.py` | Argon2id benchmark helper |
| `docs/THREAT_MODEL.md` | Threat model |
| `tests/` | Unit tests |

## 4. Runtime Files

| Path | Purpose |
| --- | --- |
| `vault.bin` | Encrypted container |
| `.state/store.bin` | Encrypted object-cue state blob |
| `.state/lock.bin` | Local key for object-cue state encryption |
| `.state/access.bin` | Local access key required to recover `vault.bin` |
| `.state/signal.key` | Panic trigger token |
| `.state/signal.trigger` | Panic trigger file |
| `.state/events.log` | Optional audit log |
| `.state/events.auth` | Optional audit verifier material |
| `.state/face.enroll` | Short-lived first-time face enrollment request |

The default state directory is `.state/` and can be changed with `PHASMID_STATE_DIR`. The directory is intended to be mode `0700`; sensitive files are intended to be mode `0600`. Neutral filenames reduce obvious metadata, but they do not provide deniability.

New local state code paths should use the typed state store for schema-versioned records, atomic writes, restrictive file permissions, and explicit transition checks. Existing binary state files remain managed by their owning modules until a migration path is defined.

## 4.1 Cryptographic Boundary

Phasmid defines a local cryptographic primitive boundary in `src/phasmid/crypto_boundary.py`. Startup checks cover AES-GCM round trip behavior, HMAC-SHA-256 behavior, and random byte generation health. Failure causes local startup to stop with a neutral message in the CLI path.

This boundary improves reviewability and failure detection. It is not a FIPS validation, certification claim, or replacement for independent cryptographic review.

## 5. Internal Entry Model

The container uses two fixed internal storage spans. The CLI keeps a compact `--entry a` / `--entry b` selector, while WebUI v2 maps the internal model to neutral protected-entry workflows and does not expose internal labels during normal operation.

## 6. CLI

### Initialize

```bash
phasmid init
phasmid create /path/to/travel.vessel --no-tui --size 512M
```

`phasmid init` rotates the local access key, overwrites `vault.bin` with random
data, and leaves an empty container ready for new entries.

`phasmid create <vessel> --no-tui` initializes a Vessel file directly without
opening the TUI. The command creates the Vessel path, formats the container
with random data, rotates the local access key, and registers the Vessel for
the operator console.

### Store

```bash
phasmid store /path/to/travel.vessel --entry a --input path/to/file
phasmid store /path/to/travel.vessel --entry b --input path/to/file
```

Store flow:

1. Start the camera gate.
2. Prompt for normal access and restricted recovery passwords, or read them
   from local passphrase files when `--passphrase-file` and
   `--restricted-passphrase-file` are provided.
3. Reject empty, duplicate, short, or highly repetitive passphrases.
4. Register the physical object cue for the selected internal entry.
5. Read the input file.
6. Derive a key with Argon2id.
7. Encrypt the payload with AES-GCM.

### Retrieve

```bash
phasmid retrieve /path/to/travel.vessel --out output.bin
```

Retrieve flow:

1. Start the camera gate.
2. Prompt for the access password, or read it from a local passphrase file
   when `--passphrase-file` is provided.
3. Verify the registered physical object cue.
4. Attempt recovery against internal candidates.
5. Write or display the recovered payload if access succeeds.
6. Apply restricted recovery behavior only when the password or configured policy requires it.

These settings and passwords can cause data loss:

- `PHASMID_PURGE_CONFIRMATION=0`
- `PHASMID_DURESS_MODE=1`
- restricted recovery passwords

### Open / Close

```bash
phasmid open /path/to/travel.vessel --no-tui --face face_a
phasmid close /path/to/travel.vessel
phasmid face create /path/to/travel.vessel --face face_b --label travel
```

Open and close update only local, non-sensitive Vessel metadata used by the
operator console. This metadata may include whether the Vessel is currently
open, the number of times it has been opened, and the most recent open/close
timestamps. It does not include passphrases, plaintext content, or object-cue
material.

Each Vessel keeps a local Face registry with at least two operational Faces.
Each Face record stores a face id, local label, creation time, most recent
access time, occupancy estimate, and current status. The same shared backend
is used by CLI and TUI Face operations.

### Face-Bound Storage

Each Face owns an independent encrypted file namespace. Files stored under one
Face do not appear in another Face.

```bash
phasmid file add /path/to/travel.vessel --face face_a --input note.txt
phasmid file list /path/to/travel.vessel --face face_a
phasmid file remove /path/to/travel.vessel --face face_a --name note.txt
```

Inspection reports Face count plus per-Face occupancy, file count, and most
recent access time. It does not list cross-Face file contents.

### Clear Local Access Path

```bash
phasmid brick
```

This flow destroys `.state/access.bin` first, then performs a best-effort overwrite of `vault.bin`. Flash media, snapshots, backups, and journaling filesystems may retain old data. Recovery resistance depends primarily on destruction, rotation, or removal of required key material, not on overwrite guarantees.

## 7. WebUI v2

The WebUI is managed directly from the TUI Operator Console (hotkey `w`).

### Exposure Control

The TUI provides a high-visibility warning banner when the WebUI is active and
includes an **Auto-Kill Timer**. If the TUI detects no operator input for 10
minutes while the WebUI is running, it will automatically terminate the WebUI
subprocess to return the system to a stealth state.

To start the server manually:

```bash
PYTHONPATH=src python3 -m phasmid.web_server
```

The default bind address is `127.0.0.1:8000`, for both this command and the TUI `w` key. Binding the USB Ethernet gadget interface instead requires `PHASMID_WEBUI_EXPOSE_GADGET=1`; a wildcard bind requires setting `PHASMID_HOST` explicitly.

Every operator page, `/status`, and `/video_feed` require a page session for any peer that is not on loopback. A loopback peer is exempt: it is on the device itself, where the TUI already has full local control. The exemption is decided per request from the peer address, not from configuration.

A session is created at `/unlock` by presenting the access token (`PHASMID_WEB_TOKEN`, or the per-process token published to `<state dir>/webui_token` and shown by the TUI). The server issues an `HttpOnly`, `SameSite=Strict` cookie bound to the client address, valid for `PHASMID_UI_SESSION_SECONDS`. `POST /lock` drops it. The mutation token is rendered into page HTML only for requests that already satisfy the gate.

Requests whose `Host` header is a DNS name are rejected with `400`, which blocks DNS rebinding. Address literals and `localhost` are always accepted; add names reached over DNS or mDNS to `PHASMID_ALLOWED_HOSTS`.

WebUI v2 is server-rendered with lightweight JavaScript. It preserves the internal two-slot model while presenting normal operations as protected-entry workflows.

Normal navigation presents a Simple Operator surface:

- Home
- Protect a File
- Open a Protected File
- Guided Mode

Maintenance, diagnostics, audit, and inspection are available through
Advanced tools for experienced operators. Normal flows do not expose those
controls by default.

The restricted action view is available only by direct route and is not shown in normal navigation. A direct `GET /emergency` renders only a restricted confirmation screen until the browser has a fresh restricted confirmation session. After confirmation, the page presents a short stepwise emergency flow with exact-phrase prompts and a visible restricted-confirmation lifetime. Hidden route concealment is not a security boundary.

`PHASMID_FIELD_MODE=1` reduces normal Maintenance detail for appliance use. Before restricted confirmation, Maintenance shows only general health, local-only posture, and a confirmation requirement for sensitive maintenance. It hides state paths, audit export, token rotation, and detailed diagnostics until a fresh restricted confirmation is active. The hidden restricted action route also uses a quieter stepwise emergency flow intended to reduce operator confusion during high-stress local actions.

Field Mode is not a security boundary. It reduces casual local exposure in the WebUI and maintenance APIs. It does not prevent forensic inspection, filesystem analysis, memory capture, host compromise, browser compromise, physical coercion, or lawful compulsory process.

Hidden restricted routes are UX concealment only. They are not access control by themselves. High-risk actions are evaluated through a shared local policy layer that combines deployment-mode capability, local tokens, restricted confirmation freshness, and typed confirmation where applicable.

WebUI responses include conservative browser hardening headers such as no-store cache control, frame denial, MIME-sniffing protection, a local-only content security policy, no-referrer policy, and limited browser permissions. These headers reduce browser-visible residue and common embedding or caching risks. They do not make the WebUI suitable for untrusted networks and are not a substitute for local-only binding, host integrity, or operator discipline.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/unlock` | Access screen for non-loopback peers; the only page served without a page session |
| `POST` | `/unlock` | Open a page session by presenting the access token |
| `POST` | `/lock` | Drop the page session and any restricted confirmation |
| `GET` | `/` | Home |
| `GET` | `/store` | Store screen |
| `GET` | `/retrieve` | Retrieve screen |
| `GET` | `/maintenance` | Maintenance screen |
| `GET` | `/maintenance/entries` | Entry management screen |
| `GET` | `/emergency` | Hidden restricted action screen |
| `GET` | `/video_feed` | Camera stream for the active local WebUI session |
| `GET` | `/status` | Neutral device/object status |
| `POST` | `/restricted/confirm` | Short-lived restricted confirmation |
| `POST` | `/register_key` | Bind or rebind a physical object (camera capture or an optional uploaded reference image) |
| `POST` | `/store` | Store a protected entry |
| `POST` | `/metadata/check` | Local metadata risk check |
| `POST` | `/metadata/scrub` | Best-effort local metadata reduction |
| `POST` | `/retrieve` | Retrieve and download the matching entry |
| `POST` | `/destroy_face` | Clear the entry whose object is presented, using that entry's destroy password |
| `POST` | `/purge_other` | Hidden restricted clear action |
| `POST` | `/emergency/initialize` | Hidden container initialization |
| `POST` | `/emergency/brick` | Hidden local access-path clear action |
| `GET` | `/maintenance/diagnostics` | Local diagnostics |
| `POST` | `/maintenance/rotate_token` | Rotate Web mutation token |
| `POST` | `/maintenance/reset_session` | Reset local session counters |
| `GET` | `/maintenance/logs` | Export optional local audit log |

Every endpoint except `GET`/`POST /unlock` and the static asset mount requires a page session. Mutating endpoints additionally require `X-Phasmid-Token`. Sensitive endpoints also require a short-lived restricted confirmation session and typed action confirmation where applicable. Entry Management withholds binding details until restricted confirmation is active and returns only selected-entry neutral status.

Typed action confirmation phrases are public constants in `src/phasmid/restricted_actions.py`. They guard against operator mistakes and are never the authorization control for an action.

`/status` intentionally returns only neutral fields:

- `camera_ready`
- `object_state`
- `device_state`
- `local_mode`

The normal UI must not display internal entry labels, internal retrieval order, or restricted local-state behavior after retrieval.

Detailed maintenance diagnostics may include neutral hardware-binding availability fields after restricted confirmation or when Field Mode is not suppressing detail.

WebUI exposure is bounded by explicit operator start from the TUI, local-only binding to `127.0.0.1` by default, opt-in and single-interface USB gadget binding, and TUI-managed auto-kill on inactivity.

## 8. Capture-Visible Surface Rule

No capture-visible surface should reveal the internal disclosure model, internal trial order, slot purpose, restricted recovery side effects, or the existence of an alternate protected state.

Capture-visible surfaces include the WebUI, rendered HTML, browser history, browser cache, JavaScript console, response headers, download filenames, CLI output, shell history, systemd stdout/stderr, audit logs, state-directory filenames, screenshots, and documentation copied to the device.

Common user-facing wording should be centralized where practical. New UI, CLI, API, and audit text must either reuse shared neutral strings or pass terminology audit before release.

## 9. Stress-Use UX Principle

Phasmid must prefer simple, low-choice flows under stress.

Normal operation should remain:

1. Protect a File
2. Open a Protected File
3. Guided Mode when help is needed

Advanced and restricted actions must remain separated. Field Mode should reduce
diagnostic noise. The UI should avoid forcing the user to reason about internal
slots, trial order, recovery side effects, or disclosure structure during
stressful conditions.

## 10. Metadata and Data Minimization

Store provides a local-only metadata risk check. It does not call cloud services and does not send telemetry.

`/destroy_face` is the only restricted action gated by a credential rather than
by a public confirmation phrase alone. It requires the bound object of the entry
being cleared to be matching at the moment of the call, that entry's destroy
password (a different credential from its access password, which cannot perform
this action and which this password cannot use to read), and the phrase
`DESTROY FACE` — the same phrase `phasmid emergency destroy-face --confirm`
takes. It does **not** additionally require a restricted confirmation session:
that would add a step without adding authorization, and this is the one action
reached under duress, where each extra step is taken in front of the person
applying it. The entry cleared is determined by the live object match and never
by a request parameter, so the surface never has to name one of two entries.
Failures are indistinguishable — a wrong destroy password, an uninitialized
entry, and an object that stopped matching all return the same rejection — and
they count against the same attempt limiter as `/retrieve`.

`/metadata/check` and `/metadata/scrub` enforce the normal Web mutation token, rate limiting, and upload size limit. Uploaded data is processed in memory; these routes do not require writing the uploaded file to disk, and the intended implementation property is no disk write for uploaded metadata inspection.

The initial checker warns about common risks:

- GPS-like image metadata;
- camera maker or model metadata;
- device serial-like fields;
- document author fields;
- creator application fields;
- document title or subject fields;
- embedded thumbnails;
- local path leakage;
- original filename context.

Storage is not blocked by default. The UI offers continue, best-effort metadata reduction when supported, or cancel.

Best-effort metadata reduction is conservative. It never overwrites the original file unless a future explicit option is added. Unsupported file types fail safely. Downloads use a neutral filename and must not expose the original filename in response headers. Metadata removal is best-effort and may not remove every embedded identifier from every file format.

The Store screen includes a short reminder: store only what is needed and separate identities, evidence, notes, and operational context when possible.

## 11. Cryptography

The current format is JES v3.

- No plaintext magic/header.
- Fixed-width internal storage spans.
- Each span contains a normal access slot and a restricted recovery slot.
- Per-record random salt and nonce.
- AES-GCM authenticated encryption.
- Filename and payload metadata are encrypted.
- v1/v2 compatibility retrieval has been removed.

Argon2id inputs:

- User password
- Physical-object cue token
- Internal mode
- Password role
- Per-record random salt
- `.state/access.bin`
- Optional external values from `PHASMID_HARDWARE_SECRET_FILE`, `PHASMID_HARDWARE_SECRET`, or `PHASMID_HARDWARE_SECRET_PROMPT`

Default Argon2id parameters are tuned for Raspberry Pi Zero 2 W class hardware: `memory_cost=32768`, `iterations=2`, `lanes=1`.

Recommended field hierarchy:

1. strong access password;
2. physical-object cue;
3. `.state/access.bin`;
4. optional external value via `PHASMID_HARDWARE_SECRET_FILE` or `PHASMID_HARDWARE_SECRET_PROMPT=1`.

For high-risk deployments, do not store all recovery conditions on the same physical medium. Phasmid is strongest when the encrypted container, local state, memorized password, physical-object cue, and optional external key material are separated.

## 12. Physical-Key Matching

Phasmid extracts ORB features from camera frames.

Registration:

1. Capture several frames over a short interval.
2. Select the candidate with the most keypoints.
3. Reject low-feature images.
4. Reject candidates too similar to an existing object cue.
5. Store templates together in encrypted `.state/store.bin`.

Retrieval:

1. Extract ORB features from current frames.
2. Match against encrypted reference templates.
3. Require enough good matches and homography inliers.
4. Require stable matching in at least 3 of the last 5 frames.
5. Reject ambiguous matches.

The physical object is an operational cue, not a high-entropy cryptographic factor.

Multi-object and visual-sequence cue extensions are analysis-only at this stage. Any future implementation must preserve neutral capture-visible behavior, explicit ambiguity rejection, and no direct cryptographic dependence on unstable image coordinates.

An experimental policy-layer prototype can evaluate neutral frame signals (for example `none|detected|matched|ambiguous`) and optional short token sequences, but this remains a local operational gate decision and not a cryptographic input path.

## 13. Runtime Policy

| Variable | Purpose | Default |
| --- | --- | --- |
| `PHASMID_STATE_DIR` | Runtime state directory | `.state` |
| `PHASMID_STATE_SECRET` | External value for object-cue state encryption | unset |
| `PHASMID_HARDWARE_SECRET_FILE` | External value file mixed into Argon2id | unset |
| `PHASMID_HARDWARE_SECRET` | External value string mixed into Argon2id | unset |
| `PHASMID_HARDWARE_SECRET_PROMPT` | Prompt for an external value | unset |
| `PHASMID_PURGE_CONFIRMATION` | Require explicit confirmation for configured recovery behavior | `1` |
| `PHASMID_DURESS_MODE` | Enable opt-in access-triggered local-state update | `0` |
| `PHASMID_WEB_TOKEN` | Web access and mutation token | random at start |
| `PHASMID_UI_SESSION_SECONDS` | WebUI page session lifetime | `1800` |
| `PHASMID_ALLOWED_HOSTS` | Extra `Host` names accepted beyond address literals | unset |
| `PHASMID_HOST` | Web bind host; overrides gadget exposure when set | `127.0.0.1` |
| `PHASMID_WEBUI_EXPOSE_GADGET` | Bind the USB gadget interface address instead of loopback | `0` |
| `PHASMID_PORT` | Web bind port | `8000` |
| `PHASMID_MAX_UPLOAD_BYTES` | Web upload limit | `26214400` |
| `PHASMID_RESTRICTED_SESSION_SECONDS` | Restricted confirmation lifetime | `120` |
| `PHASMID_FIELD_MODE` | Reduce normal WebUI operational detail | `0` |
| `PHASMID_PROFILE` | Select local capability mode: `standard`, `field`, or `maintenance` | `standard` |
| `PHASMID_MIN_PASSPHRASE_LENGTH` | Minimum Store passphrase length | `10` |
| `PHASMID_ACCESS_MAX_FAILURES` | Failed access attempts before temporary lockout | `5` |
| `PHASMID_ACCESS_LOCKOUT_SECONDS` | Temporary access lockout duration | `60` |
| `PHASMID_AUDIT` | Enable audit logging | `0` |
| `PHASMID_AUDIT_FILENAMES` | Record filename hashes | unset |

## 14. Mission Presets and Retention

Phasmid documentation defines neutral mission presets rather than role-revealing UI labels. Examples include:

- Local Notes;
- Temporary Holding;
- Protected Material;
- Travel Set;
- Review Set;
- Research Material.

Presets should influence guidance such as metadata warning, external key material recommendation, retention reminders, audit disabled by default, Field Mode recommendation, and entry separation guidance.

Retention principle: the safest sensitive data is data not carried. Users should remove stale entries after the task or trip, avoid old contact lists, avoid mixing unrelated work in one local entry, and review contents before checkpoints or inspection events.

## 15. Restricted Recovery and Key Destruction

On flash media, complete overwrite-based deletion cannot be guaranteed across every storage layer. Phasmid therefore treats restricted recovery primarily as key-path invalidation and key-material destruction, with best-effort overwrite as a secondary measure.

Restricted recovery must not be represented as guaranteed secure deletion. User-facing surfaces should use neutral terms such as restricted local update, local access path, key material, and best-effort overwrite.

### Key-Material Invalidation Sequence

The following table defines the mandatory ordering for local access-path clear operations. Key-material destruction must precede any container overwrite. This ordering ensures that the container ciphertext becomes unrecoverable even if the overwrite fails or is partially reversed by the storage layer.

| Step | Action | Target | Effect |
|------|--------|--------|--------|
| 1 | Overwrite + remove | `.state/access.bin` | Local access key destroyed; Argon2id derivation path broken |
| 2 | Best-effort overwrite | `vault.bin` (full or partial slot) | Container ciphertext randomized; recovery requires the key from step 1 |

**Step 1 alone** makes recovery infeasible: the Argon2id key cannot be recomputed without the local access key, even if the attacker has a copy of `vault.bin` and the user's passphrase. Step 2 is a secondary, best-effort measure.

Tests confirming this ordering and behavior are in `tests/test_vault_core.py` under the "Key-material invalidation sequence" section.

This invalidation sequence applies to: `vault.silent_brick()`, `vault.purge_mode()`, and the restricted-recovery path triggered by the restricted recovery password (PURGE_ROLE).

## 16. v4 Key Schedule Design (Argon2id + HKDF-SHA-256)

The v3 container format uses inline string concatenation for domain separation in the Argon2id context string. The v4 design introduces a second derivation stage via HKDF-SHA-256 that produces cryptographically independent, explicitly labelled subkeys from a single Argon2id output.

### Design

```
Argon2id(passphrase + local_key + hardware_secret, salt)
    → 32-byte IKM
    → HKDF-SHA-256(IKM, info=<label>) → vault open subkey
    → HKDF-SHA-256(IKM, info=<label>) → vault purge subkey
    → HKDF-SHA-256(IKM, info=<label>) → local state subkey
    → HKDF-SHA-256(IKM, info=<label>) → audit HMAC subkey
```

### Domain Labels (v4)

| Label | Purpose |
|-------|---------|
| `phasmid-v4:vault:open:1` | AES-GCM key for the OPEN recovery slot |
| `phasmid-v4:vault:purge:1` | AES-GCM key for the PURGE recovery slot |
| `phasmid-v4:state:1` | AES-GCM key for local state blobs |
| `phasmid-v4:audit-hmac:1` | HMAC-SHA-256 key for audit record chaining |

Label format: `phasmid-v4:<purpose>:<version>`. The version suffix is incremented when the purpose changes semantically. This decouples label evolution from container format changes.

### HKDF Role in This Design

Argon2id provides memory-hard password stretching and is not replaced. HKDF-SHA-256 is used exclusively for domain-separated subkey derivation from the Argon2id output. HKDF does not replace or weaken the Argon2id stage.

### v3 Compatibility

v3 containers remain valid under the v3 KDFEngine path. A v4 container uses `src/phasmid/kdf_subkeys.py` for the second derivation stage. Migration: retrieve with v3, re-store with v4.

This design is not a FIPS validation claim and does not imply certification. It is an engineering improvement to domain separation within the local key derivation pipeline.

Test vectors and domain separation tests are in `tests/test_kdf_subkeys.py`.

## 17. Appliance and Seizure Review

Raspberry Pi Zero 2 W appliance assumptions are documented in `docs/RPI_ZERO_APPLIANCE_DEPLOYMENT.md`. The recommended appliance posture is local-only binding, USB gadget access, SSH disabled after provisioning, Wi-Fi and Bluetooth disabled unless explicitly needed, dedicated service user, systemd hardening, Field Mode, audit disabled by default, debug disabled by default, no telemetry, no cloud dependency, no remote management, and external key-material separation.

Seizure review requirements are documented in `docs/SEIZURE_REVIEW_CHECKLIST.md`. Review normal screens, restricted pages before and after confirmation, browser history, cache, HTML source, JavaScript console, HTTP response headers, download filenames, optional audit logs, `.state/` names, temporary files, shell history, systemd logs, CLI output, environment variables, and service unit files.

Operational guidance documents include `docs/SOURCE_SAFE_WORKFLOW.md`, `docs/SEIZURE_REVIEW_CHECKLIST.md`, `docs/FIELD_TEST_PROCEDURE.md`, `docs/REVIEW_VALIDATION_RECORD.md`, `docs/OPERATIONS.md`, `docs/RESTRICTED_ACTIONS.md`, and `docs/STATE_RECOVERY.md`.

Optional audit records are versioned and include sequence, previous record hash, record hash, and local verifier fields. This improves local tamper review when audit logging is enabled, but it also creates additional local metadata and is disabled by default.

## 17. Testing

```bash
python3 -m unittest discover -s tests
```

KDF benchmark:

```bash
python3 scripts/bench_kdf.py
```

## 18. Compatibility

This build reads and writes JES v3 records only. Earlier development containers that depend on superseded internal record labels are not supported and should be reinitialized before use.

## 19. Limits

Phasmid does not guarantee protection against a compromised OS, live memory capture, keylogging, camera observation, forced disclosure, complete secure deletion, deniability, or unsafe network exposure.

Phasmid does not claim software existence concealment. Discovery of project files, binaries, logs, or deployment traces can reveal that coercion-aware storage software is present.

The intended claim boundary is:

- controlled disclosure is in scope;
- data-existence deniability is partial and scenario-dependent;
- software existence concealment is out of scope.
