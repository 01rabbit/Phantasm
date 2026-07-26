# AGENTS.md

> **Notice**: This file is the primary context entry point for AI-assisted development.
> It defines the project boundaries, security invariants, and the current work focus.

## 0. Quick Start for AI Agents

1. **Identify the Task**: Match your task to a domain in the [Canonical Source Map](#canonical-source-map).
2. **Load Minimal Context**: Load only the files and documentation sections listed for that domain.
3. **Verify Invariants**: Check your proposed changes against the [Core Invariants](#core-invariants).
4. **Follow Language Rules**: Ensure all user-visible text follows [User-Facing Language Rules](#user-facing-language-rules).
5. **Run Tests**: Execute the relevant tests and static analysis before submitting.

---

## Purpose

This file is the first context entry point for AI-assisted development in this repository.

Phasmid is a field-evaluation prototype for local-only coercion-aware storage. It explores lawful local protection of sensitive material where device seizure, compelled access, over-disclosure, metadata risk, and local UI/log leakage are practical risks.

Phasmid is research software. It is not a replacement for full-disk encryption, hardware-backed key storage, an audited classified-data handling system, organizational records-management systems, or a complete solution to compelled disclosure.

Use this file to keep AI-assisted changes small, scoped, and consistent with the project boundary.

---

## Project Status & Roadmap

### Current Focus: Unified JES Operator Surface Hardening and Documentation Consistency

The JES Operator Interface unification work is merged into **`main`** and the Raspberry Pi Zero 2 W validation issue track (`#89` through `#94`) is completed. The current focus is stability maintenance of the unified operator experience, preserving WebUI/TUI terminology parity, and keeping implementation and documentation synchronized without reintroducing branch-specific assumptions.

### Active Branch

**`main`** contains:
- TUI Operator Console (Textual-based): full operator screen set (Home, Doctor, Audit, Guided, Inspect, Create, Open, Face Manager, Settings, About)
- Merged WebUI redesign phases `#39` through `#43`

Target: maintain and harden the unified JES operator surface on `main`.

### Priority Tracking Status

- Pi Zero 2 W remote field-test harness and validation workflow issues (`#89` through `#94`) are completed and retained as traceability references.
- New implementation priorities should be tracked as separate issues and reflected here only while actively in progress.

Historical roadmap detail, completed milestone history, and the WebUI redesign sequence are maintained in `docs/ROADMAP_HISTORY.md`. Keep this file focused on active context and operating constraints, not long-form project history.

---

## Project Boundary

Preserve this boundary in code, documentation, tests, and UI behavior:

- local-only operation by default
- protected entries stored in `vault.bin`
- local runtime state under `.state/` or `PHASMID_STATE_DIR`
- password-based cryptographic recovery
- Argon2id-derived keys
- AES-GCM authenticated encryption
- local access key material mixed into recovery
- object-image matching as an operational access cue
- optional UI face lock as a local interface gate
- neutral WebUI and CLI language
- restricted local actions with explicit confirmation
- best-effort local access-path invalidation
- target-hardware field evaluation before stronger claims

Do not expand Phasmid into remote management, cloud recovery, telemetry, covert communication, censorship bypass, surveillance evasion, malware storage, offensive operations, or classified-data handling infrastructure.

---

## Non-Negotiable Security Claims

Do not claim that Phasmid provides:

- perfect deniability
- guaranteed secure deletion
- protection against compromised hosts
- protection against malware or keyloggers
- protection against live memory capture
- protection against camera observation
- protection against physical coercion after disclosure
- certified classified-data handling
- formal compliance approval
- anonymity
- covert communication
- censorship bypass
- surveillance evasion
- remote wipe
- remote unlock
- remote attestation
- tamper-proof audit logging
- protection on untrusted networks

When discussing deletion, restricted recovery, panic behavior, bricking, or emergency actions, describe the behavior as:

- local access-path clearing
- key-material destruction
- key-path invalidation
- restricted local update
- best-effort overwrite

Never describe it as guaranteed secure deletion.

---

## Core Invariants

Preserve these invariants unless a change explicitly updates the threat model, specification, tests, and user-facing documentation.

- The system is local-only by default.
- The WebUI binds to `127.0.0.1` by default, on every start path including the TUI `w` key. USB gadget binding is opt-in via `PHASMID_WEBUI_EXPOSE_GADGET` and binds that one interface address; only an explicit `PHASMID_HOST` can produce a wildcard bind.
- `vault.bin` alone should not be enough for normal recovery when required local state is absent.
- The local access key remains part of the recovery path unless a documented migration changes the container format.
- Object matching is an operational access cue, not cryptographic key material.
- ORB descriptors, image coordinates, face templates, and camera frames must not be described as high-entropy secrets.
- UI face lock is a local interface gate only and must not be treated as vault encryption.
- Hidden routes are UX concealment only, not access control.
- WebUI pages, `/status`, and `/video_feed` require a page session established at `/unlock` with the access token. `_ui_unlocked()` must remain a real check; never reduce it to an unconditional `True`.
- The mutation token is rendered into page HTML only for a request that already holds a page session. It is a CSRF token for an unlocked session, never the credential that opens one.
- Typed confirmation phrases are public constants. They are typo guards, not authorization; no action may be gated by a phrase alone.
- Field Mode reduces casual local exposure but is not a security boundary.
- Restricted actions must require server-side checks, short-lived restricted confirmation, and typed confirmation where applicable.
- Normal UI and CLI flows must not reveal internal storage labels, trial order, restricted recovery behavior, or alternate protected state.
- Capture-visible surfaces must use neutral language.
- Audit logging remains optional and must not record passwords, payload bytes, plaintext filenames, internal entry semantics, or disclosure structure.
- Metadata reduction is best-effort and must not be described as complete sanitization.
- Passing automated tests does not prove field safety.

---

## Canonical Source Map

Load only the relevant files for the requested change. Do not load the whole repository by default.
Issue-level implementation history is maintained in `docs/ROADMAP_HISTORY.md`.

### Cryptography, Container Format, and Key Path

Use this context for changes involving `vault.bin`, the Phasmid vault core, Argon2id, AES-GCM, salts, nonces, local access key material, span layout, record parsing, restricted recovery slots, destructive behavior, or migration:

- `src/phasmid/vault_core.py`
- `src/phasmid/crypto_boundary.py`
- `src/phasmid/kdf_engine.py`
- `src/phasmid/kdf_providers.py`
- `src/phasmid/container_layout.py`
- `src/phasmid/record_cypher.py`
- `docs/SPECIFICATION.md`, especially sections 11 and 15
- `docs/THREAT_MODEL.md`
- `tests/test_vault_core.py` and related tests

### TUI Operator Console

Use this context for changes involving the Textual-based operator interface, TUI screens, widgets, theme, banner, service layer, or WebUI lifecycle management from the TUI:

- `src/phasmid/tui/app.py`
- `src/phasmid/tui/theme.py`
- `src/phasmid/tui/banner.py`
- `src/phasmid/tui/screens/` (all screen files)
- `src/phasmid/tui/widgets/` (all widget files)
- `src/phasmid/services/` (shared service layer: doctor, audit, guided, inspection, vessel, profile, webui)
- `src/phasmid/models/` (data models: vessel, profile, doctor, audit, inspection)
- `docs/TUI_OPERATOR_CONSOLE.md`
- `tests/test_tui.py`

Design concept: structured institutional UI with terminal-first aesthetics.  
Theme: `phasmid-dark` (`primary=#00d7af`, `background=#0d0d0d`, `success=#87d700`).

Key TUI-only responsibilities (do not replicate these in WebUI):
- Vessel creation, listing, and file-system operations via `VesselService`
- Profile and settings persistence via `ProfileService`
- WebUI lifecycle control (start/stop/auto-kill) via `WebUIService`
- Secure passphrase input (terminal prompt, not browser field)

### WebUI, API Routes, and Restricted Actions

Use this context for changes involving FastAPI routes, Web mutation token, restricted confirmation, hidden routes, Field Mode, face lock sessions, store/retrieve routes, maintenance routes, emergency routes, response headers, or neutral download filenames:

- `src/phasmid/web_server.py`
- `src/phasmid/templates/`
- `src/phasmid/restricted_actions.py`
- `src/phasmid/capabilities.py`
- `src/phasmid/emergency_daemon.py`
- `src/phasmid/bridge_ui.py`
- `docs/SPECIFICATION.md`, especially sections 7, 8, and 9
- `docs/THREAT_MODEL.md`
- `tests/test_web_server.py` and related tests

### CLI Behavior

Use this context for changes involving `main.py`, command syntax, CLI output, confirmations, retrieve/store/init/brick/reset-face-lock behavior, or CLI terminology:

- `main.py`
- `src/phasmid/cli.py`
- `src/phasmid/passphrase_policy.py`
- `docs/SPECIFICATION.md`, especially section 6
- `docs/THREAT_MODEL.md`
- `tests/test_cli.py` and related tests

### Object Cue, Camera Matching, and Face Lock

Use this context for changes involving ORB matching, camera capture, object cue registration, match ambiguity, stable multi-frame matching, face template enrollment, or UI lock behavior:

- `src/phasmid/ai_gate.py`
- `src/phasmid/web_server.py` (UI face-lock session handling)
- `docs/SPECIFICATION.md`, especially section 12
- `docs/THREAT_MODEL.md`
- related tests in `tests/`

### Metadata Handling

Use this context for changes involving metadata risk detection, metadata reduction, uploads, in-memory processing, file type support, original filename handling, or neutral metadata-reduced downloads:

- `src/phasmid/metadata.py`
- `src/phasmid/web_server.py` metadata routes
- `docs/SPECIFICATION.md`, especially section 10
- `docs/THREAT_MODEL.md`
- related tests in `tests/`

### Audit Logging

Use this context for changes involving event logs, audit record shape, hash chains, HMACs, log export, audit filenames, event names, or audit metadata:

- `src/phasmid/audit.py`
- `src/phasmid/operations.py`
- `src/phasmid/web_server.py` maintenance log export
- `docs/THREAT_MODEL.md`
- `docs/SPECIFICATION.md`
- related tests in `tests/`

### Local State and Deployment Posture

Use this context for changes involving `.state/`, state file names, state permissions, typed state, attempt limiting, tmpfs, LUKS, deployment profile, appliance setup, service hardening, runtime secrets, or Raspberry Pi deployment:

- `src/phasmid/config.py`
- `src/phasmid/state_store.py`
- `src/phasmid/attempt_limiter.py`
- `docs/RPI_ZERO_APPLIANCE_DEPLOYMENT.md`
- `docs/RPI_ZERO_DEPLOYMENT.md`
- `docs/FIELD_TEST_PROCEDURE.md`
- `docs/SEIZURE_REVIEW_CHECKLIST.md`
- `docs/REVIEW_VALIDATION_RECORD.md`
- `docs/SOLUTION_READINESS_PLAN.md`
- related tests in `tests/`

### Testing, CI, Coverage, and Release Review

Use this context for changes involving tests, CI, static analysis, coverage, release validation, SBOMs, manifests, or review records:

- `tests/`
- `.github/workflows/`
- `pyproject.toml`
- `requirements-dev.txt`
- `scripts/`
- `docs/REVIEW_VALIDATION_RECORD.md`
- `docs/SOLUTION_READINESS_PLAN.md`
- `README.md`

---

## Documentation Authority

When documents overlap, use this authority order:

1. `docs/THREAT_MODEL.md` controls security assumptions, residual risks, and safety boundaries.
2. `docs/SPECIFICATION.md` controls intended behavior and implementation contracts.
3. `README.md` controls public-facing project summary, installation, usage, and known limits.
4. Deployment documents control appliance setup and operational procedures.
5. Field test and seizure review documents control validation procedure and review evidence.
6. Issue descriptions describe planned work but do not override merged documentation.

Do not silently resolve contradictions. If code, tests, README, specification, threat model, and issue text conflict, state the conflict and update the affected artifacts in the same change when appropriate.

---

## User-Facing Language Rules

Use neutral terms in WebUI, CLI output, logs, response bodies, headers, filenames, documentation examples, and tests that assert visible text.

Prefer:

- protected entry / Disclosure Face (TUI-aligned term for WebUI operator pages)
- local entry
- object cue
- access cue
- passphrase (preferred over "access password" in operator-facing contexts)
- local access path
- restricted confirmation
- restricted local update
- key material
- key-path invalidation
- best-effort overwrite
- metadata risk
- local-only operation
- Field Mode
- UI face lock
- object cue accepted
- no valid entry found
- local container initialized
- Janus Eidolon System / JES (brand subtitle, operator-facing)
- Vessel (TUI term for the deniable container; use in operator pages)
- Disclosure Face 1 / Disclosure Face 2 (TUI-aligned labels for entry select options)
- Live Sensor Feed (camera panel title in operator context)

Avoid in normal user-facing surfaces:

- dummy
- secret
- hidden slot
- real
- fake
- decoy
- purge slot
- trial order
- alternate state
- duress password
- panic password
- self-destruct
- dead man switch
- secure delete
- biometric proof
- authenticated by object
- classified approved
- military grade
- unbreakable
- deniable encryption

Internal implementation names may remain in code when necessary, but normal capture-visible behavior should stay neutral.

---

## Capture-Visible Surface Rule

Before changing any of the following, check whether the change reveals internal disclosure structure:

- WebUI text
- HTML templates
- JavaScript console messages
- API responses
- response headers
- download filenames
- CLI output
- shell-visible messages
- systemd stdout or stderr
- audit events
- exported logs
- diagnostics
- browser-visible routes
- documentation copied to a deployed device
- tests that encode user-visible strings

Do not reveal during normal operation:

- internal slot labels
- internal retrieval order
- restricted recovery side effects
- alternate protected state
- object binding internals
- local state paths in Field Mode before restricted confirmation
- original filenames where neutral filenames are required
- whether a failure was caused by password, object cue, local state, restricted policy, or internal candidate mismatch, unless required for safe operation

---

## AI Context Discipline

For any AI-assisted task:

1. Identify the affected domain using the Canonical Source Map.
2. Load only the relevant source files, tests, and document sections.
3. State which core invariants the change touches.
4. Make the smallest safe change.
5. Update tests when behavior changes.
6. Update documentation when behavior, claims, terminology, or operational assumptions change.
7. Avoid broad repository-wide rewrites unless explicitly required.
8. Do not combine unrelated refactors with security-sensitive behavior changes.
9. Do not change cryptographic behavior and UI language in the same patch unless the issue explicitly requires it.
10. Do not modify container compatibility without a documented migration or compatibility plan.

---

## Testing Expectations

Run or update tests when changing:

- cryptography or container format
- KDF inputs
- local access key behavior
- state file layout
- Web mutation authorization
- restricted confirmation
- restricted actions
- Field Mode visibility
- face lock behavior
- object cue behavior
- metadata checking or scrubbing
- audit output
- UI terminology
- CLI terminology
- destructive or restricted operations
- diagnostics
- response headers
- download filenames

Default test command:

```bash
python3 -m unittest discover -s tests
```

KDF benchmark command:

```bash
python3 scripts/bench_kdf.py
```

Passing automated tests do not prove field safety. They verify implementation contracts only. Field safety still requires target-hardware field testing and seizure review.

---

## Change Discipline

Make small, reviewable changes.

Do not:

- add telemetry
- add cloud dependencies
- add remote unlock
- add remote wipe
- expose the WebUI to untrusted networks by default
- weaken local-only defaults
- weaken typed confirmations
- weaken short-lived restricted sessions
- weaken Web mutation token checks
- weaken upload limits
- weaken neutral error behavior
- increase Field Mode diagnostic detail before restricted confirmation
- introduce compliance, certification, or field-proven claims without validation records
- silently break existing v3 containers
- silently migrate stored data
- store all recovery conditions on the same medium by default
- add custom threshold cryptography without review and test vectors
- treat device identifiers as high-entropy secrets
- treat UI face lock as vault encryption
- treat object cues as cryptographic authentication

If a proposed change would improve convenience but weaken capture-visible quietness, local-only posture, or recovery safety, reject the change or require an explicit threat-model update.

---

## Review Checklist for AI-Generated Changes

Before finalizing an AI-generated change, verify:

- The touched domain matches the loaded context.
- Core invariants are preserved.
- User-facing language remains neutral.
- Field Mode remains quiet.
- Hidden routes are not treated as access control.
- Restricted actions still require the intended predicates.
- Download filenames remain neutral where required.
- Audit records do not expose sensitive semantics.
- Metadata handling does not claim complete sanitization.
- Deletion behavior is not described as guaranteed secure deletion.
- Tests cover the changed behavior.
- Documentation claims match actual implementation.
- Existing container compatibility is preserved or migration is explicitly documented.

---

## Operational Discipline

### Self-Hardening Execution Rules

When implementing tasks generated from `PHASMID_SELF_HARDENING_ISSUES.md`, follow these additional constraints:

- No scope creep: do not add features or claims that are not explicitly requested by the scoped issue.
- Keep README and implementation claims aligned; if behavior is implemented but not documented (or vice versa), open a follow-up issue instead of silently expanding claims.
- Use test-first discipline for behavior changes: add a failing test first, then implement the fix.
- Avoid custom cryptographic primitive logic when vetted high-level library APIs already cover the requirement.
- Keep PR scope single-purpose by default (`1 issue = 1 PR`).
- If changing `AGENTS.md`, explicitly mention that change in the PR description.

### Change & Test Strategy

- **Surgical Edits**: Prefer targeted edits over full-file rewrites for large files.
- **Verification**: Run `ruff`, `mypy`, and `python3 -m unittest discover -s tests` after changes.
- **No Regressions**: Ensure coverage stays above **70%**.

---

## Scope of This File

This file is development guidance only. It does not define user-facing product claims, legal advice, operational approval, or deployment authorization.

If this file conflicts with the threat model or specification, the threat model and specification take precedence according to the Documentation Authority section.
