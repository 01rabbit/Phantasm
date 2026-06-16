# Coercion-Safe Delaying Architecture

## Overview

Phasmid implements a coercion-safe delaying architecture to increase uncertainty,
delay confident conclusions, separate coerced disclosure from true disclosure, and
improve operator survivability in hostile or coercive environments.

This architecture does not claim permanent secrecy against unlimited forensic
analysis. Its purpose is to avoid immediate proof, increase investigation cost
and time, and provide plausible controlled disclosure under stress, coercion, or
opportunistic inspection.

---

## Design Principles

- Prioritize survivability over perfect secrecy.
- Avoid obvious failure states under coercion.
- Prefer plausible ambiguity over active deception.
- Use pre-consistent disclosure profiles instead of emergency fake generation.
- Avoid claims of forensic invisibility.
- Avoid anti-forensic or malware-like behavior.
- Treat delay and uncertainty as defensive mechanisms.

---

## Security Claims

| Claim | Description |
|---|---|
| Separation of coerced from true disclosure | Coerced disclosure path uses a pre-configured dummy profile that is operationally separate from the true disclosure path. |
| Immediate proof avoidance | No single action or observation confirms or denies the existence of protected content. |
| Increased analysis cost | An adversary must invest time to distinguish dummy content from protected content. |
| Pre-consistent disclosure | Dummy profiles are configured and populated before any coercive event, not generated on demand. |
| Local-only operation | All standby, dummy, and profile operations are local. No network calls are introduced. |
| Natural coercion-safe flow | Standby and dummy disclosure transitions do not require suspicious rapid key sequences or visible "panic" indicators. |

---

## Non-Claims

- Phasmid does not guarantee permanent secrecy against a capable forensic examiner
  with unlimited time and resources.
- Phasmid does not claim that dummy content is indistinguishable under forensic analysis.
- Phasmid does not forge or tamper with filesystem metadata, kernel logs, or timestamps.
- Phasmid does not conceal the existence of the software itself.
- Phasmid does not provide coercion-proof operation; survivability is a probabilistic
  improvement, not an absolute guarantee.
- Silent Standby does not erase data; it removes it from the visible UI surface only.
- Recovery from standby requires re-authentication; no automatic re-entry is provided.

---

## Assumptions

- The operator has pre-populated a plausible dummy profile before any coercive event.
- The dummy profile is internally consistent: file types, sizes, and directory structure
  match the declared context profile.
- The operator activates standby before a coercive party reaches the active UI state.
- The hardware form factor does not itself attract hostile inspection.
- The host operating system is not compromised at the time of standby activation.

---

## Known Limitations

- Standby transition is a UI-layer operation. It does not erase key material from memory.
- A live memory capture performed after standby activation but before process exit may
  still expose in-memory key material.
- Dummy content plausibility depends entirely on operator preparation; a trivially empty
  or structurally inconsistent dummy profile reduces survivability.
- Recognition confidence routing (coercion_safe mode) routes low-confidence recognition
  to dummy disclosure but does not verify physical coercion context.
- The dummy plausibility report is a local advisory tool; it does not verify adversarial
  perception.

---

## Three-Component Architecture

### 1. Silent Standby

Silent Standby provides a coercion-safe transition from a sensitive UI state to a
non-sensitive standby state.

States:

```text
active          - Normal operation; sensitive UI visible.
standby         - Sensitive UI cleared; non-sensitive screen displayed.
sealed          - Session sealed; re-authentication required to return to active.
dummy_disclosure - Operator is presenting dummy content as the apparent data.
```

Transition rules:

- `active → standby`: Triggered by configurable hotkey (default: Ctrl+S).
- `standby → sealed`: Automatic; standby always seals the session.
- `sealed → active`: Requires re-authentication; direct re-entry to prior state is disallowed.
- `sealed → dummy_disclosure`: Coercion-safe mode routes naturally toward dummy path.

What standby clears:

- Visible sensitive content in the TUI.
- True-profile UI references.
- Temporary display buffers.

What standby does NOT do:

