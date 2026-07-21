# Phasmid DEF CON Demo Labs — Demo Runbook

Operator runbook for presenting Phasmid at a DEF CON Demo Labs station (repeating
pitch plus a live tabletop demo). This document is the event-specific demo profile;
it sits on top of the shared, event-neutral [`COMMON_DEMO_RUNBOOK.md`](COMMON_DEMO_RUNBOOK.md)
and must stay aligned with [`../CLAIMS.md`](../CLAIMS.md) and
[`../NON_CLAIMS.md`](../NON_CLAIMS.md).

- **Presenter:** Makoto Sugita (Mr. Rabbit / `01rabbit`)
- **Format:** Demo Labs station — ~10–12 min core loop plus a 2–5 min live demo
- **Product position:** a coercion-aware deniable-storage research prototype — local disclosure control, not anti-forensics

---

## 1. Purpose

Show that encrypted storage can be technically correct while the *disclosure workflow*
still endangers the person holding the device. Phasmid reframes the problem around
compelled access, device seizure, over-disclosure, and unsafe fail-closed behavior, and
demonstrates a local-only, coercion-aware alternative: controlled disclosure instead of
all-or-nothing unlock.

The demo must leave a visitor with three things: the **Janus two-slot idea**, the
**object cue is a cue, not a key** distinction, and the **honest scope** (what Phasmid
does *not* claim).

## 2. Demo story

> They don't break your crypto — they take the device and make you open it. Full-disk
> encryption is all-or-nothing, so opening it under pressure exposes everything. Phasmid
> adds a layer above storage: show a plausible, ordinary surface under pressure while
> protected local state stays off the visible path — and route to a prepared dummy
> disclosure instead of failing loudly.

Core narrative path (mirrors the speaker script in
[`DEFCON_DEMO_LABS_SCRIPT.md`](DEFCON_DEMO_LABS_SCRIPT.md)):
**problem / over-disclosure → Janus two-slot model → object cue (a cue, not a key) →
coercion-safe delaying → Prepare→Bind→Operate→Disclose → honest scope → live demo.**

## 3. What the demo proves

- **Local-only:** vessel creation and operation need no cloud service, remote unlock, or network path.
- **Two faces:** one vessel presents an ordinary disclosed surface while protected state stays off the visible path.
- **Object cue, not a key:** an everyday object operates the access gate and policy checks; it is not the encryption key, and a photo of it unlocks nothing.
- **Coercion-safe fallback:** Silent Standby clears the sensitive UI and seals the session; low-confidence recognition can route to a prepared dummy disclosure instead of an obvious access-denied loop.
- **Honest limits:** the Audit view states the non-claims in plain language.

## 4. Required components

**Hardware (tabletop):**

- Raspberry Pi Zero 2 W in a 3D-printed case, with a camera for the object cue, on a mini tripod.
- An everyday object to use as the cue (kept in hand / on the table).
- Host laptop or the appliance itself running the TUI; the WebUI is reached over USB at `127.0.0.1`.

**Software / state (verify before the session):**

- `./phasmid` starts and opens the Main Operator Console (TUI).
- A demo Vessel can be created (deniable container file).
- A context profile is selected and a plausible dummy dataset is prepared **in advance**.
- `phasmid doctor` and `phasmid audit` open cleanly.
- No real or sensitive data is loaded. No demo step requires internet access.

**Screens to have ready** (`images/`): `TUI_HOME`, `TUI_FACE`, `TUI_AUDIT`, `TUI_DOCTOR`
as fallbacks if live hardware misbehaves.

## 5. Demo modes

Both modes drive the same real operator console — there is no separate "demo screen".

### 5.1 Live TUI demo (primary)

Operate the real TUI on the tabletop hardware and narrate as you go. This is the default
and the most engaging path for a Demo Labs station.

### 5.2 Guided walkthrough (reproducible fallback)

Use the built-in Guided Workflows (`g`) — `coerced_disclosure`, `headerless_inspection`,
`multiple_faces`, `safety_checklist` — and the camera-independent recognition routing.
This survives camera or lighting problems and stays reproducible at a noisy booth.

### 5.3 Recorded clip (hard fallback)

If the hardware fails entirely, narrate over the `TUI_*` screenshots and a pre-recorded
session clip. Prepare this clip in advance.

