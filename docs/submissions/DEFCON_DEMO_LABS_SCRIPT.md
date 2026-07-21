# Phasmid — DEF CON Demo Labs — Speaker Script

Companion talk track for `Phasmid_DEFCON_DemoLabs.pptx` (24 slides). The English lines are
what the presenter says at the station; the `[STAGE]` notes are delivery/staging cues and are
not read aloud. Every English line is also embedded verbatim in the corresponding slide's
speaker notes inside the `.pptx`.

- **Presenter:** Makoto Sugita (Mr. Rabbit / `01rabbit`)
- **Format:** Demo Labs station — repeating pitch plus a live tabletop demo
- **Timing:** core loop ~10–12 min plus a 2–5 min demo
- **Core path:** 1 → 6 → 11 → 12 → 13 → 15 → 17 → 20 → 21 → 22 → 24
- **`[DEPTH]` slides** (7, 8, 10, 16, 18, 19): expand only when the audience bites; otherwise skim.

---

### Slide 1 — Title ⏱0:20
"Hey, thanks for stopping by. This is Phasmid — the reference build of what I call the Janus Eidolon System. Local-only, coercion-aware storage, built for the moment someone has both your device and you. I'm Makoto Sugita — Mr. Rabbit."
`[STAGE]` Keep the hook short. Point to the banner once, then get into it.

### Slide 2 — whoami ⏱0:30
"Quick background: independent security researcher and open-source tool developer, penetration tester by trade, CISSP. I turn offensive experience into defensive tools — deception, delaying action, coercion-aware design. You may have seen my other work, the Azazel system and the PAKURI family, at Black Hat Arsenal, BSides, SecTor, CODE BLUE. Find me at 01rabbit on GitHub."
`[STAGE]` Move through the bio. Point to the GitHub handle.

### Slide 3 — The Problem ⏱0:40
"Here's the problem Phasmid is built for. Attackers today don't need to break your crypto. They take the device — at a border, a checkpoint, an arrest — and they ask you to unlock it. And full-disk encryption is all-or-nothing: the moment you open it under pressure, everything is exposed. That's over-disclosure."
`[STAGE]` Deliver the gravity plainly, not dramatically.

### Slide 4 — Pick your fate ⏱0:20
"So you get three bad options. Refuse — and you escalate. Comply with full-disk encryption — and you hand over everything. Or... controlled disclosure — show what's visible, protect the rest. Same demand, very different blast radius."
`[STAGE]` Light laugh here. Keep the tempo up.

### Slide 5 — What it is / isn't ⏱0:30
"Let me be precise. Phasmid is a field-evaluation research prototype for disclosure control — not casual file encryption, local-only by default. And it is not a replacement for audited full-disk encryption, not hardware-backed keys, not a magic delete button. I'll keep drawing that line the whole way through."
`[STAGE]` Declare the honesty up front. Gesture across the IS panel, then the ISN'T panel.

### Slide 6 — Core idea: Janus ⏱0:40
"The core idea is Janus — two faces. A two-slot model. Slot A is what a capture-visible surface shows: plausible, ordinary, disclosed under pressure. Slot B is protected local state, kept off the visible path, bound to local conditions — not just a password. What you show is not all there is."
`[STAGE]` Point to the two slots left/right. This is the conceptual core.

### Slide 7 — Adversary model ⏱0:40 `[DEPTH]`
"Who does it defend against? Five in-scope adversaries — physical captor, passive observer, local active attacker, local-network attacker, and a coercing authority. And, just as important, five out of scope: a compromised kernel, hardware implants, remote attackers, supply-chain, and breaking the crypto itself. If the host is owned, no user-space tool saves you — and I won't pretend otherwise."
`[STAGE]` Expand for the threat-model crowd. Otherwise one line: "who we fight, and who we don't."

### Slide 8 — STRIDE + LINDDUN ⏱0:20 `[DEPTH]`
"For the threat-model folks: eighteen scenarios, each tagged with STRIDE and LINDDUN — offline cracking, session replay, header leakage, timing side-channels, coerced disclosure. It's all written down in the repo."
`[STAGE]` Usually skim. If the forensics/research crowd bites, point to a representative row.

### Slide 9 — Architecture boundary ⏱0:30
"Architecturally, four things stay explicit: two-slot storage, local access-key mixing, a restricted-action policy that gates sensitive behavior, and capture-visible discipline — normal flows never expose the structure, the recovery path, or the trial order."
`[STAGE]` Move fast through the four points.

### Slide 10 — Layers & document map ⏱0:20 `[DEPTH]`
"Under that, narrow local layers — entry points, policy, crypto core, local state, deployment. And it's all documented: specification, threat model, the formal Janus spec, the delaying-architecture doc."
`[STAGE]` Skim. Just convey "it's properly documented."

### Slide 11 — Three pillars ⏱0:30
"Three moving parts. One — an encrypted local vessel: authenticated encryption, password-derived keys. Two — object-cue operation; I'll come right back to this, it's the fun part. Three — controlled disclosure: workflows that separate what's shown from what's protected."
`[STAGE]` Tease pillar 2, pull to the next slide.

### Slide 12 — The object is a cue, not a key ⏱0:40 ★
"Here's the fun part. You show an everyday object to the camera to operate the access gate — nothing to type, nothing that looks like a secret. But this matters: the object is a cue, not a key. It drives operation and policy checks. It is not the encryption key. A photo of the object unlocks nothing. The crypto stays with Argon2id and AES-GCM — the object just decides whether you get to act."
`[STAGE]` The key differentiator. Slow down. Stress "cue, not a key." You can hold up a physical object here.

