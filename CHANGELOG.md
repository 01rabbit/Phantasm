# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project follows SemVer-style release intent for documented interfaces.

## [Unreleased]

### Added

- `scripts/pi_zero2w/tune_camera.py` — finds the camera settings that give
  *this* object, in *this* room, the most to match on. The defaults above are
  measured, but they are measured against synthetic scenes, and the real
  optimum depends on the light and the object in a way nothing decided in
  advance can capture. It sweeps resolution, shutter ceiling, denoising and
  sharpening against whatever is in front of the lens, reports what each is
  worth in keypoints, and prints the launcher line to use. Refuses to
  recommend anything when no configuration produced a single keypoint, rather
  than picking a winner out of zeros.
- `scripts/pi_zero2w/measure_cue_margin.py` — how much margin a bound access
  object actually has on the device it will be shown on. The cue either matches
  or it does not, and the WebUI badge and `/status` report only that; on stage
  that is the wrong resolution, because an object clearing its threshold by one
  point and one clearing it threefold look identical right up until the lighting
  changes. It reports the template's keypoint count, the thresholds that count
  produces, and the good matches and inliers scored over a run of live frames,
  ending in a worst-case margin. It also names the case the tuning knobs cannot
  fix: below roughly 48 keypoints `GOOD_MATCH_FLOOR` decides the threshold
  rather than `PHASMID_CUE_GOOD_MATCH_RATIO`, so lowering the ratio moves
  nothing and the object itself has to change. Reads the same reference store
  the console uses and writes nothing.
- `PHASMID_CUE_DEBUG` draws the live cue scores along the bottom of the camera
  preview — keypoints, good matches, inliers, and the bar each has to clear.
  The measuring script above answers the same question but cannot show what the
  lens is looking at, and aiming a camera is iterative: closer, turned, relit,
  each step needing to know whether it helped. Reported from the device as the
  blind version being awkward to work with, which it was. Off by default and
  deliberately given no UI control: the preview is a capture-visible surface
  and these numbers describe the mechanism (CLM-05), so this is for rehearsing
  with nobody watching. Costs one extra feature extraction per frame while
  enabled, and nothing at all when it is off.
- `PHASMID_CUE_LOWE_RATIO` and `PHASMID_CUE_RANSAC_PX` expose the two constants
  that decide *what counts as the same feature* and *how far a correspondence
  may sit from the fitted geometry*. Asked for from the device, where an object
  that matched one day stopped matching the next. They are the knobs the
  proportional thresholds cannot substitute for: the Lowe ratio is the one for
  light that has moved since the object was bound, and the RANSAC tolerance is
  the one for **many good matches and almost no inliers**, which is what a
  non-planar object looks like when it is turned - `findHomography` fits a
  plane-to-plane transform, so correspondences off that plane are discarded as
  outliers no matter how real they are. Neither substitutes for binding the
  view being shown, and loosening either has to be re-verified against the
  object-absent refusal or Step 4 of the demo stops proving anything.
- `score_descriptors` reports `frame_keypoints` alongside the template's count,
  and the overlay shows both. A template of 213 keypoints scoring 5 good
  matches reads identically whether the frame offered 900 candidates or 6 -
  whether the object is in front of a working camera and not being recognised,
  or the camera is delivering a blur. Those want opposite responses.
- `measure_cue_margin.py --save DIR` writes the first frame and the grayscale
  actually matched on. No score answers "is the object in the picture at all",
  which stayed the open question through two rounds of measuring on the device.

### Changed

- The Lowe ratio and the RANSAC reprojection tolerance are named constants on
  `ObjectCueMatcher` rather than literals inside the matching path, and the new
  `score_frame` / `score_descriptors` read the same ones the gate decides on.
  A diagnostic reporting different numbers from the ones being applied is worse
  than no diagnostic, because it is believed — someone would tune against it
  and take the result on stage. `tests/test_cue_scores.py` holds the two paths
  to the same answer in both directions, matching and refusing.
- `PHASMID_CUE_GOOD_MATCH_RATIO` drops from 0.25 to 0.18. Not a loosening for
  its own sake: CLAHE finds more keypoints in the same object, and a
  *proportion* of a richer template is a higher absolute bar, so two
  presentations that had passed stopped passing — the object tilted five
  degrees, and the object held ten percent closer. 0.18 is the loosest value at
  which both return, and no looser. The inlier proportion did not need to move.

### Fixed

- **The WebUI froze, and Home never came back.** Reported from the device in
  the middle of the demonstration sequence: clear an entry with its destroy
  password, confirm its access password no longer opens it, press Home - and
  the interface stopped answering. Nothing was wrong with Home.

  Every route was written `async def`, which in FastAPI means the body runs
  directly on the one event loop. Several of those bodies are not asynchronous
  in any sense: they derive keys with Argon2id, overwrite container bytes, and
  poll the camera with `time.sleep`. On a Pi Zero 2 W that is seconds of work
  per request, and for all of it uvicorn can serve nothing else - not
  `/status`, not `/video_feed`, not the home page.

  The step that exposed it is the most expensive path in the application.
  Confirming a cleared entry no longer opens runs every mode's Argon2id against
  bytes that are now random, waits for all of them to fail, and only then runs
  the destroy-password check's own derivation. Nothing short-circuits, so the
  stall is at its longest exactly when an operator is standing in front of an
  audience.

  Two things in the page turned that stall into a hang. The status poller fired
  every 1.2 s without waiting for the previous request, and the camera preview
  holds an MJPEG connection open for the life of the page. A few seconds of
  silence is enough to fill the browser's six-connection budget for the origin,
  and the navigation that follows has no socket left to go out on - which is
  what "frozen" looked like, with a healthy server behind it.

  Both halves are fixed. The nine routes that can block (`/retrieve`,
  `/destroy_face`, `/purge_other`, `/store`, `/register_key`,
  `/register_scene`, `/emergency/brick`, `/emergency/initialize`,
  `/emergency/panic`) now run their work in the threadpool, and the poller
  keeps one request in flight at a time with a 4-second abort. Being on the
  loop was also what kept container operations from overlapping, so a device
  lock now holds that guarantee explicitly rather than by accident.

