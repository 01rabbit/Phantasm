# Phasmid Architecture

Phasmid is a field-evaluation prototype for local-only coercion-aware storage and the reference implementation of the Janus Eidolon System.

![Phasmid architecture overview](images/architecture_v1.png)

Two-slot architecture overview: vessel structure, disclosure faces, local key material, and object-cue operating boundary.

## Architectural Layers

Phasmid is organized into a few narrow local layers:

1. CLI and WebUI entry points coordinate local operations without exposing internal disclosure structure in normal capture-visible flows.
2. Restricted-action policy checks enforce confirmation, timing, and capability requirements for sensitive local updates.
3. The cryptographic core manages `vault.bin`, key derivation, container layout, record encryption, and local access-key mixing.
4. Local state modules manage typed state, attempt limiting, object-cue material, and optional audit records.
5. Deployment and review documents define the operating boundary for field evaluation and appliance hardening.

## Naming Boundary

Phasmid is the only active product and implementation name in this repository.

- Python package: `src/phasmid`
- Console script: `phasmid`
- WebUI module path: `python3 -m phasmid.web_server`
- Environment variables: `PHASMID_*`

The repository does not keep legacy import paths, wrapper modules, or environment-variable aliases.

## Local Security Boundary

The architecture preserves these constraints:

- `vault.bin` alone is not sufficient for normal recovery when required local state is absent
- object cues are operational access cues, not cryptographic secrets
- an experimental lightweight local object model may contribute neutral status signals to object-cue policy, but it is disabled by default and is not cryptographic material
- hidden routes are UX concealment, not access control
- restricted actions require server-side checks and explicit confirmation
- Field Mode reduces exposure but is not a security boundary

## Coercion-Safe Delaying Architecture

Phasmid implements a three-component coercion-safe delaying architecture:

1. **Silent Standby** — Transitions from sensitive UI state to non-sensitive standby
   on a configurable hotkey. States: `active`, `standby`, `sealed`, `dummy_disclosure`.
   Recovery requires re-authentication. Standby does not erase key material from memory.

2. **Plausible Dummy Dataset** — Pre-configured context-consistent content for
   controlled disclosure. Generated before any coercive event. Guided by context
   profiles. Evaluated by the plausibility report.

3. **Context Profile Templates** — Schemas that define expected content for a given
   operational context (`travel`, `field_engineer`, `researcher`, `maintenance`,
   `archive`). Guide dummy generation and plausibility validation.

Recognition modes control response to low-confidence recognition:

- `strict` — mismatch is a failure
- `coercion_safe` — low confidence routes to dummy disclosure path
- `demo` — safe debug visibility

This architecture does not claim forensic invisibility. It increases uncertainty,
delays confident conclusions, and avoids obvious failure states under coercion.

See `docs/COERCION_SAFE_DELAYING.md` for full design documentation.

## Current Documentation Map

- [SPECIFICATION.md](SPECIFICATION.md) defines implementation behavior and configuration.
- [THREAT_MODEL.md](THREAT_MODEL.md) defines assumptions, residual risk, and safety boundaries.
- [JANUS_EIDOLON_SYSTEM.md](JANUS_EIDOLON_SYSTEM.md) defines the formal two-slot architecture.
- [README.md](../README.md) defines the user-facing tool summary and operational limits.