## 6. Pre-demo checklist

- [ ] `./phasmid` launches; Main Operator Console renders (terminal ≥ 100×30).
- [ ] Demo Vessel exists, or can be created live (`c`).
- [ ] Context profile selected; dummy dataset prepared and **plausibility report resolved** (`a` → Audit).
- [ ] Object cue registered under Faces (`f`), and the physical cue object is on the table.
- [ ] Silent Standby hotkey (default `Ctrl+S`) confirmed working; re-auth confirmed required.
- [ ] `coercion_safe` recognition mode set for the fallback portion (it is **opt-in / disabled by default**).
- [ ] WebUI toggle (`w`) starts/stops cleanly and shows the `⚠️ WEBUI ACTIVE (EXPOSED)` banner.
- [ ] `phasmid doctor` shows the disclaimer line: *"This check reduces obvious mistakes. It does not certify the host as secure."*
- [ ] Fallback screenshots and recorded clip on hand.
- [ ] Stickers out; repo URL visible.

## 7. Demo sequence

Six steps. Keep talking short — move your hands, point at the screen, watch the bottom bar.

### 7.1 Create — a deniable container

- **Do:** `c` → create a Vessel.
- **Show:** headerless container; local-only posture; local state path.
- **Speak:** *"This vessel is local-only and headerless — no cloud service, no magic bytes."*

### 7.2 Faces — register the object cue (the Janus two faces)

- **Do:** `f` → add / show Disclosure Faces; associate the object cue.
- **Show:** neutral face labels; the cue drives operation, not decryption.
- **Speak:** *"The object is a cue, not a key. It decides whether you get to act — it is not the encryption key, and a photo of it unlocks nothing."*

### 7.3 Guided — Prepare → Bind → Operate

- **Do:** `g` → run the guided prepare → bind → operate flow.
- **Show:** binding to local state and the object cue; operation through the console.
- **Speak:** *"Prepare a vessel, bind it to local state and the cue, then operate — controlled, under documented assumptions."*

### 7.4 Audit — dummy-profile plausibility

- **Do:** `a` → Audit view; show the dummy profile plausibility assessment and the non-claims section.
- **Show:** plausibility is prepared in advance and scored; non-claims are stated plainly.
- **Speak:** *"Plausibility is prepared before any pressure — it is not fabricated on demand. And here are the things we do not claim."*

### 7.5 WebUI — local, over USB

- **Do:** `w` → start the WebUI; point to `127.0.0.1:8000` reached over USB; show the exposure banner.
- **Show:** localhost / USB-gadget binding, no public network; auto-kill after 10 min idle.
- **Speak:** *"The WebUI is local — over USB at localhost. It never touches a network, and it retracts itself when idle."*

### 7.6 Silent Standby — hotkey → dummy disclosure

- **Do:** press the standby hotkey (`Ctrl+S`); show the sensitive UI cleared and the session sealed; in `coercion_safe` mode, show the natural route to `dummy_disclosure`.
- **Show:** `active → standby → sealed`; recovery requires re-authentication; no "access denied" loop.
- **Speak:** *"Silent Standby drops the sensitive UI into a harmless state and seals the session. Recovery needs re-auth. Under coercion-safe mode, a low-confidence match routes to the prepared dummy path instead of failing loudly. It removes the UI surface — it is not memory erasure."*

## 8. What to show on screen

- The Main Operator Console (`TUI_HOME`) as the default reference — vessels, vessel status, operator log, command bar.
- The Faces manager for the object-cue idea; the Audit manifest for plausibility and non-claims; Doctor for the honesty disclaimer.
- The bottom command bar and status line during Silent Standby — that transition is the payoff.
- Keep public screenshot exposure minimal; the Home screen is the safe default image.

## 9. Suggested talk track

### 9.1 Short version (station loop)

*"Phasmid is local-only, coercion-aware storage for the moment someone has both your
device and you. Two faces on one vessel — show a plausible ordinary surface under
pressure, keep protected state off the visible path. You operate it with an everyday
object as a cue — a cue, not a key. Under pressure, Silent Standby seals the session and
a prepared dummy disclosure carries the moment. Honest limits included — it buys
uncertainty and time, it does not claim forensic invisibility."*

### 9.2 If asked "is this live?"