- **The tuning sweep recommended a configuration the device cannot run**, and
  recommended it directly underneath its own printed warning not to. Two
  defects, both found by the first run on hardware:
  - **The measurement saturated.** The gate's detector caps at
    `nfeatures=1000` - the right cap for matching, the wrong one for comparing
    settings. On the device 640x480 reported 919 keypoints and every
    resolution above it reported exactly 1000, which reads as "bigger is
    better" and means "the ruler ended here". Worse, `max` then answered ties
    with whichever option came first in the list: the sharpness sweep was
    recommended at 1.0 while the same table showed 2.5 with half again as much
    detail. The probe now counts with the cap lifted, and ties fall through to
    detail and then to cost.
  - **The frame budget was printed and then ignored.** 1024x768 measured 272 ms
    per frame against a 250 ms interval at four frames a second - and the sweep
    measures *less* work than the console does, since it never matches, encodes
    or draws. Anything past the budget is now excluded from the ranking, with
    what was dropped and why said out loud. More pixels than the device can
    process is not more cue: the match history needs several consecutive
    frames, and a frame that arrives late has not arrived.

  Replayed against the device's own numbers, the corrected ranking answers
  640x480 rather than 1024x768, and sharpness 2.5 rather than 1.0.
- **The camera was opened, never configured.** For most of this project's life
  exactly one control was set on it — `FrameDurationLimits` — and everything
  else was left at defaults tuned for photographs a person will look at. That
  is not the same thing as an image a corner detector can work with, and none
  of the gaps announce themselves: each one presents as an object that will not
  bind, or binds and will not match, which is where days of searching went
  instead. Audited against what the module actually offers, and closed:
  - **Resolution was 320x240**, about 1.5% of what an `imx708` delivers, and
    the ceiling on everything downstream. A corner needs pixels to be a corner
    in. Measured on a printed packet filling ~30% of the frame width, in focus:
    **24 template keypoints at 320x240, 572 at 640x480, 823 at 1024x768** — and
    a template needs 60 of its own to be bound at all, so that object could not
    be bound at the old default no matter what else was right. Now 640x480,
    tunable by `PHASMID_CAMERA_SIZE`.
  - **The shutter could run to 200 ms.** A person holding an object still is
    not still at 200 ms. Measured on a 572-keypoint template: a 3 px smear
    (~33 ms) scores 197 good matches, 9 px about 70, 21 px scores 22 and is
    refused. Capped at 33 ms via `PHASMID_CAMERA_MAX_EXPOSURE_US`. Not free —
    the light lost returns as gain and gain as noise, which the same
    measurement shows hurts *more* than blur, so the value is adjustable and
    worth measuring on the bench rather than assuming.
  - **Denoising smoothed away what ORB looks for** — print, weave, the edge of
    a label. `PHASMID_CAMERA_DENOISE`, minimal by default.
  - **Sharpening was left at the ISP's default.** FAST decides a corner from
    local contrast. `PHASMID_CAMERA_SHARPNESS`, 1.5 by default.
  - **White balance drifted under the grayscale conversion.** Grayscale is a
    weighted sum of the channels, so every AWB adjustment is a global change to
    what ORB sees — and a NoIR sensor, whose red channel carries infrared the
    algorithm was not designed for, hunts more than most. The gains are now
    frozen once the camera has settled (`PHASMID_CAMERA_LOCK_AWB`).
  - **Autofocus was engaged but not aimed.** Metered across the whole frame the
    lens is as likely to lock onto the desk or the far wall, both of which are
    more of the picture than the object. Now `AfSpeed` fast, an `AfWindows`
    focus window on the middle where the object is presented, and an explicit
    `AfTrigger` sweep before the capture that becomes a template — continuous
    autofocus is usually in the right place, and "usually" is doing a lot of
    work at the one moment that gets written to disk.

  Every control is offered against what the module reports supporting, so a
  fixed-focus or unfamiliar module loses the tuning rather than failing to
  open, and `status()` reports which were accepted — "the camera ignored half
  of this" should not look like success.
- **The camera's lens was never focused.** The module on the device is an
  `imx708` — Camera Module 3 — which has a motorised lens, and picamera2 leaves
  it wherever it powered up unless told otherwise. Pointed at an object on a
  desk, that is the wrong distance. Nothing anywhere reports it: an
  out-of-focus frame is not an error, it is a frame with almost no corners in
  it, so the object fails to bind (`Object does not stand out from the scene
  behind it`, with the mask found and under 60 keypoints inside it) and, once
  bound, fails to match. Every reading looks like a problem with the object.
  The camera is now asked what it supports and set to continuous autofocus when
  it has a lens to move; fixed-focus modules have no `AfMode` and are left
  alone. `PHASMID_CAMERA_FOCUS` overrides — `auto` for a single sweep, `off`
  for the previous behaviour, or a number of dioptres to park it. `/status`
  reports which was applied, because "the lens is in the wrong place" is
  invisible in every other number.
- **Capture and retrieval were never held to the same standard, and the
  asymmetry ran the wrong way.** Asked from the device: is retrieval stricter
  than capture? It is. Capture *builds* a template from the frame in front of
  it, so it succeeds by construction; the only test it ran was the negative one
  from #184, that the template does not answer to the empty scene. Nothing
  asked whether it would still answer to the *object* a moment later.
  Retrieval, meanwhile, asks past the per-frame thresholds for the entry to
  appear in `MATCH_HISTORY_REQUIRED` of the last `MATCH_HISTORY_FRAMES` frames
  — at `TARGET_FPS`, about a second of consistent matching. A template scoring
  near the bar flickers across that window and never accumulates, so the
  operator got a clean capture, a green toast, and an entry that would not
  open, with the two events far enough apart not to look related. Capture now
  samples fresh frames of the object still being held and applies the same
  count, refusing with what to change. It runs after the too-similar check,
  which is cheap and which re-capturing can never satisfy, and only on the
  camera path — registering from an image file has no live frames to be
  repeatable across.
