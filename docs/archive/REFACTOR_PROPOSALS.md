# Refactor Proposals

This document records proposal-only items from the June 2026 refactor pass.
No code changes are authorized by this document. Items that affect stored data,
security gates, operator-visible behavior, or deployment posture require owner
approval and matching specification or threat-model updates before
implementation.

## D2: `kdf_subkeys.py` Staged v4 Design

Motivation: `kdf_subkeys.py` is not wired into the v3 runtime path, but its
presence can be mistaken for an active container-format migration.

Design: Choose one of three owner-approved outcomes: keep it with an explicit
"design artifact, not wired" module header; move it under an archive namespace;
or remove it together with its direct tests and retention-matrix entries.

Migration steps: If kept, add the header and a short note in the retention
matrix. If archived or removed, update imports, `tests/test_kdf_subkeys.py`,
`tests/test_terminology.py`, and `tests/TEST_RETENTION_MATRIX.md` in the same
change.

Test impact: Run terminology tests, retention-matrix checks, full default and
optional suites, and any claim-coverage checks that mention future key
derivation work.

Compatibility risk: Low if only documented. High if implemented as a format
change, because any v4 subkey migration would affect stored local data and
container compatibility.

Gate: Q1.

## D3: Dead Recognition Module Disposition

Motivation: `face_sample_matcher.py` and `object_cue_policy_gate.py` appear
unused by runtime imports, while similarly named modules make the active object
cue path harder to identify.

Design: After owner approval, either delete the unused modules or retain them
with clear "not wired into runtime" headers and retention-matrix rationale.
Keep `lightweight_object_matcher.py` and `recognition_benchmark.py` as
evaluation components.

Migration steps: For deletion, remove the module files, remove or relocate
their tests, update `tests/test_terminology.py`, and update
`tests/TEST_RETENTION_MATRIX.md`. For retention, add headers and matrix notes.

Test impact: Run optional recognition tests, terminology tests, scenario tests,
and full suites. Also grep importers before deletion.

Compatibility risk: Low for documentation. Medium for deletion because
external experiments may import these modules even if runtime code does not.

Gate: Q2.

## D7: `web_server.py` Decomposition

Motivation: `web_server.py` combines app setup, global mutable state, public
routes, operator routes, maintenance routes, emergency routes, metadata
handling, and security gates in one large module.

Design: Introduce an explicit `AppState` container and split routes into
routers by surface: public store/retrieve, operator pages, maintenance,
emergency, and metadata. Keep route paths, request shapes, response bodies,
headers, and neutral filenames unchanged.

Migration steps: First add `AppState` without moving routes. Then move one
router at a time behind compatibility imports. Preserve module-level aliases
used by tests until all tests are migrated. Avoid combining this with UI text
or security-gate changes.

Test impact: `tests/test_web_server.py`, webui leakage tests, restricted-action
tests, Field Mode scenario tests, and full default/optional suites need to run
after every router move.

Compatibility risk: High. This surface is adjacent to Web mutation tokens,
restricted confirmation, hidden routes, Field Mode visibility, response
headers, and capture-visible strings.

Gate: Owner review required before implementation.

## D11: Audit Durability And Chain-State Scaling

Motivation: audit appends currently do not fsync per record or use
inter-process locking, and the next sequence state is derived by reading the
whole log.

Design: Evaluate three options: accept current append semantics and document
the local durability limit; add optional fsync controlled by configuration; or
add advisory file locking plus a compact chain-state sidecar. Any option must
preserve existing record shape and `verify_log_integrity()` compatibility.

Migration steps: Add characterization tests first. If adding a sidecar, make it
rebuildable from `events.log` and never required to verify older logs. If
adding fsync, measure write latency on target hardware before enabling it by
default.

Test impact: audit record-shape tests, multi-record chain verification,
tamper-detection tests, operations export tests, and Pi Zero 2 W performance
validation.

Compatibility risk: Medium for optional fsync; high for sidecar or lock
semantics if they change field-device behavior.

Gate: Q5.

## D14: `operations.py` Split

Motivation: `operations.py` mixes state verification, audit verification,
redacted export, and doctor-like status routines that are reachable from CLI
commands.

Design: Split into `state_ops.py`, `audit_ops.py`, and `export_ops.py`, with
`operations.py` retained as a compatibility shim that re-exports public
functions.

Migration steps: Add new modules with copied functions and no behavior change.
Update internal imports one call site at a time. Keep CLI imports stable until
tests prove equivalence. Remove the shim only in a later owner-approved pass.