- Erase key material from process memory.
- Prevent a live memory capture from recovering in-use key material.
- Fabricate system events or fake log entries.
- Hide the Phasmid process from the process list.

### 2. Plausible Dummy Dataset

Dummy datasets provide a disclosure-ready alternative content set that can plausibly
stand alone without the true protected content being visible or required.

Dummy content rules:

- Generated or imported before any coercive event.
- Context-consistent: file types and directory structure match the declared context profile.
- Occupancy ratio must be plausible relative to the container size.
- File count and size distribution must be realistic for the declared context.

Explicit restrictions:

- No forged forensic artifacts.
- No fake kernel logs or system event fabrication.
- No timestamp forgery or anti-forensic metadata tampering.
- No intentional forensic-tool deception.
- No malware-like behavior.

### 3. Context Profile Templates

Context profiles define the expected content structure for a given operational context.
They guide dummy generation and provide plausibility validation.

Built-in profiles:

| Profile | Intended Use | Typical Content |
|---|---|---|
| `travel` | Travel data carrier | Images, itinerary, notes, receipts |
| `field_engineer` | Engineering field work | Logs, configs, exported diagnostics, manuals |
| `researcher` | Research material | PDFs, notes, references, exported datasets |
| `maintenance` | Device maintenance | Diagnostic exports, system check results, update files |
| `archive` | Long-term archive | Documents, media, backups |

---

## Coercion-Safe Recognition Fallback

Recognition mode controls how the system responds to low-confidence or failed recognition.
This is a prototype routing behavior implemented in the local object-cue path and
covered by camera-independent tests. Live camera behavior still requires target
hardware field validation.

| Mode | Behavior |
|---|---|
| `strict` | Mismatch → failure |
| `coercion_safe` | Low confidence → dummy disclosure path |
| `demo` | Safe debug visibility |

In `coercion_safe` mode:

- Low recognition confidence routes to dummy disclosure rather than returning an obvious
  access-denied error.
- Repeated recognition instability also routes to dummy disclosure.
- The transition is natural and does not produce visible "access denied" loops.
- This routing does not detect coercion, verify intent, or prove that the operator
  is under pressure.

Failure handling rules:

- Repeated obvious lockout messages are avoided.
- Aggressive error messages are avoided.
- Visible "access denied" cycling is avoided.

---

## Allowed and Disallowed Behaviors

### Allowed

- Plausible dummy disclosure using pre-configured content.
- Privacy-preserving standby transitions that remove sensitive UI state.
- Ambiguity-preserving workflows where no single observation confirms or denies.
- Local-only operation with no network side effects.
- Configurable hotkey-triggered standby.
- Context-profile-guided dummy structure.
- Local plausibility reports for operator self-assessment.

### Disallowed

- Rootkits or kernel-level hiding mechanisms.
- Hidden process persistence.
- Anti-forensic data destruction triggered by coercion detection.
- Forensic tool bypass or interference.
- Malware-like concealment behavior.
- False system event fabrication.
- Timestamp forgery.
- Fake law enforcement or intrusion log generation.
- Anti-forensic metadata tampering.

---

## Operational Guidance

Before deployment in any environment where coercion is a realistic risk:

1. Select a context profile appropriate to the operational context.
2. Populate the dummy dataset with plausible, context-consistent content.
3. Run the dummy plausibility report and resolve all warnings.
4. Test the standby transition to confirm it clears the sensitive UI.
5. Confirm that re-authentication is required to return from standby.
6. Review the Seizure Review Checklist (`docs/SEIZURE_REVIEW_CHECKLIST.md`).

---

## References

- `docs/THREAT_MODEL.md` — threat model and adversary definitions
- `docs/NON_CLAIMS.md` — explicit non-claims inventory
- `docs/CLAIMS.md` — claims inventory
- `docs/SEIZURE_REVIEW_CHECKLIST.md` — seizure-condition review checklist
- `docs/FIELD_TEST_PROCEDURE.md` — field testing procedures
- `docs/JANUS_EIDOLON_SYSTEM.md` — two-slot architecture specification
