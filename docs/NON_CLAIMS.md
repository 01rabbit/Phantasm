# Phasmid Non-Claims

This document lists protections or guarantees that Phasmid does not provide.
Each item includes a brief rationale to keep review and deployment decisions explicit.

## Non-Claims

- Phasmid does not provide perfect deniability.  
  Rationale: behavior and artifacts are reduced, not eliminated, and depend on host conditions.

- Phasmid does not provide guaranteed secure deletion.  
  Rationale: flash media behavior, wear leveling, and host storage layers prevent absolute erase guarantees.

- Phasmid does not provide protection against compromised hosts.  
  Rationale: malware, kernel compromise, and privileged tracing can bypass local software controls.

- Phasmid does not provide protection against malware or keyloggers.  
  Rationale: local input capture defeats passphrase and workflow hygiene controls.

- Phasmid does not provide protection against live memory capture.  
  Rationale: in-use key material can be exposed by privileged memory inspection.

- Phasmid does not provide protection against camera observation.  
  Rationale: shoulder-surfing and direct visual capture are outside software-only defenses.

- Phasmid does not provide protection against coercion after disclosure.  
  Rationale: once disclosure has occurred, software cannot enforce human-safety outcomes.

- Phasmid does not provide certified classified-data handling.  
  Rationale: the project is a field-evaluation prototype and not a certified records system.

- Phasmid does not provide remote management, remote wipe, or remote unlock.  
  Rationale: local-only posture is a core project boundary.

- Phasmid does not provide communications security, anonymity, censorship bypass, or surveillance evasion.  
  Rationale: the project scope is local storage behavior, not network transport or anti-censorship systems.

- Phasmid does not provide forensic-grade unverifiable deniability.  
  Rationale: host-level traces and operational artifacts can remain detectable under expert forensic analysis.

- Phasmid does not bypass forensic tools or claim forensic invisibility.  
  Rationale: the project controls local disclosure behavior; it does not interfere with analysis tools or make software artifacts disappear.

- Phasmid does not hide processes or hide like malware.  
  Rationale: malware-like concealment is outside scope and explicitly disallowed.

- Phasmid does not provide protection in jurisdictions where key disclosure refusal is criminalized.  
  Rationale: legal coercion outcomes are determined by law and court process, not cryptographic design.

- Phasmid does not provide protection against trained forensic examination of host artifacts unless target-hardened deployment is followed.  
  Rationale: deployment controls (tmpfs, local-only binding, hardened host policy) materially affect artifact exposure.

- Phasmid does not promise a single maintainer (bus factor 1) sustainability guarantee.  
  Rationale: long-term response capacity and maintenance continuity can be constrained by single-maintainer limits.

## Coercion-Safe Delaying Non-Claims

- Phasmid does not guarantee permanent secrecy against unlimited forensic analysis.  
  Rationale: the coercion-safe architecture increases uncertainty and investigation cost; it does not eliminate the adversary's eventual ability to distinguish dummy from protected content.

- Phasmid does not claim that dummy content is indistinguishable under expert forensic analysis.  
  Rationale: an expert forensic examiner with sufficient time may identify structural differences between dummy and true content.

- Phasmid does not forge or tamper with filesystem metadata, kernel logs, or timestamps.  
  Rationale: anti-forensic tampering is an explicitly disallowed behavior.

- Silent Standby does not erase key material from process memory.  
  Rationale: standby is a UI-layer operation; live memory capture after standby may still expose in-memory key material.

- Phasmid does not detect or verify physical coercion context.  
  Rationale: coercion-safe recognition mode routes based on recognition confidence, not on verified coercion state.

- Dummy plausibility is entirely dependent on operator preparation.  
  Rationale: the plausibility report is advisory; a trivially empty or inconsistent dummy profile reduces survivability.
