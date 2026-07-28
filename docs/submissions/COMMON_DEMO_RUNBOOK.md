# Common Demo Runbook

This runbook is the mandatory sequence for all concept tracks.

## Demo Goal

Show Phasmid as a local-only coercion-aware storage prototype for constrained devices, with explicit claims and non-claims.

## Fixed Sequence

1. Vessel/container creation
2. Context profile selection
3. Operator-supplied decoy placement, plus optional free-space filling
4. Silent Standby transition
5. Coercion-safe fallback behavior
6. Claims/non-claims display

## Operator Script (Concise)

### 1) Vessel creation

- Open TUI Operator Console.
- Create a vessel.
- Verify local-only posture and local state path.

Speak line:
`This vessel is local-only and does not require cloud services.`

### 2) Context profile selection

- Select one built-in profile.
- Show profile intent and expected file distribution.

Speak line:
`Profile selection shapes the optional free-space filler, not cryptographic keys and not the operator's own disclosure material.`

### 3) Operator-supplied decoy and free-space fill

- Store the operator's own decoy file in the disclosure Face — Phasmid does not generate it.
- Optionally run Fill Free Space and show the occupancy report.
- Show warnings if occupancy is low or sparse.

Speak line:
`The decoy is the operator's own file, prepared in advance; the filler only occupies free space and is never disclosure material.`

### 4) Silent Standby

- Trigger standby hotkey.
- Show sensitive UI cleared.
- Confirm re-authentication is required.

Speak line:
`Silent Standby removes sensitive UI surface; it is not memory erasure.`

### 5) Coercion-safe fallback

- Demonstrate low-confidence/ambiguous path.
- Show fallback behavior that avoids obvious unsafe lockout loops.

Speak line:
`Fallback prioritizes safer disclosure behavior under pressure.`

### 6) Claims/non-claims display

- Open claims list and non-claims list.
- Read 2-3 non-claims explicitly.

Speak line:
`This prototype does not claim anti-forensic invisibility or guaranteed secure deletion.`

## Required Safety Language

- Use `passphrase`, `object cue`, `local access path`, `best-effort`.
- Avoid `self-destruct`, `secure delete`, `anti-forensics`, `investigator deception`.

## Evidence Checklist

- Screenshot of each step
- One full session screen capture
- One constrained-device run confirmation
- Exact version/tag used in demo
