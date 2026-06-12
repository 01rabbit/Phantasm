# Refactor Report

Branch: `refactor/debt-pass-1`

Instruction artifact: `refactor-instructions.md` was untracked at start and
was explicitly approved by the owner as the authoritative instruction artifact.
It remains untracked and is not included in this refactor branch.

## Summary

Completed:

- Phase 0 baseline on Python 3.10 after an initial environment probe found that
  `bash -lc` picked up Python 3.7.
- Phase 1 safety-net tests for container constants, local state crypto, and
  LUKS wrapper behavior.
- Phase 2 safe cleanup items: fixed the `AGENTS.md` face-lock reference,
  removed the dead mypy override entry, centralized container format constants,
  guarded the crypto self-test flag, and labeled evaluation recognition modules.
- Phase 3 small separation items: confirmed D8 service wrappers were already
  one-line delegates, centralized state directory setup, and cached TUI vessel
  entropy inspection by path, mtime, and size.
- Phase 4 boundary items: annotated `vault_core.py`, added debug logging to
  silent local failure paths, narrowed metadata scrub parse exceptions, and
  documented threading contracts.
- Phase 5 typed `ai_gate.py` enough to remove its mypy `ignore_errors`
  override.
- Phase 6 proposal-only items in
  `docs/archive/REFACTOR_PROPOSALS.md`.

Skipped or no-op:

- D8 required no code: `audit_service`, `doctor_service`, `guided_service`, and
  `inspection_service` already had module-level canonical implementations with
  class wrappers delegating to them.
- D11 production changes were not implemented because durability and locking
  are gated by Q5; existing audit tests already covered record shape,
  multi-record verification, tamper detection, and deleted-record detection.
- D2, D3 deletions, D7, D11 implementation, D14, D17, D18, D19, D20, and D21
  remain proposal-only or owner-gated as directed.

No new stop-and-ask conditions were encountered after the owner approved
proceeding with the untracked instruction artifact.

## Commits

- `9eb43a6 Add refactor safety-net tests`
- `ed4c354 Fix AGENTS face-lock reference`
- `93bb83a Centralize container format constants`
- `c94983b Guard crypto self-test flag`
- `9014293 Label object recognition evaluation modules`
- `2bc19d5 Centralize state directory setup`
- `4cca140 Cache TUI vessel entropy inspection`
- `bc2c43a Annotate vault core API`
- `6fb4c55 Log silent local failure paths`
- `ff73628 Document threaded runtime contracts`
- `bd4a41f Annotate AI gate and enable mypy`
- `d66ac74 Add refactor follow-up proposals`
- final reporting commit: `Add refactor completion report`

## Per-Phase Log

### Phase 0

Files touched: none.

Baseline command log: `/tmp/phasmid-refactor-baseline-py310.log`.

Results:

- `black --check`: pass (`No Python files are present to be formatted`)
- `ruff`: pass
- `mypy src`: pass
- `compileall`: pass
- `bandit`: pass
- `tests`: 449 tests, 5 skipped, pass
- `tests_optional`: 124 tests, pass
- `coverage --fail-under=70`: 71%, pass
- claims coverage: total 39, test 33, manual 6, unverified 0, pass

### Phase 1

Commit: `9eb43a6 Add refactor safety-net tests`

Files touched:

- `tests/test_container_format_constants.py`
- `tests/test_local_state_crypto.py`
- `tests/test_luks_layer.py`

Verification:

- Targeted added tests: 10 tests, pass
- Phase log: `/tmp/phasmid-refactor-phase1.log`
- `ruff`: pass
- `mypy src`: pass
- `tests`: 459 tests, 5 skipped, pass
- `tests_optional`: 124 tests, pass
- `coverage --fail-under=70`: 71%, pass

### Phase 2

Commits:

- `ed4c354 Fix AGENTS face-lock reference`
- `93bb83a Centralize container format constants`
- `c94983b Guard crypto self-test flag`
- `9014293 Label object recognition evaluation modules`

Files touched:

- `AGENTS.md`
- `pyproject.toml`
- `src/phasmid/container_layout.py`
- `src/phasmid/crypto_boundary.py`
- `src/phasmid/crypto_params.py`
- `src/phasmid/lightweight_object_matcher.py`
- `src/phasmid/recognition_benchmark.py`
- `src/phasmid/record_cypher.py`
- `tests/test_container_format_constants.py`

Verification:

- D4: `mypy src`, `ruff`, pass
- D1: container format, layout, record cipher, vault core, headerless invariant
  tests, pass
- D12: `tests.test_crypto_boundary`, pass
- D3 label-only: optional lightweight matcher and recognition benchmark tests,
  pass
- Phase log: `/tmp/phasmid-refactor-phase2.log`
- `ruff`: pass
- `mypy src`: pass
- `tests`: 459 tests, 5 skipped, pass
- `tests_optional`: 124 tests, pass
- `coverage --fail-under=70`: 71%, pass

### Phase 3

Commits:

- `2bc19d5 Centralize state directory setup`
- `4cca140 Cache TUI vessel entropy inspection`

Files touched:

- `src/phasmid/audit.py`
- `src/phasmid/config.py`
- `src/phasmid/state_store.py`
- `src/phasmid/tui/widgets/status_panel.py`
- `tests/test_tui.py`

Verification:

