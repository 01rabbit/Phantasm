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
- Rely on the operator's own pre-stored decoy for disclosure, and fill free space
  in advance, rather than fabricating anything on demand under pressure.
- Avoid claims of forensic invisibility.
- Avoid anti-forensic or malware-like behavior.
- Treat delay and uncertainty as defensive mechanisms.

---

## Security Claims

| Claim | Description |
|---|---|
| Separation of coerced from true disclosure | Coerced disclosure opens the operator's own decoy file, stored in a Face that is operationally separate from the protected Face. |
| Immediate proof avoidance | No single action or observation confirms or denies the existence of protected content. |
| Increased analysis cost | An adversary must invest time to distinguish the disclosed Face from the protected Face. |
| Pre-consistent disclosure | The operator's decoy is stored, and free space is optionally filled, before any coercive event — neither is generated on demand under pressure. |
| Local-only operation | All standby, filler, and profile operations are local. No network calls are introduced. |
| Natural coercion-safe flow | Standby and decoy-disclosure transitions do not require suspicious rapid key sequences or visible "panic" indicators. |

---

## Non-Claims

- Phasmid does not guarantee permanent secrecy against a capable forensic examiner
  with unlimited time and resources.
- Phasmid does not claim that the operator's decoy content is indistinguishable from
  the protected content under forensic analysis, and it does not judge whether that
  decoy is convincing — that judgment belongs to the operator who wrote it.
- Phasmid does not forge or tamper with filesystem metadata, kernel logs, or timestamps.
- Phasmid does not conceal the existence of the software itself.
- Phasmid does not provide coercion-proof operation; survivability is a probabilistic
  improvement, not an absolute guarantee.
- Silent Standby does not erase data; it removes it from the visible UI surface only.
- Recovery from standby requires re-authentication; no automatic re-entry is provided.

---

## Assumptions

- The operator has stored their own decoy file in the disclosure Face before any
  coercive event, and has optionally filled free space so the container does not read
  as empty.
- The decoy is realistic because the operator prepared it themselves; Phasmid does not
  fabricate it, vouch for it, or judge how convincing it is.
- The operator activates standby before a coercive party reaches the active UI state.
- The hardware form factor does not itself attract hostile inspection.
- The host operating system is not compromised at the time of standby activation.

---

## Known Limitations

- Standby transition is a UI-layer operation. It does not erase key material from memory.
- A live memory capture performed after standby activation but before process exit may
  still expose in-memory key material.
- The credibility of the disclosed decoy depends entirely on the operator's own
  preparation; Phasmid does not assess it. A container that reads as suspiciously
  empty reduces survivability, which is why filling free space is recommended.
- Recognition confidence routing (coercion_safe mode) routes low-confidence recognition
  to decoy disclosure but does not verify physical coercion context.
- The Free Space Filler occupancy report is a local advisory tool measuring volume; it
  does not verify adversarial perception or judge believability.

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
dummy_disclosure - Operator is presenting their own stored decoy as the apparent data.
```

Transition rules:

- `active → standby`: Triggered by configurable hotkey (default: Ctrl+S).
- `standby → sealed`: Automatic; standby always seals the session.
- `sealed → active`: Requires re-authentication; direct re-entry to prior state is disallowed.
- `sealed → dummy_disclosure`: Coercion-safe mode routes naturally toward the operator's decoy.

What standby clears:

- Visible sensitive content in the TUI.
- True-profile UI references.
- Temporary display buffers.

What standby does NOT do:

- Erase key material from process memory.
- Prevent a live memory capture from recovering in-use key material.
- Fabricate system events or fake log entries.
- Hide the Phasmid process from the process list.

### 2. Free Space Filler

The disclosure-ready content is the operator's own file: something that looks like the
real thing, stored by the operator in the disclosure Face under the decoy passphrase.
Phasmid never fabricates it. A tool-generated dataset has no credibility as a cover
story, and it is not what the operator would actually be handing over under pressure.

The Free Space Filler is a separate, optional step. It fills unused space in a Face so
an otherwise-empty container does not read as suspiciously empty. It is not disclosure
material, it is never shown or handed over, and it does not stand in for the operator's
decoy.

Filler rules:

- Generated only to occupy free space, before any coercive event.
- Context-consistent: file types and directory structure follow the declared context
  profile, for occupancy purposes only.
- Reported as occupancy ratio relative to the container size, file count, and size
  distribution — a volume measurement, not a plausibility verdict.

Explicit restrictions:

- No forged forensic artifacts.
- No fake kernel logs or system event fabrication.
- No timestamp forgery or anti-forensic metadata tampering.
- No intentional forensic-tool deception.
- No malware-like behavior.

### 3. Context Profile Templates

Context profiles define the expected content structure for a given operational context.
They guide the optional free-space filler's content. They do not validate whether the
operator's own disclosure material is plausible — the tool measures volume, and judging
whether a cover story is convincing is the operator's job, not the tool's.

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

- Disclosure of the operator's own pre-stored decoy content.
- Privacy-preserving standby transitions that remove sensitive UI state.
- Ambiguity-preserving workflows where no single observation confirms or denies.
- Local-only operation with no network side effects.
- Configurable hotkey-triggered standby.
- Context-profile-guided free-space filler structure.
- Local free-space occupancy reports for operator self-assessment.

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

1. Select a context profile appropriate to the operational context (it shapes the
   optional free-space filler, not the operator's own disclosure material).
2. Store your own decoy file in the disclosure Face — Phasmid does not generate it.
3. Optionally fill free space and resolve any occupancy warnings from the report.
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
