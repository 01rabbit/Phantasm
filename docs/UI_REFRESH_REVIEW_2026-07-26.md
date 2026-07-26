# UI Refresh Review — 2026-07-26

## Decision

**Proceed to demo adjustment, with a target-device smoke test as the next gate.**

The review found no release-blocking regression in the refreshed WebUI/TUI flow
or in the security controls exercised by the automated suite. This is a
conditional engineering decision, not a field-safety or security certification.
Before presenting the demo, rehearse the complete flow on the actual Raspberry
Pi, camera, display, and USB-gadget setup that will be used.

## Scope

The review covered the UI refresh and its follow-up hardening through commit
`d5eb6ad`, including:

- the Simple Operator TUI entry point and guided flow;
- the refreshed Home, Protect, Open, maintenance, and access-token pages;
- image-file object-cue registration;
- WebUI lifecycle and bind-address behavior;
- remote page-session gating, mutation-token handling, Host validation, and
  restricted-action predicates;
- operator documentation and demo instructions.

The review did not re-evaluate the cryptographic container format, prove field
safety, or replace the existing target-hardware and seizure-review procedures.

## Core-invariant review

| Invariant | Review result |
| --- | --- |
| Local-only default | Preserved: WebUI startup paths default to loopback; gadget exposure remains opt-in. |
| Remote page access | Preserved: non-loopback peers require an access-token-established page session. |
| DNS rebinding posture | Preserved: DNS-name `Host` values are rejected unless explicitly allowed. |
| Mutation authorization | Preserved: the mutation token is withheld from locked page responses and remains required for mutation routes. |
| Restricted actions | Preserved: server-side capability/session checks remain in addition to typed typo guards. |
| Capture-visible language | No blocking disclosure-structure terminology was found in the refreshed templates. |
| Object cue and UI face lock boundary | Preserved in operator guidance: neither is presented as cryptographic authentication. |
| Container compatibility | No container-format or migration change was part of the UI refresh. |

## Verification evidence

- `python3 -m unittest discover -s tests`: 542 tests passed; 5 were skipped.
- `ruff check .`: passed.
- `mypy src main.py`: did not complete cleanly because the environment lacks a
  Python 3.12 `tomli` implementation/stub; the reported location was unchanged
  operator-profile compatibility code, not a UI-refresh type error.
- Coverage enforcement could not be repeated because the `coverage` module is
  not installed in this environment. The review therefore does not make a new
  coverage-percentage claim.

## Residual demo risks

These are not blockers for beginning demo adjustment, but they should be made
explicit in the rehearsal plan:

1. **Target-device performance remains the decisive UX check.** Desktop tests do
   not establish camera latency, page responsiveness, thermal behavior, or
   object-cue stability on a Pi Zero 2 W.
2. **A tethered browser adds one access step.** Stage `/unlock`, pin
   `PHASMID_WEB_TOKEN` for the rehearsal if repeatability is needed, and keep the
   token out of captured slides and recordings.
3. **Browser and OS artifacts remain.** The Finish action clears application
   session state; it does not guarantee deletion of downloaded files, browser
   caches, screenshots, or operating-system traces.
4. **Object matching is environmental.** Rehearse lighting, framing, camera
   focus, and the exact demonstration object. A successful match is an
   operational cue, not proof of identity.
5. **Loopback access is intentionally exempt from the page token.** This is
   consistent with the local-device trust boundary, but it is not protection
   against a compromised local host.

## Demo-adjustment entry criteria

Begin content and timing adjustments now. Do not declare the demo ready until a
single target-device rehearsal has verified all of the following:

- TUI launch, WebUI start/stop, and the displayed address/token;
- unlock from the actual presentation browser when using USB gadget mode;
- Protect and Open with the chosen sample file and physical object;
- neutral failure behavior for one deliberately incorrect attempt;
- Finish/Lock and WebUI shutdown;
- no token, passphrase, original sensitive filename, or internal entry semantics
  appear on the captured presentation surface;
- the fallback path in the demo runbook works without weakening local-only
  defaults or restricted-action checks.

If any item fails, treat it as a demo blocker and fix or simplify the rehearsal
flow rather than bypassing the relevant control.