- The cue overlay reports `stable N/3` alongside the per-frame scores. Clearing
  the per-frame bar is not enough to open anything, and a score sitting near
  the threshold is visible only as a count that will not fill.
- **A bound object only opened the container in the room it was bound in.**
  Reported from the device: a Face registered in one place stopped matching
  once the background changed, which means data stored in one environment
  could not be recovered in another. For a device whose premise is being
  carried and used under pressure somewhere else, that is not a rough edge.
  `to_gray` applied `cv2.equalizeHist` — a *global* remap computed from the
  whole frame's histogram. The two-shot capture (#184) had already restricted
  *where* descriptors come from, so the template held only object keypoints;
  their values were still computed through a mapping the background had a vote
  in. Measured on an unchanged object patch composited onto different
  backgrounds, against a bar of 12: **25 good matches on the binding wall, 4 on
  a dimmer one, 1 in another room.** `to_gray` now uses CLAHE, equalising per
  tile, so a change on the far side of the frame does not remap the object. The
  same measurement becomes 502 / 212 / 243, all matching, while the empty scene
  and a different object still score 0 — the refusal the demo rests on is
  unchanged. Local equalisation is also far more sensitive on a plain wall: 505
  template keypoints where the global version found 25, because a histogram
  dominated by flat wall crushes the object's own contrast into a few levels.
- `docs/submissions/Phasmid_Demo_Runbook.md` said `PHASMID_RECOGNITION_MODE=demo`
  makes recognition deterministic, which reads as a safety net it is not.
  `_recognition_confidence()` returns 1.0 only when the ORB match has *already*
  succeeded and 0.0 otherwise, so the demo-mode fallback branch is unreachable
  on a failed match: **there is no rescue path**. Corrected, and a new §9.0.4
  gives the numbers that separate a camera problem from a template problem from
  a geometry problem - tuning thresholds against the wrong one breaks the
  object-absent refusal the demo rests on.

### Migration

- **Objects bound by an earlier build have to be bound again.** Descriptors are
  only comparable within the grayscale they were cut from, so templates written
  under `equalizeHist` do not match under CLAHE. Rather than load them and
  leave an entry that looks bound and silently never matches — which is
  indistinguishable, to an operator, from the defect above — the store now
  records which space it wrote (`ObjectCueStore.DESCRIPTOR_SPACE`) and treats
  anything else as unbound. Re-capture from the Store page; nothing else is
  affected, and no stored file is touched.

## [0.6.0] - 2026-08-01

> Everything in this release came from running the demo on the device rather
> than from reading the code. The object cue was binding to the wall behind the
> object; the retrieval lockout never ended, and on the CLI side had never
> counted past one failure; clearing a Face was impossible for anything the
> WebUI had protected. The capability that closes the release is the one the
> hardware sessions argued for: **a destroy password now works in the field
> that opens an entry**, so refusing under pressure needs no separate screen a
> watcher could learn to recognise.
>
> This is a MINOR bump: no `vault.bin` format changed and no claim was removed
> from `docs/CLAIMS.md`, per [docs/VERSIONING.md](docs/VERSIONING.md).
> `src/phasmid/dummy_generator.py` was removed, but nothing in `src/` imported
> it and no CLI, TUI or WebUI path reached it, so no documented operator
> behaviour changed with it — CLM-40 stands and now points at the filler that
> ships. Two claims are added: CLM-46 and CLM-47.

### Security

