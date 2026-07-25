# Local Operations

This document describes repeatable local checks for operators and reviewers.

These commands do not unlock protected entries, do not perform restricted actions, and do not print filesystem paths in normal output.

## Commands

Check local state readiness:

```bash
phasmid verify-state
```

On hosts that expose device-binding inputs, `verify-state` also reports whether local hardware binding material is available and whether a supplemental key-material source has been configured.

Expected neutral output shape:

```text
verify-state: ready
- local_state: ready - local state directory is present
- state_permissions: ready - local state permissions are restricted
```

Check the optional audit log:

```bash
phasmid verify-audit-log
```

If audit logging is disabled or no audit log is present, the command reports `not_enabled`. This is not a failure by itself because audit logging is disabled by default for field deployments.

When audit records include integrity fields, `verify-audit-log` also checks the local verifier material in `.state/events.auth` and reports attention if the verifier material is missing or if record integrity does not validate.

Summarize local health:

```bash
phasmid doctor
```

Export a redacted audit log for review:

```bash
phasmid export-redacted-log --out review-events.jsonl
```

The redacted export uses a fixed schema and omits detailed fields that could reveal file labels, local paths, or operational grouping.

## WebUI Exposure Management

When a graphical interface is required, the operator may "expose" the WebUI. Because this opens a network listener, it is managed with strict exposure controls.

### Procedure

1. **Expose**: Press `w` in the TUI Main Console. Confirm the "WebUI Exposed" notification.
2. **Operate**: Perform necessary tasks via `http://127.0.0.1:8000`.
3. **Retract**: Press `w` again in the TUI. Confirm the shutdown of the WebUI process.

For the normal Protect/Open workflow after the interface is available, use the
[WebUI Operator Guide](WEBUI_OPERATOR_GUIDE.md). That guide is the operator
manual for the Simple Operator dashboard; this document covers exposure
management and local checks.

### Safety Mechanisms

- **Inactivity Auto-Kill**: The TUI monitors operator input. If no keys are pressed for 10 minutes, the WebUI is automatically terminated.
- **Visual Feedback**: The TUI Home Screen displays a prominent warning while the WebUI is active.
- **Process Isolation**: The WebUI runs as a managed subprocess and is terminated cleanly by the TUI on exit or retraction.

## Output Rules

Operational commands should report:

- readiness status;
- neutral check names;
- whether attention is required.

Operational commands should not report:

- local filesystem paths;
- internal storage labels;
- object-cue feature data;
- face-lock template data;
- password-derived data;
- detailed restricted-action failure reasons.

## Test Linkage

The local operations commands are covered by automated tests in `tests/test_operations.py`. Field validation still requires the Field Test Procedure and Seizure Review Checklist.

Restricted-flow procedure coverage is tracked in `tests/scenarios/restricted_flows.json` and validated by `tests/test_scenarios.py`.
