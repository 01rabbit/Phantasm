# Black Hat Europe Arsenal Demo Plan

Internal submission-prep note for event-specific demo packaging. This document is a planning aid and supplemental review artifact, not the event-neutral project overview.

## Demo Positioning

Phasmid is a local-only coercion-aware disclosure-control prototype for constrained devices.

The demo targets Raspberry Pi Zero 2 W-class hardware and equivalent constrained local environments. It is designed around compelled access, device seizure, over-disclosure, and unsafe fail-closed behavior: cases where encrypted storage can be technically correct while the disclosure workflow still creates risk for the person operating it.

Phasmid is not anti-forensics. It does not claim forensic invisibility, forensic-tool bypass, metadata forgery, process hiding, malware-like concealment, or guaranteed secure deletion on flash media.

## Demo Flow

### Demo 1: Local Vessel Creation

Show creation of a local encrypted Vessel and confirm that the workflow does not require a cloud service, remote unlock path, or network dependency.

### Demo 2: Context Profile Selection

Show context profile selection before disclosure preparation. Reviewer-friendly examples include:

- `researcher`
- `travel`
- `field_engineer`
- `maintenance`

### Demo 3: Plausible Dummy Dataset

Show dummy dataset generation and the plausibility report. Explain that dummy data is not decoration; it is part of the controlled-disclosure safety model and must be prepared before any compelled-access scenario.

### Demo 4: Silent Standby

Show Silent Standby clearing sensitive UI state and sealing the session. Direct restoration is not allowed; returning to an active state requires re-authentication.

### Demo 5: Coercion-Safe Fallback

Show the implemented prototype behavior for safer fallback under ambiguous or unsafe access conditions. Current code supports configurable recognition modes and camera-independent routing tests; live camera behavior remains subject to target-hardware field validation.

### Demo 6: Claims and Non-Claims

Show the claims and non-claims documentation. Emphasize:

- no forensic-tool bypass
- no metadata forgery
- no process hiding
- no forensic invisibility claim
- no guaranteed secure deletion on flash media

## Reviewer Takeaways

- Phasmid reframes encrypted storage around compelled-access safety.
- It treats disclosure plausibility and fail-closed behavior as security properties.
- It is a research prototype with explicit claims and non-claims.
- It is suitable for live demonstration because it has visible CLI/TUI flows and local-only behavior.

## Demo Checklist

- Repository opens cleanly.
- `./phasmid` starts.
- TUI opens.
- Demo Vessel can be created.
- Context profile can be selected.
- Dummy report can be generated.
- Silent Standby can be triggered.
- Claims/non-claims are easy to locate.
- No demo requires internet access.
- No sensitive real data is used.
