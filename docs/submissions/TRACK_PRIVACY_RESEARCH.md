# Track Package: Privacy-and-Research

## Positioning

Use this framing for audiences prioritizing privacy, disclosure ethics, and transparent research boundaries.

## Title and Subtitle

Title:
`Phasmid: Coercion-Safe Deniable Storage for Constrained Devices`

Subtitle:
`Protecting the person who may be forced to disclose the data`

## Abstract (Template)

Phasmid is a local-only coercion-aware storage prototype for Raspberry Pi Zero 2 W-class constrained devices. Conventional encryption protects data from unauthorized access, but compelled-access scenarios shift risk to the person who may be forced to disclose credentials or explain encrypted storage. Phasmid explores whether disclosure behavior can reduce unsafe over-disclosure while keeping claims and non-claims explicit.

The system implements Janus Eidolon System (JES), a two-slot local disclosure architecture that separates visible disclosure from protected local state. It combines context profile templates, plausible disclosure datasets, Silent Standby transitions, and coercion-safe fallback behavior.

Phasmid is not anti-forensics and does not claim permanent secrecy against unlimited analysis. The demo focuses on local-only operation, controlled disclosure, and transparent safety boundaries.

## Preferred Keywords

- compelled access
- over-disclosure reduction
- privacy-preserving disclosure
- local-only operation
- transparent non-claims

## Language to Avoid

- anti-forensics
- deceive investigators
- forensic evasion
- covert communication

## Demo Mapping

Follow [`COMMON_DEMO_RUNBOOK.md`](COMMON_DEMO_RUNBOOK.md) with profile examples such as:

- `researcher`
- `travel`
- `archive`
