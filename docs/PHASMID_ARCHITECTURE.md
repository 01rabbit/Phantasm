# Phasmid Architecture

Phasmid is a field-evaluation prototype for local-only coercion-aware storage and the reference implementation of the Janus Eidolon System.

![Phasmid architecture overview](images/architecture_v1.png)

Two-slot architecture overview: vessel structure, disclosure faces, local key material, and object-cue operating boundary.

## Architectural Layers

Phasmid is organized into a few narrow local layers:

1. The TUI operator console, CLI, and WebUI entry points coordinate local operations without exposing internal disclosure structure in normal capture-visible flows. The TUI console owns Vessel lifecycle (creation and deletion); the WebUI and TUI both operate on an already-created Vessel day to day (store, retrieve). See "Vessel Model" below.
2. Restricted-action policy checks, and role-scoped WebUI access tokens (store vs. recover), enforce confirmation, timing, and capability requirements for sensitive local updates and for which WebUI surfaces a given session can reach at all.
3. The cryptographic core manages Vessel containers (`*.vessel`) and the legacy single-container `vault.bin` fallback, key derivation, container layout, record encryption, and local access-key mixing.
4. Local state modules manage typed state, attempt limiting, object-cue material, and optional audit records.
5. Deployment and review documents define the operating boundary for field evaluation and appliance hardening.

## Vessel Model

A Vessel (`*.vessel`) is the concrete, operator-facing container that implements the Janus Eidolon two-slot model: each Vessel holds exactly two disclosure Faces (`face_a`/`face_b`, shown as Entry 1/Entry 2 in the WebUI), each independently protected by its own passphrase and physical object cue. An operator can create and hold more than one Vessel at a time; `VesselWorkflowService` is the shared entry point both the TUI and the WebUI use for all Vessel and Face operations (create, delete, store, retrieve, list, remove).

Vessel lifecycle is a TUI-only responsibility: the TUI creates a Vessel and its Faces, and Delete Vessel (TUI Expert Home) is the only path that permanently scrambles and removes a Vessel file, freeing its disk space, when an operator is finished with it. This is deliberate, not incidental — a Vessel is a self-contained container the operator carries a specific mental model of ("this is the thing I made and will eventually delete"), and folding creation or deletion into the WebUI would blur that boundary for a surface designed to be exposed over a USB gadget link. The WebUI's role is limited to operating on a Vessel that already exists: registering a Face's credentials (store role) and decrypting or destroying (recover role).

The physical-object cue store is a device-wide singleton (`AIGate` / `access_cue_service`), not scoped to any single Vessel. Two consequences follow: a cue registered for one Vessel is still "known" after that Vessel closes, so an operator who reuses the same pair of physical objects across several Vessels does not have to re-register them each time; and a Vessel's own creation clears the cue store, since a brand-new Vessel's Faces are unbound and a cue left over from a deleted or unrelated Vessel would otherwise make the very first Store attempt on it look already bound to someone else's object.

`vault.bin` remains as a legacy, non-Vessel fallback: a WebUI deployment that has never had a Vessel created for it falls back to a single unnamed container at that path, preserving compatibility with the original pre-Vessel single-container model. New deployments should create a Vessel through the TUI rather than relying on this fallback.

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
- role-scoped WebUI access tokens (store, recover) are real access control, separate from route hiding: a recover-role session cannot reach Face setup, Store, Maintenance, or any restricted-passphrase field regardless of whether it can guess a hidden route's path
- restricted actions require server-side checks and explicit confirmation
- Field Mode reduces exposure but is not a security boundary

## Coercion-Safe Delaying Architecture

Phasmid implements a three-component coercion-safe delaying architecture:

1. **Silent Standby** — Transitions from sensitive UI state to non-sensitive standby
   on a configurable hotkey. States: `active`, `standby`, `sealed`, `dummy_disclosure`.
   Recovery requires re-authentication. Standby does not erase key material from memory.

2. **Free Space Filler** — The disclosure content itself is the operator's own file,
   stored by the operator in the disclosure Face; Phasmid never fabricates it. The
   filler is a separate, optional step that occupies unused space in a Face so an
   otherwise-empty container does not read as empty. Generated before any coercive
   event, guided by context profiles, and reported by volume (size, file count,
   occupancy ratio) — not judged for how convincing it is.

3. **Context Profile Templates** — Schemas that define expected content for a given
   operational context (`travel`, `field_engineer`, `researcher`, `maintenance`,
   `archive`). Guide the optional free-space filler's content; they do not validate
   whether operator-supplied disclosure material is plausible.

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