### Slide 13 — Coercion-safe delaying ⏱0:40
"This is what makes it coercion-safe. Silent Standby — a hotkey drops the sensitive UI into a harmless state; recovery needs re-auth. A plausible dummy dataset, prepared before any coercion and scored for plausibility. And context profiles — travel, field engineer, researcher — that shape what 'normal' looks like. In coercion-safe mode, a low-confidence match routes to the dummy path instead of failing loudly."
`[STAGE]` Note that Silent Standby will be demoed later.

### Slide 14 — Design principle: Restraint ⏱0:30
"The principle is restraint. The vault file alone isn't meant to be enough. Normal flows don't reveal structure or recovery. Metadata reduction is best-effort — I call it support, not sanitization. Restraint is the feature, not a limitation."
`[STAGE]` Skim. Keep the honest tone.

### Slide 15 — Flow: Prepare → Bind → Operate → Disclose ⏱0:30
"Operationally it's four steps: Prepare a vessel, Bind it to local state and the object cue, Operate through CLI, TUI, or local WebUI, and Disclose — controlled, under documented assumptions."
`[STAGE]` Point to the four steps in order. This is the map for the demo.

### Slide 16 — Tech: small, local, boring ⏱0:30 `[DEPTH]`
"Small, local, boring by design. Argon2id for key derivation, AES-GCM for authenticated encryption, WebUI bound to localhost, running on a Pi Zero 2 W. Tuned parameters, per-record encryption, no plaintext header."
`[STAGE]` For the tech crowd. Numbers only if asked.

### Slide 17 — Field hardware ⏱0:40 ★
"And here's the actual thing. A Pi Zero 2 W in a 3D-printed case, a camera for the object cue, on a little tripod. The WebUI is reached over USB at localhost — it never touches a network. It's meant to read as an unremarkable small gadget. It's right here on the table — come look after."
`[STAGE]` Point to / lift the real device. Bridge to the tabletop demo.

### Slide 18 — Cryptographic core (v3) ⏱0:20 `[DEPTH]`
"For the crypto people: Argon2id with mixed-in local access-key material and device binding, an optional external secret as a third factor, AES-GCM per record with authenticated metadata, and no plaintext marker in the vault. Details are in the repo."
`[STAGE]` Skim. Q&A hook.

### Slide 19 — Operational guards ⏱0:20 `[DEPTH]`
"The WebUI is hardened: localhost binding, per-process tokens, a restricted-confirmation session, attempt limiting, rate limiting, inactivity auto-kill, hardened headers, and an opt-in, HMAC-chained audit log."
`[STAGE]` Skim. For ops/defense questions.

### Slide 20 — Design ethics: will & won't ⏱0:40 ★
"Now the ethics — and this matters at DEF CON. Phasmid allows plausible controlled disclosure, standby, ambiguity-preserving workflows. It explicitly disallows rootkits, kernel-level hiding, anti-forensic destruction, forensic-tool bypass, fabricating false events or timestamps. It increases uncertainty and delays confident conclusions — it does not claim forensic invisibility."
`[STAGE]` Be honest with the forensics/LE audience. Make eye contact here.

### Slide 21 — Scope, honestly drawn ⏱0:30
"Scope, drawn honestly. Software-existence concealment: out. Data-existence deniability: partial. Controlled disclosure: in, and central. Coercion-aware fallback: in. And what it never claims — perfect deniability, forensic immunity, secure deletion on flash, protection from a compromised host. No snake oil."
`[STAGE]` The honesty close. Then move to the demo.

### Slide 22 — Live demo (real TUI) ⏱2:00–5:00 ★
"Let me show you. This is the real TUI — Local Disclosure Control. I'll create a vessel — a deniable container — set the object cue under Faces, run the Guided prepare-bind-operate flow, check dummy-profile plausibility in Audit, launch the local WebUI, then trigger Silent Standby with a hotkey and show the dummy disclosure. Watch the bottom bar."

Demo run:
1. **Create** → make a Vessel (deniable container)
2. **Faces** → register the object cue (the Janus two faces)
3. **Guided** → prepare → bind → operate
4. **Audit** → dummy-profile plausibility
5. **WebUI** → show the `127.0.0.1` launch
6. **Silent Standby** (hotkey) → transition to `dummy_disclosure`

`[STAGE]` Fallback: if the hardware misbehaves, switch to the TUI images on this slide and narrate; a recorded clip is recommended. Don't over-talk — move your hands, point at the screen.

### Slide 23 — Quick start ⏱0:20
"Want to try it? Clone the repo, cd in, run `./phasmid` — first run sets up a venv and opens the console. Research software, Apache-2.0. Evaluate it locally, in field-test conditions — not as production protection."
`[STAGE]` Point to the repo URL on screen. Bridge into stickers.

### Slide 24 — Closing ⏱0:20
"That's Phasmid — local-only, coercion-aware storage, honest limits included. Code, threat model, and architecture are all on GitHub at 01rabbit. Grab a sticker — and please, come break it. Questions?"
`[STAGE]` Point to stickers → Q&A. Say the handle one more time.

---

## Anticipated Q&A

- **Relationship to LUKS?** — The TUI has a LUKS integration, but Phasmid is a disclosure-control layer, not a replacement for full-disk encryption (slides 5, 21).
- **Deniability?** — Data-existence deniability is *partial*; perfect deniability is not claimed (slide 21).
- **Does it really protect after seizure?** — Host compromise and kernel capture are out of scope (slide 7). What it buys you is uncertainty and time (slide 20).
- **Is the object-cue biometrics?** — No. It's a cue, not a key (slide 12).