- The destroy password now works from the ordinary retrieval field. Entering an
  entry's destroy password where its access password goes, with that entry's
  object in front of the camera, clears the entry — and the response is the one
  a mistyped password produces, byte for byte. Nothing on the surface separates
  the two, which is the whole property: **the credential that can be compelled
  is not the only credential there is**, and using the other one requires no
  different screen, field, or gesture that a person watching could learn to
  recognise. Reached only after the ordinary retrieval has failed, so an access
  password can never be shadowed by it, and scoped by the live object match, so
  one entry's destroy password cannot reach the other. It does not count against
  the attempt limiter: the credential was correct, and an operator who has just
  cleared one entry still needs the attempts to open another. The cost of giving
  nothing away is that the operator is told nothing either — success is
  observable only as the entry no longer opening, so it has to be rehearsed.
  The explicit `/destroy_face` panel stays for clearing an entry deliberately
  rather than under pressure. (#191, CLM-46)
- `POST /destroy_face` — clearing a protected entry from the WebUI. The destroy
  credential existed only in `phasmid emergency destroy-face`, so the one
  scenario the tool exists for, refusing to disclose under duress, was the one
  that dropped out of the browser and onto a terminal. It reuses the service
  call the CLI already uses and asks for the same `DESTROY FACE` phrase, so the
  two interfaces agree rather than each inventing a dialect. Which entry is
  cleared is decided by the object in front of the camera and never by a request
  parameter: naming an entry on screen would say there is more than one. The
  destroy password stays a distinct credential from the access password —
  neither can do the other's job — so a coerced operator who hands over the
  access password has not handed over this. Every refusal reads the same, and
  failures count against the same attempt limiter as `/retrieve`. This is the
  only restricted action gated by a credential rather than by a public phrase
  alone, and it deliberately does **not** additionally require a restricted
  confirmation session: that would add a step without adding authorization, in
  the one flow reached in front of the person applying the pressure. (#189)
- An access lockout never ended. `AttemptLimiter` cleared its failure count
  only on a success, so after serving the full sixty seconds the caller still
  stood at `max_failures` and the next single mistake locked them out again —
  indefinitely, for anyone who could not produce a success. Reported from the
  device as the lockout "dragging on" long past its sixty seconds. Serving the
  lockout now spends the failures that earned it, and the lockout itself still
  holds for its whole period. (#190)
- `FileAttemptLimiter` could not record a second failure. `write_record`
  treated rewriting a record in the phase it was already in as an illegal
  transition, so the first failure persisted and every one after it raised
  `state transition rejected` — meaning the CLI-side retrieval lockout has
  never counted past one, and the brute-force ceiling CLM-31 and CLM-32
  describe did not hold on that path. A rewrite in the same phase is an update
  in place, not a transition, and is now allowed; genuine backwards moves are
  still rejected. (#190)
- The pre-Vessel container implemented the opposite destruction rule from the
  one this release settled on, inside the same endpoint. `_purge_for_password_role`
  handed back the payload the destroy password decrypted *and* cleared the
  **other** entry; the rule is that a destroy password ends the entry it belongs
  to and never discloses. Both halves were the wrong way round. Replaced by
  `_clear_accessed_entry`, named for what it does. Only ever ran when no Vessel
  was registered, so no stored data behaved this way in practice — but a
  contradiction left in the tree is one somebody eventually builds on. (#192)
- Clearing a Face was impossible for anything the WebUI had protected.
  `destroy_face` and `destroy_vessel` asked only for the registry's
  `object_binding` fingerprint, which the CLI writes and the WebUI never does —
  the WebUI binds through the ORB cue store. Every attempt raised "object
  binding not registered", which `/destroy_face` reported as an ordinary
  rejection, indistinguishable from a wrong destroy password. Measured on a
  WebUI-stored Face: the destroy password verified and the call still failed.
  Both mechanisms are now accepted; only the *proof* differs, and either way
  the operator must be holding the right object at the moment they ask. This
  also repairs the CLI fallback the Runbook documents, which had the same
  blind spot. (#190)

### Added

- Doctor reports **Clearing Passwords**: how many set-up entries have a
  clearing password and how many do not. The mistake it catches is the one that
  happened on the device — set on one entry and not the other, discovered only
  when the missing one was needed, at which point "never set" and "wrong
  password" are indistinguishable *by design*, because the clearing path gives
  nothing away on failure (#191). Beforehand is the only place the difference
  can surface. Reported as counts and never as which entry: which one carries a
  clearing password is what the sealed registry sidecar exists to keep out of
  readable state (#180). INFO rather than WARN — unlike the environment
  variables in the check above it, nothing here fires without the operator
  typing that specific password, so an entry without one is a setup state, not
  an armed hazard. Suppressed under `PHASMID_FIELD_MODE`, following the Simple
  screen's cross-entry file total. (#194, CLM-47)
- `PHASMID_CUE_GOOD_MATCH_RATIO` and `PHASMID_CUE_INLIER_RATIO` — per-device
  tuning for the proportional cue thresholds below. Documented in
  `docs/CONFIGURATION.md`. (#188)

### Changed

- The TUI's Open Vessel operation runs on a worker instead of inline from the
  button handler. `collect_auth_sequence()` waits up to ten seconds for an
  object match; run inline, that froze the whole console for those ten seconds
  with nothing on screen to say why, which reads as a hang rather than as a
  device waiting to be shown something — the same defect as the generation
  freeze fixed in #156. Field validation now runs first, so a missing path or
  passphrase is reported the instant the button is pressed rather than after a
  wait the operation was never going to use, and an elapsed counter names what
  is being waited for. It deliberately says nothing about whether a match has
  happened: reporting live match state is the half of #158 that is in tension
  with giving limited detail on failed access, and that stays open. (#158)

### Removed

- `src/phasmid/dummy_generator.py`, which produced a directory of fabricated
  files — text, logs, JSON, CSV, binary stubs, with varied mtimes — to be
  presented as real. Nothing in `src/` imported it and no CLI, TUI or WebUI
  path called it, so no operator could run it; but `docs/CLAIMS.md` and
  `docs/IMPLEMENTATION_STATUS.md` described it as a capability, so a reader
  auditing this project would find it and conclude the tool manufactures cover
  stories. That is the position the project abandoned: **the operator supplies
  the material they would disclose.** (#165)

### Fixed

- A published claim was evidenced by tests of code that could not run. CLM-40 —
  "the free-space filler does not forge forensic artifacts, fake kernel logs, or
  perform timestamp forgery" — cited `tests/test_dummy_generator.py`, which
  tested the unreachable module above. The filler that actually ships is
  `VesselWorkflowService._build_generated_file_specs`, and **nothing tested it
  for that property**. New `tests/test_free_space_filler_content.py` holds the
  shipped filler to the claim: no system-log or forensic markers, no fabricated
  dates, deterministic output, and filenames that do not imply a provenance.
  CLM-37 and the implementation-status entries now point at the live code and
  its tests too. (#165)
- Anything that asked "is the bound object present?" was answered *no* whenever
  the matcher had been stopped — not because the object was absent, but because
  nothing was looking. A successful retrieval calls `access_cue_service.close()`
  to save power and heat, which stops the background matcher; the retrieve page
  restarted it on its next `/video_feed` request, so whether the answer was true
  depended on whether the browser had reconnected its preview yet. Reported from
  the device as the explicit clear panel refusing an object plainly in front of
  the camera, right after a successful retrieval. `/retrieve` and
  `/destroy_face` now resume the matcher and give it a bounded moment to settle,
  gated on a frame actually arriving so a device with no camera answers at once
  rather than standing still on every call. Free when the matcher is already
  running, which is the normal case. (#192)
- A bound object was refused at retrieval when it was plainly in front of the
  camera. `MIN_GOOD_MATCHES=50` / `MIN_INLIERS=30` are absolute counts
  calibrated when a reference template covered the whole frame and carried
  400-900 keypoints; masking the template to the object (#184) leaves 72 on a
  plain wall, and the same counts then demand that most of the template be
  re-found almost exactly. Measured on a 72-keypoint template: the identical
  frame scores 62 good matches, but ±6 of grayscale noise — less than a real
  sensor produces — drops it to 42, and only one of six presentations matched.
  The thresholds are now a proportion of the template's own keypoint count
  (25% good matches, 15% inliers), floored at 12/8 and **capped by the absolute
  counts, so nothing is ever stricter than before**. Safe because discrimination
  never came from the counts being high: on the same scene the empty view and a
  different object each score zero good matches, so the separation is 42-vs-0,
  not 42-vs-49. After the change all six presentations match and all four
  negative cases are still refused. (#188)
- Binding an access object failed on real hardware, and the failure was in the
  two-shot capture added for #184, not in how the object was presented. The
  scene and object frames were differenced after `cv2.equalizeHist`, which is a
  *global* remap driven by each frame's own histogram: holding an object up
  changes the mapping for the wall behind it too, so the difference stopped
  describing the object. Measured on a plain wall, the equalised difference left
  about an eighth of the object standing, and for a brighter object on the same
  wall left nothing at all — capture was refused every time. The difference is
  now taken on unequalised grayscale (`ObjectCueMatcher.to_diff_gray`), while
  ORB still describes the equalised image so the template lives in the same
  space as the frames it is later matched against. (#186)
- A capture could be accepted when the whole view changed rather than an object
  being placed in it. The area ceiling was applied to the largest connected
  region, and a wholly different view of the same room still has a largest
  region of object-like size. The ceiling now applies to the total changed area,
  and a new `MIN_OBJECT_DOMINANCE` requires that one region account for most of
  the change — measured at 0.96–1.00 for an object held up against 0.47 for a
  replaced view. The operator is told which of the two failures occurred, since
  "hold it closer" and "stop moving the camera" ask for opposite things. (#186)
- Deleting the last Vessel left its bound-object templates behind. The
  object-cue store is device-wide rather than scoped to a Vessel, so the next
  Store attempt found an entry already bound to an object belonging to data
  that no longer existed, and pushed the operator into the Replace confirmation
  flow instead of letting them bind. `create_vessel` already cleared them for
  this reason; `delete_vessel` now does too, but only when no Vessel is left to
  own them. (#186)

### Documentation

- Demo Runbook and Talk Script updated for the hardware-verified flow:
  two-shot capture in Step 2, the object held up through the save, and
  **Step 4 (object absent, retrieval refused) moved to the WebUI** now that the
  negative case is verified there. Step 3 and Step 4 run in the same tab, so the
  contrast changes only the object — not the screen. `Recover File` stays in the
  TUI as the fallback when the WebUI is unavailable, and the WebUI's five-failure
  lockout is called out, because rehearsing Step 4 there can consume it before
  the talk. A new Step 4b covers ending an entry with its destroy password from
  the same field, including the fact that **success is silent** — the only
  confirmation is that the entry no longer opens.
- `docs/CLAIMS.md` gains CLM-46 (a destroy password entered in the retrieval
  field ends the entry it belongs to, discloses nothing, and is answered
  identically to a mistyped password) and CLM-47 (Doctor reports clearing-password
  coverage as counts only, never which entry).

## [0.5.0] - 2026-07-30

> Closes a disclosure gap in local state and narrows the TUI to the operations
> the role-gated WebUI does not already cover. The **Vessel registry no longer
> stores Face credential material in cleartext**: per-Face volume, the profile
> identifying which Face holds generated filler, the bound object's perceptual
> fingerprints, and the destroy-passphrase verifier move into an encrypted
> sidecar under the local state key. A side effect worth having — a purged Face
> is now indistinguishable from a never-used one in what stays readable.
>
> This is a MINOR bump: no `vault.bin` format changed and no claim was removed
> from `docs/CLAIMS.md`, per [docs/VERSIONING.md](docs/VERSIONING.md). Note
> that the registry migration is **one-way** — see Migration below.

### Security

- `vessel_registry.json` held, in cleartext at mode `0600` in the config
  directory, each Face's `file_count` and `occupancy`, the `dummy_profile` that
  identifies which Face carries generated filler, the `object_binding`
  perceptual fingerprints of the bound access object, and `emergency_auth` — a
  scrypt verifier for that Face's destroy passphrase. The last two are
  credential material. All of it was readable by anyone holding the device as
  the logged-in user, with no passphrase and without launching Phasmid, which
  lands against the in-scope physical-captor and coercing-authority
  adversaries and needs no compromised host. The file is now split: a cleartext
  discovery index (paths, Vessel label, open bookkeeping, each Face's fixed
  `face_id`/`created_at`/`selector`) plus `vessel_registry.bin` in the state
  directory, AES-GCM under the local state key through the same
  `LocalStateCipher` the ORB blob and access-token store use. (#178, #180)
- A purge no longer leaves a signature in cleartext. `forget_face_contents()`
  still preserves `object_binding` and `emergency_auth` as credentials, but
  since those are now sealed, a purged Face (bound, credentialed, zero files)
  and a never-used one (unbound, uncredentialed, zero files) read identically
  without the state key. Previously the difference disclosed that data had been
  destroyed — the duress path's legal exposure without the deniability it
  exists for. (#180)
- Raised the destroy-passphrase verifier's KDF cost from the interactive tier
  (`scrypt n=2**14`, 16 MiB) to `n=2**15`, so `128*r*n` matches
  `ARGON2_MEMORY_COST` at 32 MiB, and recorded the KDF parameters alongside the
  hash so the cost can be raised again without invalidating passphrases already
  set. The verifier is kept rather than replaced by a check against the
  container: `destroy_face` and `destroy_vessel` overwrite raw bytes via
  `purge_mode`/`silent_brick` and must work on a container that cannot be
  decrypted. (#180)

### Added

- Doctor reports **Automatic Destruction**: a warning when an ordinary
  retrieval will destroy the Face it did not open, naming the specific setting
  — `PHASMID_DURESS_MODE` on, or `PHASMID_PURGE_CONFIRMATION` off. Both make
  the destruction silent and irreversible, and neither is visible while
  operating, so an operator who armed one weeks ago had no other reminder. A
  warning rather than an error, because the owner may have armed it
  deliberately. (#182)
- `scripts/pi_zero2w/run_demo_console.sh` forces both of those settings to
  their safe values and warns when it overrides an inherited one. Forced rather
  than defaulted: `${VAR:-0}` would preserve an inherited `1` and leave the
  trap armed. (#182)

### Changed

- TUI operations fully covered by the role-gated WebUI are **deactivated, not
  removed**: `Add File` is gone from the Open Vessel operation selector, and
  `Doctor` and `Inspect` from the Expert footer. The underlying service calls
  and screens are untouched and both remain reachable from the command palette.
  `Recover File` and `Audit` deliberately stay: they are still the verified way
  to demonstrate the object-absent refusal and to reach the audit view in one
  keypress. (#169 Phase 1, #177)
- The Expert footer's minimum safe terminal width drops from **145 to 124
  columns**, now that two bindings no longer occupy it. Below it, `w WebUI`
  leaves the footer silently — with no ellipsis — taking the key that retracts
  an exposed WebUI with it. (#177)
- Under `PHASMID_FIELD_MODE`, the Simple screen's `Files` column collapses to
  `-` instead of showing a cross-Face total. Outside Field Mode the total is
  deliberate: this console is the declared inspection surface, where the
  two-Face model is meant to be legible. (#179)

### Fixed

- `docs/TUI_OPERATOR_CONSOLE.md` claimed the Vessel registry stored "only
  non-secret metadata (file paths)" and never object keys or recovery secrets.
  Both were false. Replaced with the actual field inventory, and
  `THREAT_MODEL.md` gained a **Configuration Directory Surface** section, which
  had never mentioned the file at all. (#179)
- The test suite no longer reads or rewrites the operator's real
  `~/.config/phasmid/vessel_registry.json`. A stale registry from an earlier
  session made five cases fail with an assertion about a purge call that said
  nothing about the cause, and seven module-level tests rewrote that registry
  as a side effect. Not reproducible in CI, which starts from a clean runner.
  (#181)

### Migration

- The registry migrates on first load: the pre-split cleartext values are read
  as the source of truth, the sealed sidecar is written, the old bytes are
  overwritten, and the reduced index replaces them. No operator action needed.
- **The migration is one-way.** A build older than 0.5.0 reading the migrated
  registry finds no Face detail in the cleartext index and does not know about
  the sidecar, so Face bookkeeping, object bindings and destroy-passphrase
  verifiers would read as absent. Keep a copy of `vessel_registry.json` before
  upgrading if a downgrade path matters.
- On flash media, the pre-migration cleartext may persist in unlinked blocks.
  This project does not claim secure deletion there.
- Losing the local state key costs Face detail, never Vessel access: a missing,
  truncated, or wrong-key sidecar degrades to "no Face detail known". Under
  `PHASMID_TMPFS_STATE` that detail is volatile, consistent with the object-cue
  references that already live in a volatile state directory.

## [0.4.0] - 2026-07-29

> Adds role-scoped WebUI access: a **store** token reaches Face setup and
> registration, a **recover** token reaches only decrypt/destroy, with no Face
> selector or restricted-passphrase field anywhere in its surface. The legacy
> shared `PHASMID_WEB_TOKEN` still grants the store role until a role token is
> issued for either role, after which `/unlock` stops accepting it — pin
> `PHASMID_STORE_TOKEN`/`PHASMID_RECOVER_TOKEN` instead if a script or demo
> depends on a known value.
>
> This is a MINOR bump: the additions are backward compatible, no `vault.bin`
> format changed, and no claim in `docs/CLAIMS.md` was removed, per
> [docs/VERSIONING.md](docs/VERSIONING.md).

### Security

- `/unlock` refuses the legacy shared `PHASMID_WEB_TOKEN` the moment any role
  token has been issued for either role. `WEB_TOKEN` is embedded as the CSRF
  mutation guard in every unlocked page's HTML, recover-role sessions
  included; without this, reading a recover-role session's page source handed
  over what was needed to mint an independent, fresh store-role session
  through `/unlock`, defeating the reason the narrower role exists. A device
  that has not adopted role tokens yet is unaffected.
- A role mismatch on a gated WebUI route now returns a plain 404, verified
  byte-identical (status and body) to FastAPI's default response for an
  unregistered route, rather than a distinguishable 303 redirect or 403. The
  previous behavior let a recover-role session, or anyone probing the URL bar
  without ever holding a credential, confirm that a higher-privileged tier
  exists even though they could never reach it.
- The Open Vessel screen showed a Face selector and a labeled restricted
  recovery passphrase field for every operation, including Recover File — the
  operation an operator under duress would actually run. An onlooker who
  never learns any passphrase content still learned, from the form alone,
  that the Vessel has two alternate faces and two categories of credential.
  Recover File and List Files no longer show the Face selector, the input
  file field, or the restricted passphrase field; which face answers is
  resolved from the passphrase and object cue rather than picked from a menu.
  The WebUI's `/store` page and `/maintenance` surface carried the identical
  exposure, closed by the role-token system below.

### Added

- **Role-scoped WebUI access tokens.** A new `AccessTokenService` issues two
  tokens — **store** (Face setup, registration, and everything the recover
  role reaches) and **recover** (decrypt/destroy only) — persisting only a
  salted, encrypted-at-rest hash of each. Issuing or reissuing a token
  requires a live USB gadget interface, so granting either role happens with
  the operator's hands physically on the device over USB. A new TUI screen
  (`t`, Access Tokens) issues and revokes each role, showing a freshly issued
  token exactly once. `/unlock` now tags each WebUI session with a role, and
  the home page's Store card, Guided Mode link, and Advanced tools panel are
  hidden entirely for a recover-role session rather than left as dead links.
- `PHASMID_STORE_TOKEN` / `PHASMID_RECOVER_TOKEN` environment overrides pin
  the two role tokens to fixed values, mirroring the existing
  `PHASMID_WEB_TOKEN` pattern, so a demo or scripted run does not depend on a
  value the TUI shows once and that would otherwise have to be copied down by
  hand before going on stage.
- **Delete Vessel** (`del`, TUI Expert Home). Permanently scrambles and
  removes a Vessel file an operator is finished with, actually freeing the
  disk space — distinct from the existing duress `destroy-vessel` path, which
  deliberately keeps the container at its original size and path so an
  operator under coercion still has something to point to. A finished
  Vessel has no cover story left to preserve, so this requires no face
  credentials or emergency password, only the `DELETE VESSEL` confirmation.
- The WebUI Store page (`/store`) shows an explicit "Choose the entry" step,
  letting an operator deliberately set up Entry 1 and Entry 2 in turn rather
  than depending on whichever entry the camera happens to match or the dict
  iteration order of the first unbound one — the visible control the TUI's
  Add File screen already had.
- `scripts/pi_zero2w/run_demo_console.sh`: launches the operator console with
  the environment the live demo depends on — silenced libcamera logs so they
  do not overwrite the TUI, gadget exposure opt-in, pinned demo role tokens,
  deterministic recognition mode, and disabled terminal flow control so
  `Ctrl+S` (Silent Standby) is not swallowed as XOFF.
- `scripts/pi_zero2w/run_demo_smoke_test.sh`: pre-demo smoke test for the target
  device. Asserts bind-host resolution, WebUI startup, access-token publication
  and permissions, the `/unlock` page-session flow, the Silent Standby
  transitions, and clean shutdown, then prints the steps that require a human.
  Uses a scratch state directory and port 8099 so a running operator WebUI and
  the real state directory are untouched. Exits non-zero on any failed check.

### Fixed

- Creating a Vessel at the console's default size could kill the process with
  an out-of-memory error on a Raspberry Pi Zero 2 W: `format_container`,
  `silent_brick`, `purge_mode`, and `randomize_slot` all filled their span
  with a single `os.urandom()` call, which allocates the whole request at
  once. All four now write in 1 MiB chunks. This matters most for
  `silent_brick`, the duress-destroy operation the design leans on — an
  operator whose container did not fit in RAM was exactly the operator whose
  destroy would have been killed mid-run.
- Closing a WebUI camera-view browser tab could silently freeze the TUI's own
  object-cue matching until the whole console was restarted. `generate_frames()`
  is called by two independent, concurrent consumers on the one shared camera
  — the TUI's always-on background matcher and a fresh call per WebUI
  `/video_feed` request — and its `finally` clause released the camera
  whenever *either* caller's generator exited. Active callers are now
  reference-counted so the hardware is only released once the last one exits.
- A successful WebUI Retrieve stops the shared camera to save power and heat;
  nothing but the TUI's Open Vessel action ever restarted it. A Store/Retrieve
  session driven entirely from the WebUI — the flow the role-token system
  above is built around — left the camera preview permanently blank after the
  first successful retrieval, with the match badge frozen on its last value.
  `/store`, `/retrieve`, and `/video_feed` now restart the camera (a no-op if
  already running) before serving.
- Creating a new Vessel did not reset the physical-object cue store, a
  device-wide singleton rather than something scoped to any one Vessel file.
  A cue left over from a deleted or unrelated Vessel made the very first
  Store attempt on a brand new Vessel look already bound to an object that
  had nothing to do with it, forcing an operator through the Replace
  confirmation flow to register Face 1/Face 2 on a Vessel just created.
  `create_vessel()` now clears the cue store as part of initializing a new
  Vessel.
- The Simple Operator home screen carried only the shared top banner for an
  exposed WebUI. Expert's dedicated in-body warning panel makes the exposure
  much harder to miss; going unnoticed on the Simple screen was observed live
  when the WebUI was started while Expert was the active screen. Simple now
  carries the same dedicated warning panel, wired the same way.
- The Simple Operator home screen's title was a bare static "PHASMID" string;
  it now uses the same responsive banner Expert does, so terminal-width
  behavior and appearance match between the two screens.
- The WebUI and the TUI console operated on different storage: `web_server.py`
  held its own module-level `PhasmidVault("vault.bin")` and stored/retrieved
  straight through it, so a file saved from a browser never appeared in any
  Vessel, in Audit, or in Vessel Status. The WebUI now stores and retrieves
  through the same `VesselWorkflowService` the console uses, resolving its
  target Vessel via `PHASMID_WEB_VESSEL`, then the most recently opened
  Vessel in the console's registry, then the legacy container.
- Standby could display the WebUI's access token in plain text: Textual
  notifications render on the app's overlay and survive a screen push, so
  exposing the WebUI and then triggering Silent Standby left a 30-second
  toast carrying the URL and token sitting on the one screen meant to show
  nothing sensitive. Standby now clears pending notifications, and no longer
  advertises `w` (expose WebUI) in its footer, since acting on it there would
  re-expose the surface Standby just concealed.
- Silent Standby concealed the local screen but never touched the WebUI
  server: it kept serving on the USB gadget address throughout standby,
  reachable from a tethered laptop while the device screen showed an
  innocuous page. Standby now retracts the WebUI and reports it on recovery;
  it is not restarted automatically, since re-exposing the interface should
  be an explicit operator decision.
- Rich markup silently stripped bracketed key names (`[w]`, `[e]`, `[n]`,
  `[g]`, `[d]`) out of several user-facing strings, including the only
  on-screen instruction for retracting an exposed WebUI. Key names are now
  escaped (`\[x]`) wherever they name a literal key rather than markup.
- Silent Standby and the context-profile screen crashed on push: both
  declared `border: solid $text-muted`, an auto-contrast token Textual
  accepts for `color` but rejects for `border`. Triggering Silent Standby
  (`Ctrl+S`) crashed the app instead of concealing the sensitive UI — the
  opposite of what the feature exists for.
- Plausibility (Free Space Filler) generation ran inline on the UI thread and
  measured at roughly four minutes for a 64 MiB Vessel — four minutes of a
  completely unresponsive console with no feedback, indistinguishable from a
  crash. It now runs on a worker thread with elapsed time shown and the
  plausibility buttons disabled while it works.
- The Expert footer silently dropped `w`/`q`/`?` (and, at narrower widths,
  further bindings) below its safe minimum column count, with no visual
  indication the row was incomplete — footer cells sit at fixed offsets
  rather than compressing to fit. Hiding the LUKS binding while the LUKS
  layer is disabled by default, and gating it correctly the two times this
  cycle a new binding (Access Tokens, Delete Vessel) raised the threshold
  again, keeps the documented minimum in `docs/submissions/Phasmid_Demo_Runbook.md`
  (now 145 columns) matched to what the running application actually needs.
- The Doctor advisory's "not configured" gate tested whether the default
  container/profile paths exist, or resolved an unset variable to an empty
  string (`Path("")` is the working directory, which always exists). Any
  device that had ever stored to the unnamed default container failed the
  gate and got the full warning storm it exists to avoid; an empty override
  silently measured the console's own working directory. It now reads the
  environment variables that express operator intent instead of the
  filesystem.
- The Face Manager panel, retitled "Free Space Filler", still displayed a
  plausibility verdict (`Level: HIGH  Score: 87`) underneath — a judgement on
  how convincing the disclosure material is, the one thing the note directly
  below it disclaims and the tool cannot assess. It reports volume only now.
- Empty-state copy on the Simple Operator home screen never cleared once a
  Vessel existed: `_refresh_table` only ever assigned the "No protected
  storage found" text and never restored the default, so it kept
  contradicting the vessel table listed directly above it.

- Expert controls are no longer a one-way trip. `escape` returns to the Simple
  Operator screen, matching every other pushed screen in the TUI; previously the
  only way out was `q`, which quits the application, so reaching Expert controls
  ended the simple surface for the rest of the session. The protected storage
  list is refreshed on return, so work done in Expert controls is reflected
  immediately. `docs/TUI_OPERATOR_CONSOLE.md` documented the old behaviour as a
  caveat and now documents the return path and the full Expert key table.
- `scripts/pi_zero2w/run_webui_probe.sh` asserted only that `curl` did not fail.
  Since 0.3.0 a non-loopback peer without a page session is redirected to
  `/unlock`, and `curl -sf` treats that 303 as success, so the probe would time
  an empty redirect and report meaningless latency. It now requires HTTP 200 and
  fails with an explanation when it sees the unlock redirect.
- `scripts/bootstrap_pi.sh` aborted before it created the virtualenv on
  Raspberry Pi OS Trixie. The apt package list named `libatlas-base-dev`, which
  Debian 13 dropped, and `set -e` turned that one missing candidate into a total
  failure: no `.venv`, no editable install, no usable device, from a script whose
  whole job is to produce one. The list now names `libopenblas-dev`, which the
  supported releases ship and which `scripts/pi_zero2w/README.md` and
  `docs/PI_ZERO2W_FIELD_TEST.md` already prescribed, so the repository no longer
  contradicts itself about its own dependencies. Packages with no installation
  candidate are reported and skipped instead of ending the run, because the BLAS
  development headers only matter when no wheel is available and numpy has to be
  built from source.
- `scripts/validate_pi_environment.sh` recorded Stage A as failed on every run
  under Python 3.13. The probe did `import importlib` and then called
  `importlib.util.find_spec`; importing the parent package does not bind `util`
  as an attribute, so the check raised `AttributeError` and was recorded as a
  missing-import failure while picamera2, cv2 and numpy were in fact all
  importable. It now imports `importlib.util` directly.
- `.gitignore` did not cover `_pi_field_test/`, the directory that
  `scripts/pi_zero2w/run_remote_perf.sh` and
  `scripts/pi_zero2w/run_demo_smoke_test.sh` write their results into.
  Running either left the working tree dirty for good, so every device that
  had been field tested reported untracked output on each `git status` and a
  real untracked change was easy to lose among it. Parts of the contents were
  already covered by the `vault.bin`, `*.bin` and `.state/` patterns; the
  directory itself was not.

### Changed

- The demo launch script and runbook pin `PHASMID_STORE_TOKEN` /
  `PHASMID_RECOVER_TOKEN` rather than the legacy `PHASMID_WEB_TOKEN`, since
  `/unlock` stops accepting the legacy token the moment any role token
  exists; the pre-staged browser tab for the runbook's show-only step now
  unlocks with the Recover token, the role with nothing to disclose.
- The DEF CON Demo Labs materials (runbook, talk script, deck) are revised to
  v4 to match the settled product model: the operator supplies both the
  material they would disclose and the material they would withhold, and the
  restricted credential destroys under coercion rather than fabricating a
  false disclosure. The demo walkthrough now includes recovering with the
  object absent, refused after ten seconds — without that contrast, a
  successful recovery alone does not demonstrate that the object cue gates
  anything.

- The DEF CON Demo Labs materials described a TUI that no longer exists. The
  runbook, the talk script and slide 24 of the deck all documented one command
  bar -- `o c i f g a d s l ? q w` -- which 0.2.0 replaced with a two-layer
  surface: a Simple Operator home screen and Expert controls behind `e`.
  Following the old sequence on stage would have pressed `c` for Create and `f`
  for Faces on a screen that binds neither, and the deck would have projected a
  key bar the audience could see did not match the live terminal beside it. All
  three artifacts now match the 0.3.0 build, checked against the running
  application rather than read off the source: the home footer, the expert
  footer, `Ctrl+S` for Silent Standby with `Ctrl+R` or `Esc` to recover, and `w`
  as an application-level binding that works from either screen. Three of the
  runbook's open fill-ins are closed as a result, including the Silent Standby
  key, which the demo's climax depended on and which was still blank.
- `README.md` named Bookworm and Bullseye as the deployment targets. Bullseye
  ships Python 3.9 and cannot satisfy the Python 3.10 requirement stated two rows
  above it in the same table. The row now names Trixie and Bookworm and states
  the 64-bit requirement the install path already depended on; a note below the
  table records why 32-bit and Bullseye are excluded.
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
