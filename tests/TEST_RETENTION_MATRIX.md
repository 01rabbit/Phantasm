# Test Retention Matrix

This matrix classifies tests into retention buckets so we can reduce maintenance cost without weakening security boundaries.

## A) Keep (Core contract and security boundary)

These should remain in default CI because they verify active claims, threat-model boundaries, or critical recovery behavior.

- `tests/test_vault_core.py`
- `tests/test_crypto_boundary.py`
- `tests/test_container_layout.py`
- `tests/test_record_cypher.py`
- `tests/test_kdf_engine.py`
- `tests/test_kdf_subkeys.py`
- `tests/test_config.py`
- `tests/test_ai_gate_routing.py`
- `tests/test_state_store.py`
- `tests/test_volatile_state.py`
- `tests/test_attempt_limiter.py`
- `tests/test_passphrase_policy.py`
- `tests/test_restricted_actions.py`
- `tests/test_web_server.py`
- `tests/test_metadata.py`
- `tests/test_operations.py`
- `tests/test_cli.py`
- `tests/test_audit.py`
- `tests/test_capabilities.py`
- `tests/test_strings.py`
- `tests/test_terminology.py`
- `tests/scenarios/test_brick_irreversibility.py`
- `tests/scenarios/test_field_mode_visibility.py`
- `tests/scenarios/test_headerless_invariant.py`
- `tests/webui/test_source_leakage.py`
- `tests/crypto/test_constant_time.py`
- `tests/crypto/test_no_weak_randomness.py`
- `tests/crypto/test_nonce_uniqueness.py`

## B) Keep but mark optional profile (heavy or extra dependencies)

These are valuable but may require optional dependencies/hardware and should run in extended CI or dedicated jobs.

- `tests_optional/test_ai_gate.py`
- `tests_optional/test_object_gate.py`
- `tests_optional/test_object_model_gate.py`
- `tests_optional/test_object_cue_policy_gate.py`
- `tests_optional/test_lightweight_object_matcher.py`
- `tests_optional/test_recognition_benchmark.py`
- `tests_optional/test_recognition_routing.py`
- `tests_optional/test_doctor_m4.py`
- `tests_optional/test_luks_layer.py`
- `tests_optional/test_vault_invariants.py`
- `tests_optional/test_kdf_versioning.py`

## C) Consolidation status

Completed:

- `tests/test_scenarios.py` (consolidated from former coercion-safe split)
- `tests/test_observability_probe.py` (consolidated from former support split)
- `tests/test_context_profile.py` (consolidated from former dummy-profile-eval split)
- `tests/test_approval_flow.py` (consolidated from former dual-approval-support split)

Remaining candidate:

- `tests/test_docs_and_templates.py` + parts of `tests/test_terminology.py`

## D) Archive-review candidates (historical/evaluation focused)

These should be reviewed for move-to-archive only after confirming no active claim references them.

- `tests_archive_review/test_luks_eval.py`
- `tests_archive_review/test_pi_scripts.py`
- `tests_archive_review/test_release_artifacts.py`
- `tests_archive_review/test_dependency_policy.py`
- `tests_archive_review/test_claims_coverage_script.py`

## Decision rules

1. Never archive a test that is the only enforcement for a `docs/CLAIMS.md` line.
2. Prefer consolidation over deletion when behavior is still active.
3. Keep capture-visible and terminology tests in default CI.
4. If a test depends on optional packages (`cv2`, `numpy`, `fastapi`, `hypothesis`), classify it as optional profile instead of removing it.
