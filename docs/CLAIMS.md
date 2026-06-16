# Phasmid Claims Inventory

This file is the canonical inventory of Phasmid claims.  
A claim is listed with its source, verification method, and scope limitations.

| Claim ID | Claim Text | Source | Verification | Scope |
|---|---|---|---|---|
| CLM-01 | Creates an encrypted `vault.bin` container. | README.md §What Phasmid does | tests: `tests/test_vault_core.py` | Local runtime behavior |
| CLM-02 | Mixes a local access key into recovery so `vault.bin` alone is not enough. | README.md §What Phasmid does | tests: `tests/test_vault_core.py` | Recovery path with missing state |
| CLM-03 | Metadata detection and reduction are best-effort. | README.md §What Phasmid does | tests: `tests/test_metadata.py` | Supported metadata formats only |
| CLM-04 | Phasmid does not promise perfect deniability. | README.md §Not Anti-Forensics | manual | Product claim boundary |
| CLM-05 | The interface should report what the user needs to complete the current operation, but it should not reveal the internal disclosure model, storage structure, trial order, or restricted recovery behavior. | docs/THREAT_MODEL.md §Capture-Visible Surface Rules | tests: `tests/test_terminology.py`, `tests/scenarios/test_field_mode_visibility.py` | Capture-visible surfaces |
| CLM-06 | Field Mode reduces normal exposure in capture-visible workflows, but it is not a security boundary. | docs/THREAT_MODEL.md §Field Mode | tests: `tests/scenarios/test_field_mode_visibility.py` | Field Mode enabled |
| CLM-07 | Phasmid is not approved classified-data handling infrastructure. | README.md §Not Anti-Forensics | manual | Governance/compliance boundary |
| CLM-08 | The system is local-only by default. | AGENTS.md §Core Invariants | tests: `tests/test_web_server.py` | Default deployment profile |
| CLM-09 | The WebUI binds to `127.0.0.1` by default. | AGENTS.md §Core Invariants | tests: `tests/test_web_server.py` | Default host config |
| CLM-10 | Hidden routes are UX concealment only, not access control. | AGENTS.md §Core Invariants | tests: `tests/test_web_server.py` | WebUI navigation behavior |
| CLM-11 | Restricted actions must require server-side checks, short-lived restricted confirmation, and typed confirmation where applicable. | AGENTS.md §Core Invariants | tests: `tests/test_web_server.py`, `tests/test_restricted_actions.py` | Restricted endpoints |
| CLM-12 | Audit logging remains optional and must not record passwords, payload bytes, plaintext filenames, internal entry semantics, or disclosure structure. | AGENTS.md §Core Invariants | tests: `tests/test_audit.py`, `tests/test_operations.py` | Audit enabled mode |
| CLM-13 | Metadata reduction is best-effort and must not be described as complete sanitization. | AGENTS.md §Core Invariants | tests: `tests/test_metadata.py`, `tests/test_docs_and_templates.py` | Metadata workflow wording |
| CLM-14 | Passing automated tests does not prove field safety. | AGENTS.md §Core Invariants | manual | Validation process claim |
| CLM-15 | `vault.bin` contains no plaintext header or format marker (v3 format). | docs/THREAT_MODEL.md §State Directory Surface | tests: `tests/scenarios/test_headerless_invariant.py` | Current container format |
| CLM-16 | Optional audit log (`events.log`) records operation type, timestamp, and length only — not passwords, payload bytes, or plaintext filenames. | docs/THREAT_MODEL.md §State Directory Surface | tests: `tests/test_audit.py` | Audit event schema |
| CLM-17 | `create_file_response()` always returns `retrieved_payload.bin` regardless of original filename. | docs/THREAT_MODEL.md TS-08 | tests: `tests/test_web_server.py` | Retrieve path |
| CLM-18 | All responses include `Cache-Control: no-store, no-cache` and `Pragma: no-cache`. | docs/THREAT_MODEL.md TS-09 | tests: `tests/test_web_server.py` | HTTP responses |
| CLM-19 | TUI reads passphrases interactively; they are not passed as CLI arguments. | docs/THREAT_MODEL.md TS-10 | tests: `tests/test_cli.py` | TUI/CLI operator flow |
| CLM-20 | Store flow warns on metadata risk detection; best-effort scrubbing is available for supported file types. | docs/THREAT_MODEL.md TS-11 | tests: `tests/test_metadata.py`, `tests/test_web_server.py` | Metadata routes |
| CLM-21 | WebUI rate limiter (`enforce_rate_limit()`) limits 20 requests/60 s per client; exceeded rate returns HTTP 429. | docs/THREAT_MODEL.md TS-12 | tests: `tests/test_web_server.py` | Web request rate limiting |
| CLM-23 | Object matching is an operational access cue, not cryptographic key material. | AGENTS.md §Core Invariants | tests: `tests/test_ai_gate_routing.py` | Access cue behavior |
| CLM-24 | ORB descriptors, image coordinates, and camera frames must not be described as high-entropy secrets. | AGENTS.md §Core Invariants | manual | Documentation language |
| CLM-25 | `vault.bin` alone should not be enough for normal recovery when required local state is absent. | AGENTS.md §Core Invariants | tests: `tests/test_vault_core.py` | Local state absent scenario |
| CLM-26 | The local access key remains part of the recovery path unless a documented migration changes the container format. | AGENTS.md §Core Invariants | tests: `tests/test_kdf_engine.py` | Current format generation |
| CLM-27 | The safest sensitive data is data not carried. | docs/SPECIFICATION.md §Retention principle | manual | Operational practice |
| CLM-28 | This deployment plan reduces exposed services and local leakage for Raspberry Pi Zero 2 W class hardware. It does not provide physical tamper resistance, anti-forensic guarantees, or hardware-grade secure storage. | docs/RPI_ZERO_APPLIANCE_DEPLOYMENT.md §Intro | manual | Appliance deployment guidance |
| CLM-29 | `PHASMID_AUDIT=1` enables optional audit logging. | docs/SPECIFICATION.md §Audit logging | tests: `tests/test_audit.py` | Runtime configuration |
| CLM-30 | `PHASMID_FIELD_MODE=1` enables Field Mode. | docs/CONFIGURATION.md | tests: `tests/scenarios/test_field_mode_visibility.py`, `tests/test_config.py` | Runtime configuration |
| CLM-31 | `PHASMID_ACCESS_MAX_FAILURES` sets access failure threshold for lockout policy. | docs/SPECIFICATION.md §Attempt limiting | tests: `tests/test_attempt_limiter.py`, `tests/test_config.py` | Runtime configuration |
| CLM-32 | `PHASMID_ACCESS_LOCKOUT_SECONDS` sets lockout duration. | docs/SPECIFICATION.md §Attempt limiting | tests: `tests/test_attempt_limiter.py`, `tests/test_config.py` | Runtime configuration |
| CLM-33 | `PHASMID_MIN_PASSPHRASE_LENGTH` sets minimum passphrase length policy. | docs/SPECIFICATION.md §Passphrase policy | tests: `tests/test_passphrase_policy.py`, `tests/test_config.py` | Runtime configuration |
| CLM-34 | No new network surfaces introduced for operator pages; routes are gated by web token and UI unlock checks. | docs/TUI_OPERATOR_CONSOLE.md §Security notes | tests: `tests/test_web_server.py` | Operator pages |
| CLM-35 | Running `phasmid doctor` is diagnostic and does not certify the host as secure. | src/phasmid/models/doctor.py disclaimer | tests: `tests/test_tui.py`, `tests/test_operations.py` | Doctor output semantics |
| CLM-36 | Context profiles guide dummy generation and plausibility validation; built-in profiles are `travel`, `field_engineer`, `researcher`, `maintenance`, `archive`. | docs/COERCION_SAFE_DELAYING.md §Context Profile Templates | tests: `tests/test_context_profile.py` | Context profile schema |
| CLM-37 | Dummy dataset plausibility report generates local-only advisory output: container size, dummy size, occupancy ratio, file count, file type distribution, and warnings. | docs/COERCION_SAFE_DELAYING.md §Plausible Dummy Dataset | tests: `tests/test_dummy_generator.py` | Dummy plausibility report |
| CLM-38 | Silent Standby clears sensitive UI state on hotkey trigger; recovery requires re-authentication. | docs/COERCION_SAFE_DELAYING.md §Silent Standby | tests: `tests/test_standby_state.py` | Standby state transitions |
| CLM-39 | Coercion-safe recognition mode routes low-confidence recognition toward the controlled-disclosure path and avoids an obvious ambiguous-match response. | docs/COERCION_SAFE_DELAYING.md §Coercion-Safe Recognition Fallback | tests: `tests/test_ai_gate_routing.py`, `tests/test_scenarios.py`, `tests/test_web_server.py` | Prototype recognition mode routing |
| CLM-40 | Dummy generator does not forge forensic artifacts, fake kernel logs, or perform timestamp forgery. | docs/COERCION_SAFE_DELAYING.md §Disallowed Behaviors | tests: `tests/test_dummy_generator.py` | Dummy generation restrictions |
