# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows SemVer-style release intent for documented interfaces.

## [Unreleased]

### Changed

- `SECURITY.md` now states supported versions concretely rather than by
  reference to "the latest release line", links the published advisories, and
  names GitHub private vulnerability reporting as the preferred intake channel.
  A Scope note points at the accepted residual risks in `docs/THREAT_MODEL.md`
  and `docs/NON_CLAIMS.md` so documented limits are not re-reported as findings.
- The CI formatting gate now inspects files. `[tool.black] include` in
  `pyproject.toml` was `'\\.pyi?$'`, a regex matching no real path, so every
  black invocation reported "No Python files are present to be formatted" and
  exited 0. The workflow also ran an in-place `black` before `black --check`,
  which reformatted whatever the check would have caught, so the check could
  not fail even once the pattern was repaired. The pattern is corrected, the
  mutating step is replaced by a single `black --check --diff`, and the 16
  files that drifted behind the dead gate are reformatted.

## [0.3.0] - 2026-07-26

> **Upgrading from 0.2.0 changes how the WebUI is reached from another machine.**
> Browsing from the device itself is unchanged. A USB-tethered host, or anything
> reached through an explicit `PHASMID_HOST`, must now present the access token
> at `/unlock` before it is served operator pages. Pin `PHASMID_WEB_TOKEN` if a
> script or a demo run-of-show depends on a known value. Deployments reached by
> a DNS or mDNS name must list that name in `PHASMID_ALLOWED_HOSTS`.
>
> This is a MINOR bump rather than MAJOR because the project is pre-1.0 and no
> `vault.bin` format changed and no claim was removed, per
> [docs/VERSIONING.md](docs/VERSIONING.md). Treat the WebUI access change as
> breaking for automation regardless.

### Security

Follow-up hardening for the weaknesses recorded as unresolved in
GHSA-2gm6-2phc-wv26. 0.2.0 removed *remote reachability* by restoring the
loopback bind default; these changes address the underlying unauthenticated
surfaces, which anything able to reach the WebUI still had.

- WebUI page access is authenticated for any peer that is not on loopback.
  `_ui_unlocked()` in `src/phasmid/web_server.py` returned `True`
  unconditionally, so every page-level lock was a no-op. It now validates an
  `HttpOnly`, `SameSite=Strict` page-session cookie bound to the client address
  and expiring after `PHASMID_UI_SESSION_SECONDS` (default 1800). A loopback
  peer is exempt: it is on the device itself, where the TUI already has full
  local control, so a token prompt there costs a step and adds no boundary. The
  exemption is decided per request from the peer address, never from
  configuration, so a server started straight through uvicorn cannot fail open.
- Requests whose `Host` header is a DNS name are rejected with `400`. This
  closes DNS rebinding, the attack that makes even a USB-gadget-only deployment
  reachable: a page the operator visits on the tethered laptop re-resolves its
  own domain to the gadget address and the browser then treats the WebUI as
  same-origin. Rebinding needs a name; address literals cannot be rebound. The
  check costs the operator nothing, so it applies to loopback peers too.
  `PHASMID_ALLOWED_HOSTS` allows names genuinely used to reach the device.
- Added `GET`/`POST /unlock` and `POST /lock`. A session is opened by presenting
  the access token; unlock attempts are rate limited and attempt limited.
- The mutation token is no longer rendered into unauthenticated page HTML.
  `_template_context()` supplies it only to a request that already holds a page
  session, making it a CSRF token for an unlocked session rather than the
  credential that opens one.
- `/video_feed` and `/status` now require a page session. `/video_feed`
  previously streamed the live object-cue camera with no effective gate.
- `/emergency/panic` requires a page session and returns its usual concealing
  404 without one, so its public `BRICK` trigger phrase is no longer the only
  gate beyond the mutation token.
- Confirmation phrases in `src/phasmid/restricted_actions.py` are documented as
  confirmation-only typo guards, in the module, `docs/RESTRICTED_ACTIONS.md`,
  `docs/SPECIFICATION.md`, and the Core Invariants. No action is authorized by a
  phrase alone.
- Regression tests in `tests/test_web_server.py` drive the ASGI app directly, so
  they exercise real dependency execution rather than route shape. They cover
  the chained path from the advisory: GET `/` no longer discloses the token, and
  the public phrases cannot reach `vault.silent_brick()` from a locked client.

### Added

- `PHASMID_UI_SESSION_SECONDS` configures the WebUI page-session lifetime.
- `PHASMID_ALLOWED_HOSTS` lists extra `Host` header names the WebUI accepts,
  for deployments reached by a DNS or mDNS name such as `phasmid.local`.
- The WebUI publishes its access token to `<state dir>/webui_token` (mode
  `0600`) while running and removes it at shutdown, so the TUI and a manually
  started server can both show the operator a per-process token.
  `WebUIService.access_token()` reads it, and the TUI `w` notification shows it.

### Changed

- Opening the WebUI from another machine now requires entering the access token
  once per session. Browsing from the device itself is unchanged, so the Simple
  Operator flow carries no added step in the default loopback deployment.
