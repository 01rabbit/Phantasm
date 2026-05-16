# Phasmid Concept Track Guardrails

This document is an internal baseline for concept-track work.
It is intentionally minimal and not a final submission template.

## Fixed Core Message

Phasmid is a coercion-aware local storage prototype for constrained devices.  
It asks whether encryption can protect not only data, but also the person who may be forced to disclose it.

## Internal Track Labels

- `privacy-and-research`
- `field-operations`

These labels change framing only. They do not change security claims, implementation boundaries, or non-claims.

## Go/No-Go Checklist

Use this checklist before any external-facing copy is approved.

### 1) Claim Drift Check

Go only if all statements are backed by existing sources:

- [`CLAIMS.md`](CLAIMS.md)
- [`THREAT_MODEL.md`](THREAT_MODEL.md)
- [`SPECIFICATION.md`](SPECIFICATION.md)

No-go if text introduces unverified capability, performance guarantee, or new security promise.

### 2) Language Boundary Check

Go only if wording remains neutral and capture-safe per project language rules.

No-go if copy uses or implies:

- anti-forensics as headline
- investigator deception claims
- secure deletion guarantees
- covert communication or surveillance evasion

### 3) Non-Claim Integrity Check

Go only if non-claims remain explicit and unchanged from:

- [`NON_CLAIMS.md`](NON_CLAIMS.md)

No-go if text weakens or omits existing non-claims, especially around:

- perfect deniability
- guaranteed secure deletion
- compromised host resistance
- live memory capture resistance
- remote management/remote wipe/remote unlock

### 4) Scope Check

Go only if the text stays within local-only constrained-device storage scope.

No-go if framing expands into remote control, telemetry, offensive capability, or policy claims outside project boundary.

## Working Draft Assets

Internal draft materials are in [`submissions/`](submissions/README.md).