Yes — it is the real operator console and the real pipeline. Injected demo inputs and
camera-independent routing are for reproducibility at the booth; they are not the normal
operating model.

### 9.3 If asked "is the object cue biometrics?"

No. It is a cue that drives operation and policy checks, not the encryption key and not a
biometric credential. The crypto stays with Argon2id and AES-256-GCM.

### 9.4 If asked about LUKS / full-disk encryption

Phasmid is a disclosure-control layer, not a replacement for audited full-disk
encryption. The TUI can sit alongside a LUKS layer; device-level encryption remains out
of Phasmid's scope.

### 9.5 If asked "does it really protect after seizure?"

Host compromise and kernel capture are out of scope — if the host is owned, no user-space
tool saves you. Phasmid increases uncertainty and delays confident conclusions; that is
the claim, and the non-claims are stated in the Audit view.

## 10. Failure fallback

Cascading hierarchy — always keep a working path:

1. **Camera / lighting problems** → switch to Guided Workflows and camera-independent recognition routing (§5.2).
2. **TUI or hardware instability** → narrate over the `TUI_*` screenshots and the recorded clip (§5.3).
3. **Total station failure** → deliver the short talk track (§9.1) with the printed one-pager and stickers; point to the repo.

Never describe injected inputs or booth fallbacks as the normal operating model.

## 11. What not to show first / what not to say

- Do not lead with optional or peripheral integrations; lead with the Janus idea, the object-cue distinction, and honest scope.
- Do not use the words `real`, `fake`, `true`, `decoy`, or `hidden truth` for faces during ordinary operation — use neutral `Disclosure Face` labels.
- Do not use `self-destruct`, `secure delete`, `anti-forensics`, `investigator deception`, `undetectable`, `unbreakable`, `military-grade`, or `guaranteed safe`. Use `passphrase`, `object cue`, `local access path`, `plausible disclosure`, `coerced disclosure`, `best-effort`.
- Do not claim forensic invisibility, perfect deniability, secure deletion on flash, or protection from a compromised host. No snake oil.

## 12. Reset between runs

- Return from Silent Standby via re-authentication (no silent re-entry).
- Stop the WebUI (`w`) so the exposure banner clears and the station returns to a quiet state.
- Reset local generated demo assets if a clean baseline is needed (confirmation required).
- Confirm no real data was introduced during the session.

## 13. Claims and non-claims to keep visible

Keep the Audit view reachable and read 2–3 non-claims aloud during §7.4. Anchor points
(verbatim from [`../NON_CLAIMS.md`](../NON_CLAIMS.md)):

- Phasmid does not provide perfect deniability.
- Phasmid does not provide protection against compromised hosts.
- Phasmid does not bypass forensic tools or claim forensic invisibility.
- Silent Standby does not erase key material from process memory.
- Dummy plausibility is entirely dependent on operator preparation.

## 14. Evidence checklist

- [ ] Screenshot of each of the six demo steps.
- [ ] One full session screen capture (or the recorded clip used).
- [ ] One constrained-device (Pi Zero 2 W) run confirmation.
- [ ] Exact version / tag used in the demo.
- [ ] Confirmation that no demo step required internet access and no sensitive data was used.

## 15. Related documents

- [`COMMON_DEMO_RUNBOOK.md`](COMMON_DEMO_RUNBOOK.md) — shared, event-neutral fixed demo sequence
- [`DEFCON_DEMO_LABS_SCRIPT.md`](DEFCON_DEMO_LABS_SCRIPT.md) — full speaker script (talk track + staging)
- [`../TUI_OPERATOR_CONSOLE.md`](../TUI_OPERATOR_CONSOLE.md) — TUI keys, screens, and command reference
- [`../COERCION_SAFE_DELAYING.md`](../COERCION_SAFE_DELAYING.md) — Silent Standby, dummy datasets, context profiles, recognition modes
- [`../JANUS_EIDOLON_SYSTEM.md`](../JANUS_EIDOLON_SYSTEM.md) — two-slot architecture
- [`../CLAIMS.md`](../CLAIMS.md) · [`../NON_CLAIMS.md`](../NON_CLAIMS.md) — claims / non-claims inventory
- [`../SEIZURE_REVIEW_CHECKLIST.md`](../SEIZURE_REVIEW_CHECKLIST.md) — seizure-condition review checklist