- The primary navigation gains a **Lock** control, shown only where a page
  session applies. A loopback peer has none to drop.

## [0.2.0] - 2026-07-26

Version 0.1.5 was prepared and version-bumped but never tagged or published; its
changes ship here as part of 0.2.0. The last published release before this one is
0.1.4.

> **Security notice for 0.1.4 users — upgrade.** In 0.1.4 the TUI `w` key bound
> the WebUI to `0.0.0.0`, reachable from any attached network. The WebUI serves
> page HTML, the embedded mutation token, and `/video_feed` without
> authentication, and `_ui_unlocked()` returns `True` unconditionally, so that
> wildcard bind made those weaknesses remotely reachable — including the
> restricted-action confirmation phrases, which are public constants in this
> repository. 0.2.0 restores the documented loopback default. If you must expose
> the WebUI, use `PHASMID_WEBUI_EXPOSE_GADGET=1`, which binds the USB gadget
> interface only.

This release also changes the default operator surface. The TUI now opens the
Simple Operator screen instead of the detailed console, and the WebUI home is
reduced to two primary actions. Existing expert workflows remain available behind
Expert controls (`e`) and the WebUI **Advanced tools** disclosure.

### Added

- Simple Operator mode: `phasmid` with no arguments now opens a low-cognitive-load
  TUI entry screen (`src/phasmid/tui/screens/simple_home.py`) listing protected
  storage with `o` Open, `n` New, `g` Guided, `e` Expert, and `q` Quit. The
  previous detailed console is reachable with `e`.
- WebUI Simple Operator home: two primary actions, **Protect a File** and **Open
  a Protected File**, a Guided Mode entry point, and an **Advanced tools**
  disclosure holding maintenance, diagnostics, audit, and inspection.
- WebUI protect flow is now a numbered three-step wizard (choose file, create
  access password, set physical access object) whose submit control stays
  disabled until all three are ready. The retrieve flow is reduced to two steps.
- Beginner-first guided workflows (`quick_protect`, `quick_open`) in both the TUI
  and the WebUI, written without Phasmid-specific terminology.
- `docs/WEBUI_OPERATOR_GUIDE.md`: normal-use manual for the refreshed WebUI.
- README section documenting WebUI bind behaviour and the USB gadget opt-in.

- WebUI object-cue registration from a local image file: `/register_key` now accepts an optional `reference_image` upload, and the Local Entry Maintenance page provides a file picker next to the existing camera rebind flow. Registration from a file derives the same encrypted feature template as camera capture and keeps the size-limited upload handling used by other WebUI uploads.
- `AIGate.register_reference_from_image_bytes` for camera-independent reference registration, with decoding guards, downscaling of large images toward the camera frame scale, and the existing cue-similarity checks.
- Client-side preview of the selected reference image on the Local Entry Maintenance page (browser-only object URL; the file is never persisted server-side).
- Default-profile tests covering image-file registration (gate-level decode/downscale/similarity/persistence paths and WebUI routing, upload-size and replace-confirmation guards).

### Changed

- `docs/TUI_OPERATOR_CONSOLE.md` rewritten for the Simple/Expert split, and now
  documents that entering Expert controls is one-way for the session: no key
  returns to the Simple Operator screen and `q` there quits the application.
- `README.md`, `docs/OPERATIONS.md`, `docs/SPECIFICATION.md`,
  `docs/PHASMID_ARCHITECTURE.md`, and `docs/README_INDEX.md` updated for the
  refreshed operator surfaces.
- WebUI bind address is now resolved in one place, `WebUIService.resolve_bind_host()`, used by every start path. Order: explicit `PHASMID_HOST`, then opt-in USB gadget exposure, then `127.0.0.1`.
- `WebUIService.start()` takes `host=None`/`port=None` and resolves them from configuration, so `PHASMID_PORT` is now honoured on the TUI path as well.
- `WebUIService.access_url()` reports the address actually bound instead of probing for a USB gadget address, and no longer returns `None`. The TUI start notification and exposure banner show that address.

### Security

- **The TUI `w` key no longer binds the WebUI to `0.0.0.0`.** It binds `127.0.0.1`, restoring the documented default that `docs/THREAT_MODEL.md`, `docs/RPI_ZERO_DEPLOYMENT.md`, and the Core Invariants had always stated. This reverses the change made under 0.1.4. Because the WebUI serves page HTML, the embedded mutation token, and `/video_feed` without authentication, and `_ui_unlocked()` returns `True` unconditionally, the wildcard bind made every one of those weaknesses reachable from any attached network.
- Added `PHASMID_WEBUI_EXPOSE_GADGET` for the USB gadget use case. It binds the gadget interface address (`usb0` or `enx*`) only, never all interfaces, and falls back to loopback with a warning when no gadget address is present. A wildcard bind now requires setting `PHASMID_HOST=0.0.0.0` deliberately.
- Regression test `tests/test_tui.py::test_tui_toggle_webui_binds_loopback_not_all_interfaces` drives `action_toggle_webui` and asserts the host handed to uvicorn.
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