- D8: no-op after inspection; wrappers already delegated.
- D15: config, audit, operations, state-store tests, pass
- D9: status-panel entropy cache test, pass
- Phase log: `/tmp/phasmid-refactor-phase3.log`
- `ruff`: pass
- `mypy src`: pass
- `tests`: 460 tests, 5 skipped, pass
- `tests_optional`: 124 tests, pass
- `coverage --fail-under=70`: 72%, pass

### Phase 4

Commits:

- `bc2c43a Annotate vault core API`
- `6fb4c55 Log silent local failure paths`
- `ff73628 Document threaded runtime contracts`

Files touched:

- `src/phasmid/ai_gate.py`
- `src/phasmid/audit.py`
- `src/phasmid/camera_frame_source.py`
- `src/phasmid/config.py`
- `src/phasmid/metadata.py`
- `src/phasmid/object_cue_store.py`
- `src/phasmid/record_cypher.py`
- `src/phasmid/services/profile_service.py`
- `src/phasmid/services/webui_service.py`
- `src/phasmid/state_store.py`
- `src/phasmid/vault_core.py`

Verification:

- D6: vault core and record cipher tests, pass
- D10: audit, state store, operations, TUI, metadata, source-leakage, ai gate,
  object gate, scenario tests, pass
- D10 forbidden-term diff grep for touched files: no hits
- Threading docstrings: TUI and ai gate tests, pass
- Phase log: `/tmp/phasmid-refactor-phase4.log`
- `ruff`: pass
- `mypy src`: pass
- `tests`: 460 tests, 5 skipped, pass
- `tests_optional`: 124 tests, pass
- `coverage --fail-under=70`: 72%, pass

### Phase 5

Commit: `bd4a41f Annotate AI gate and enable mypy`

Files touched:

- `pyproject.toml`
- `src/phasmid/ai_gate.py`

Verification:

- Temporary override-free mypy config for `ai_gate.py`: pass
- Normal `mypy src` after removing override: pass
- `tests_optional.test_ai_gate`: 23 tests, pass
- Phase log: `/tmp/phasmid-refactor-phase5.log`
- `ruff`: pass
- `mypy src`: pass
- `tests`: 460 tests, 5 skipped, pass
- `tests_optional`: 124 tests, pass
- `coverage --fail-under=70`: 72%, pass

### Phase 6

Commit: `d66ac74 Add refactor follow-up proposals`

Files touched:

- `docs/archive/REFACTOR_PROPOSALS.md`

Verification:

- Proposal diff forbidden-term grep: no hits
- `ruff`: pass
- `mypy src`: pass

## Baseline Vs Final

| Gate | Baseline | Final |
|---|---:|---:|
| `black --check` | pass | pass |
| `ruff` | pass | pass |
| `mypy src` | pass, 87 files | pass, 87 files |
| `compileall` | pass | pass |
| `bandit` | pass | pass |
| default tests | 449, skipped 5, pass | 460, skipped 5, pass |
| optional tests | 124, pass | 124, pass |
| coverage gate | 71%, pass | 72%, pass |
| claims coverage | 0 unverified, pass | 0 unverified, pass |

Initial environment note: a first baseline attempt under `bash -lc` used
Python 3.7 and failed because tools were unavailable and the code requires
Python >=3.10 syntax. The authoritative baseline and final runs used the
repository shell's Python 3.10 environment.

## Questions Raised

No new questions were raised. Existing owner-gated questions remain:

- Q1: `kdf_subkeys.py` disposition.
- Q2: unused recognition module deletion approval.
- Q3: `_ui_unlocked()` and `_guard_page()` product decision.
- Q4: `approval_flow.py` and `roles.py` integration or archive.
- Q5: audit durability and locking policy.

## Proposals

Phase 6 proposals are in `docs/archive/REFACTOR_PROPOSALS.md` and cover D2,
D3 deletions, D7, D11, D14, D17, D18, D19, D20, and D21.

## Command Transcript

Full stdout logs were written during the run:

- `/tmp/phasmid-refactor-baseline.log` - initial Python 3.7 environment probe,
  failed as expected for the wrong interpreter.
- `/tmp/phasmid-refactor-baseline-py310.log` - authoritative baseline.
- `/tmp/phasmid-refactor-phase1.log`
- `/tmp/phasmid-refactor-phase2.log`
- `/tmp/phasmid-refactor-phase3.log`
- `/tmp/phasmid-refactor-phase4.log`
- `/tmp/phasmid-refactor-phase5.log`
- `/tmp/phasmid-refactor-final.log`
- `/tmp/phasmid-refactor-final-after-report.log` - authoritative final run
  after the report file was committed.
- `/tmp/phasmid-refactor-final-head.log` - final run against latest HEAD.

Verification command outcomes:

```text
git status -> pass; only approved untracked refactor-instructions.md present
git log --oneline -3 -> pass
python3 -m black --check src tests scripts -> pass
python3 -m ruff check src tests scripts -> pass
python3 -m mypy src -> pass
python3 -m compileall -q src tests scripts -> pass
python3 -m bandit -r src -q --severity-level medium --confidence-level high -> pass
python3 -m coverage erase -> pass
python3 -m coverage run --source=src -m unittest discover -s tests -> pass
python3 -m coverage run --append --source=src -m unittest discover -s tests_optional -> pass
python3 -m coverage report --fail-under=70 -> pass, 72%
python3 scripts/check_claims_coverage.py --claims-file docs/CLAIMS.md --tests-dir tests --output /tmp/phasmid-claims-final.json --max-unverified 8 -> pass, 0 unverified
git diff main --check -> pass
forbidden-term diff grep from the refactor directive -> internal/code-context hits only; no new user-visible prohibited language
```
