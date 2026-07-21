# Submission Package (Concept-Only)

This directory provides reusable submission assets with no event or region names.
All files here are internal working drafts, not finalized external submission text.

Use these files to keep one technical core while adjusting audience framing:

- [`COMMON_DEMO_RUNBOOK.md`](COMMON_DEMO_RUNBOOK.md): shared live demo script (fixed sequence)
- [`TRACK_PRIVACY_RESEARCH.md`](TRACK_PRIVACY_RESEARCH.md): privacy-and-research framing package
- [`TRACK_FIELD_OPERATIONS.md`](TRACK_FIELD_OPERATIONS.md): field-operations framing package

DEF CON Demo Labs package (event-specific example built on the shared core):

- [`DEFCON_DEMO_LABS_RUNBOOK.md`](DEFCON_DEMO_LABS_RUNBOOK.md): operator demo runbook — demo profile with purpose, modes, pre-demo checklist, step-by-step sequence, talk track, and failure fallback
- [`DEFCON_DEMO_LABS_SCRIPT.md`](DEFCON_DEMO_LABS_SCRIPT.md): companion speaker script (talk track + staging cues)
- [`Phasmid_DEFCON_DemoLabs.pptx`](Phasmid_DEFCON_DemoLabs.pptx): 24-slide Demo Labs station deck (with speaker notes)

## Regional Mapping Guidance

Use the same technical core and demo order for every region, then adjust framing only:

- Europe-oriented submissions: start from `TRACK_PRIVACY_RESEARCH.md`
  - Recommended title: `Phasmid: Coercion-Safe Deniable Storage for Constrained Devices`
  - Emphasis: compelled-access safety, over-disclosure reduction, explicit claims/non-claims
- MEA-oriented submissions: start from `TRACK_FIELD_OPERATIONS.md`
  - Recommended title: `Phasmid: Field-Ready Coercion-Aware Storage for Constrained Devices`
  - Emphasis: constrained-device field readiness, operational resilience, safe fallback behavior

## Reuse-Risk Control

To avoid appearing as duplicate submissions across regions:

- keep a fixed shared demo sequence in `COMMON_DEMO_RUNBOOK.md`
- change audience framing, examples, and abstract wording by track
- include a visible "what changed since prior submission" note in each final package

Suggested internal release labels:

- `Coercion-Safe Disclosure Edition` (privacy/research-first package)
- `Field Operations Edition` (field-operations-first package)

Draft handling rules:

- Do not copy-paste these files as final public abstracts without review.
- Validate all wording against claims/non-claims before external use.
- Keep final event-specific constraints in a separate review step.

All text in this folder must stay aligned with:

- [`../THREAT_MODEL.md`](../THREAT_MODEL.md)
- [`../CLAIMS.md`](../CLAIMS.md)
- [`../NON_CLAIMS.md`](../NON_CLAIMS.md)
- [`../SPECIFICATION.md`](../SPECIFICATION.md)