Test impact: `tests/test_operations.py`, CLI tests for verification/export
commands, audit tests, state-store tests, and claim coverage.

Compatibility risk: Medium because shell-visible command behavior and
diagnostic wording are capture-visible surfaces.

Gate: Owner review required before implementation.

## D17: `webui_service.py` Lifecycle Redesign

Motivation: WebUI lifecycle management combines process-group termination,
pid-file probing, socket checks, `lsof` fallback, and a daemon timer. Repeated
probes may be expensive and failures are difficult to diagnose.

Design: Introduce a small lifecycle state object that records the last probe
time, process handle, pid-file result, socket result, and startup failure
details. Cache probe results briefly for TUI ticks while keeping explicit
start/stop checks fresh.

Migration steps: Add tests around current start/stop/pid-file behavior. Add
state recording without changing decisions. Then add short-lived caching only
for passive status reads.

Test impact: TUI service tests, WebUI start/stop tests, pid-file cleanup tests,
and manual smoke testing of local WebUI startup.

Compatibility risk: Medium to high because lifecycle behavior is
operator-facing and may affect cleanup after restricted local actions.

Gate: Owner review required before implementation.

## D18: `FileAttemptLimiter` Concurrent Update Locking

Motivation: the file-backed attempt limiter uses read-modify-write state that
can lose updates under concurrent processes.

Design: Consider advisory `flock` around the read/update/write section, with a
fallback path on platforms without `flock`. Keep existing lockout thresholds,
timestamps, response shape, and neutral failure behavior unchanged.

Migration steps: Add a concurrency characterization test with mocked time and a
temporary state file. Implement locking in the narrow file-update section.
Document platform fallback behavior if needed.

Test impact: attempt-limiter tests, WebUI restricted-action tests, CLI access
tests, and scenario tests for neutral failure behavior.

Compatibility risk: Medium because this is a security control and any timing or
locking change could affect deployed operator workflows.

Gate: Owner review required before implementation.

## D19: `LocalStateCipher` Key Derivation

Motivation: `LocalStateCipher` derives local state encryption keys using
SHA-256 over configured or local key material, while vault payload keys use
Argon2id.

Design: Do not change code in a refactor pass. If strengthening is desired,
design a versioned local-state envelope with explicit migration and rollback
behavior. The old format must remain readable until migration is complete.

Migration steps: Define a new state blob version, add compatibility readers,
write new blobs only after explicit migration, and document recovery behavior
if migration is interrupted.

Test impact: local-state crypto tests, object cue store tests, nonce tests,
state-store tests, and field-device migration tests using pre-existing state
fixtures.

Compatibility risk: High. Changing this directly can make existing `.state`
blobs unreadable and would alter local recovery requirements.

Gate: Owner review plus threat-model/specification update required.

## D20: `approval_flow.py` And `roles.py` Integration Or Archive

Motivation: approval and role modules are implemented and tested, but runtime
integration is not active beyond configuration flags. This can imply a
partially delivered authorization feature.

Design: Owner must choose one path: integrate behind an explicit documented
operator workflow; retain as staged work with clear module headers; or archive
until a future issue. Integration must not weaken existing restricted
confirmation or typed confirmation requirements.

Migration steps: For integration, update specification, threat model, CLI/TUI
flows, and tests before enabling behavior. For retention/archive, add headers
and retention-matrix notes only.

Test impact: approval-flow tests, roles tests, restricted-action tests, CLI/TUI
tests, and WebUI mutation-token tests.

Compatibility risk: High if integrated, because this is authorization-adjacent
behavior. Low if only documented as staged work.

Gate: Q4.

## D21: `_ui_unlocked()` And `_guard_page()`

Motivation: `_ui_unlocked()` currently returns `True`, making `_guard_page()`
effectively non-enforcing while documentation still references UI face-lock
session behavior.

Design: Treat this as a product decision, not a refactor. If intentionally
disabled, simplify and document the current posture. If a regression, fix under
a bug issue with tests for lock, unlock, timeout, and capture-visible wording.

Migration steps: Reconcile `docs/THREAT_MODEL.md`, `docs/SPECIFICATION.md`,
AGENTS guidance, WebUI tests, and any operator documentation. Then implement
the chosen behavior in a single-purpose change.

Test impact: WebUI route guard tests, face-lock session tests if re-enabled,
Field Mode visibility tests, and source-leakage tests.

Compatibility risk: High because UI face lock is operator-visible and can be
mistaken for vault encryption if documented poorly.

Gate: Q3.
