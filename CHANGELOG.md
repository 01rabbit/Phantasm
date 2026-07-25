# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows SemVer-style release intent for documented interfaces.

## [Unreleased]

### Added

- WebUI object-cue registration from a local image file: `/register_key` now accepts an optional `reference_image` upload, and the Local Entry Maintenance page provides a file picker next to the existing camera rebind flow. Registration from a file derives the same encrypted feature template as camera capture and keeps the size-limited upload handling used by other WebUI uploads.
- `AIGate.register_reference_from_image_bytes` for camera-independent reference registration, with decoding guards, downscaling of large images toward the camera frame scale, and the existing cue-similarity checks.
- Client-side preview of the selected reference image on the Local Entry Maintenance page (browser-only object URL; the file is never persisted server-side).
- Default-profile tests covering image-file registration (gate-level decode/downscale/similarity/persistence paths and WebUI routing, upload-size and replace-confirmation guards).

### Security

- Image-file binding failures on `/register_key` are masked to a neutral message, matching the camera path: only the pre-comparison decode error is surfaced, so binding responses cannot be used as a matching oracle against the other entry's stored cue template. A regression test asserts the failure responses are indistinguishable.

## [0.1.5] - 2026-05-11

### Added

- Architecture figure embedded at the top of `docs/PHASMID_ARCHITECTURE.md` using `images/architecture_v1.png` to improve onboarding and design readability.
- Release-log updates in `docs/REVIEW_VALIDATION_RECORD.md` for profile-based test execution and combined coverage recording.

### Changed

- CI coverage gate logic updated to aggregate `tests` + `tests_optional` coverage before enforcing `--fail-under=70`.
- `CONTRIBUTING.md` validation guidance updated to document default/optional/archive-review test profiles.
- `tests/TEST_RETENTION_MATRIX.md` updated from candidate planning to current consolidation status.
- `0.1.4` changelog entry expanded to reflect the full scope of completed documentation and test-suite restructuring work.

### Security

- Coverage gating remains at 70% without threshold reduction by combining default and optional profiles, preserving verification discipline for active security boundaries.

## [0.1.4] - 2026-05-10

### Added

- `docs/README_INDEX.md` as a long-form documentation entrypoint and navigation index.
- `docs/archive/` policy and archived historical analysis/evaluation documents for traceable but non-active references.
- TUI operator screenshots (`images/TUI_HOME.png`, `images/TUI_AUDIT.png`, `images/TUI_DOCTOR.png`, `images/TUI_INSPECT.png`, `images/TUI_FACE.png`).
- Test profile documentation and retention matrix (`tests/README.md`, `tests/TEST_RETENTION_MATRIX.md`).
- Split test profiles for lifecycle management:
  - `tests_optional/` for dependency-heavy or extended tests
  - `tests_archive_review/` for historical/evaluation review tests

### Changed

- `AGENTS.md` compressed and de-duplicated while preserving boundary/security invariants and authority order.
- README restructured into a two-layer entry model:
  - quick-start-first structure with requirements before install details
  - shortened overview with deep links moved to docs index
- TUI banner/title updated to the new PHASMID ASCII identity and synchronized with operator docs.
- `docs/TUI_OPERATOR_CONSOLE.md` updated with screenshot-based presentation and current banner representation.
- Test suite reorganized and consolidated:
  - merged overlapping observability/context-profile/dual-approval/coercion-safe scenario tests
  - moved optional and archive-review tests to dedicated profiles
  - CI expanded to include default, optional, reproducible-build, and manual archive-review job paths
- `tests/test_docs_and_templates.py` and `tests/test_terminology.py` aligned with README/docs archive restructuring.
- Historical roadmap links updated to archived document paths.

### Security

- Existing local-only boundary, restricted-action constraints, and neutral capture-visible language policies were preserved during documentation and test-suite restructuring.
- Capture-visible vocabulary controls and restricted-route semantics remained enforced by updated terminology and scenario tests.

## [0.1.3] - 2026-05-10

### Added

- M6 release-discipline controls for reproducible artifact generation, dependency audit checks, and release policy documentation.
- Raspberry Pi environment bootstrap and validation scripts for target-hardware setup and checks.
- Pi Zero 2 W LUKS calibration profile and helper scripts for constrained-device measurement workflows.

### Changed

- Raspberry Pi deployment and validation documentation expanded across setup, field test procedure, seizure review checklist, and readiness planning.
- Release and validation records updated to reflect Pi Zero 2 W evaluation workflow expectations.

### Security

- Dependency vulnerability scanning via `pip-audit` in CI.
- Reproducible-build verification job added to CI to detect artifact drift.

## [0.1.2] - 2026-05-09

### Added

- Raspberry Pi-first camera backend flow with Picamera2/libcamera as primary and OpenCV as fallback.

### Fixed

- WebUI camera stream/status synchronization so `/status` reflects active streaming state.
- MJPEG streaming resilience under camera frame acquisition failures with explicit fallback frame behavior.
- WebUI process termination robustness: graceful stop with forced termination fallback when shutdown hangs.
- Camera resource cleanup lifecycle on WebUI shutdown and stream disconnect paths.
- Raspberry Pi camera color handling and stream orientation for WebUI preview consistency.

### Changed

- TUI/WebUI operator-facing WebUI exposure messaging aligned to non-localhost gadget-access operation.
- WebUI runtime observability expanded for camera backend, readiness, and stream attributes.

### Security

- Existing WebUI protections (token checks, restricted confirmations, rate limits, headers, and restricted-action policy) preserved while introducing Raspberry Pi operational hardening.

## [0.1.1] - 2026-05-09

### Fixed

- TUI-launched WebUI now starts the FastAPI app through `uvicorn` reliably.
- Extended WebUI startup wait to 10 seconds to support Raspberry Pi Zero 2 W class hardware.
- WebUI launch failures now retain actionable diagnostics (attempted command, return code, port-check status, and log path) for operator troubleshooting.

### Changed

- TUI-launched WebUI default bind host changed to `0.0.0.0` for Raspberry Pi USB gadget network access.
- TUI success notification updated to guide access via the device USB gadget IP.

### Security

- Existing WebUI protections (token checks, restricted confirmations, rate limits, and headers) remain unchanged while enabling gadget-network exposure.

## [0.1.0-prototype] - 2026-05-07

### Added

- Unified JES operator interface (TUI + WebUI alignment and operator pages).
- Threat model consolidation and claim/non-claim documentation baseline.
- Crypto hygiene inventory and tests (nonce, constant-time, randomness checks).
- M3 scenario/property/headerless invariant testing suite.
- M4 operational artifact checks and WebUI source leakage checks.

### Security

- Restricted action policy enforcement and capture-visible response neutrality hardening.
- Process hardening and volatile state support (`PHASMID_TMPFS_STATE`) with diagnostics.
- Optional signed release manifest and SBOM generation.

### Changed

- Terminology alignment toward neutral operator-facing language.

### Documentation

- STRIDE analysis, device-binding analysis, split-key recovery analysis.
- Security policy (`SECURITY.md`) and maintainer continuity note (`docs/BUS_FACTOR.md`).

## Changelog Rule

Security-impacting changes must be listed under a `### Security` section.
