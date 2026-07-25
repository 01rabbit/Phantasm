# Phasmid — DEF CON Demo Labs 台本（30分プレゼン版 / Full Script）

**Deck:** Phasmid_DEFCON_DemoLabs.pptx（全26枚 / 各スライドに同内容のスピーカーノート埋め込み済み）
**Presenter:** Makoto Sugita (Mr.Rabbit / 01rabbit)

## 枠のルール / Format
- **1枠45分・毎時00分開始・45分ハード停止（非交渉）。** 推奨は「コンテンツ30分＋Q&A/交流15分」。
- 本台本は**安全側でコンテンツ約27〜28分**に設計。開始遅延・デモ延伸を吸収し、Q&Aを15分以上確保する。
- **英語**＝壇上で話す言葉。**日本語**＝演出・進行指示（読み上げない）。行頭 `[MM:SS]` は開始からの**経過時刻の目安**。

## 進行原則 / Delivery principles
1. 各スライドは「経過時刻」を目標に。**遅れたら深掘りスライド（STRIDE / Crypto core / Guards）を短縮**して取り戻す。
2. デモは山場。**約7分で切り上げ**、時計を見て延伸しない。
3. 深い技術論争は歓迎しつつ**Q&Aへ誘導**（"find me after" / "let's go deep in Q&A"）。
4. object-cue の「cue≠key」、倫理（Allowed/Disallowed）の2点は**必ず明瞭に**。信頼の核。

## 時間配分（目安） / Timing map
| 区間 | スライド | 経過 |
|---|---|---|
| 導入 | 1 Title → 3 Agenda | 00:00–01:40 |
| 問題提起 | 4 Problem → 5 Meme | 01:40–03:10 |
| コンセプト | 6 IS/ISN'T → 7 Janus | 03:10–05:10 |
| 脅威・構造 | 8 Adversary → 11 Layers | 05:10–08:50 |
| 機構 | 12 Pillars → 16 Flow | 08:50–13:50 |
| 内部・実機 | 17 Tech → 20 Guards | 13:50–17:05 |
| 倫理・限界 | 21 Ethics → 22 Scope | 17:05–19:05 |
| **デモ** | 23 Divider → 24 Demo | 19:05–26:20 |
| 締め | 25 Quick start → 26 Closing | 26:20–~27:30 |
| **Q&A・卓上デモ・交流** | — | ~27:30–45:00 |

---

# 台本 / Script

## [00:00] Slide 1 — Title（バナー）
**EN:** "Hey, thanks for coming. This is **Phasmid** — the reference build of what I call the **Janus Eidolon System**. Local-only, coercion-aware storage, built for the moment someone has both your device *and* you. I'm Makoto Sugita — Mr. Rabbit."
**JA:** 掴みは短く。バナーを一度指す。時計スタート。

## [00:30] Slide 2 — whoami
**EN:** "Quick background: independent security researcher and open-source tool developer, penetration tester by trade, CISSP. I turn offensive experience into defensive tools — deception, delaying action, coercion-aware design. You may have seen my other work, the Azazel system and the PAKURI family, at Black Hat Arsenal, BSides, SecTor, CODE BLUE. Find me at **01rabbit** on GitHub."
**JA:** 経歴は流す。ハンドルを指す。

## [01:10] Slide 3 — Agenda
**EN:** "Here's the plan for the next half hour. First the problem — compelled access. Then the core idea, **Janus**. How it works — the object cue and coercion-safe delaying. A look under the hood — crypto, guards, the actual hardware. Then the honest limits — ethics and scope. And I'll finish with a **live demo** and how to run it yourself. I'll keep time for questions at the end."
**JA:** 6項目を指でなぞる。期待値を固定。

## [01:40] Slide 4 — The Problem
**EN:** "Here's what Phasmid is built for. Attackers today don't need to break your crypto. They take the **device** — at a border, a checkpoint, an arrest — and they ask you to **unlock it**. And full-disk encryption is all-or-nothing: the moment you open it under pressure, **everything** is exposed. That's over-disclosure."
**JA:** 3枚を左→右で指す。淡々と、しかし重く。

## [02:40] Slide 5 — Meme（pick your fate）
**EN:** "So you get three bad options. **Refuse** — and you escalate. **Comply** with full-disk encryption — and you hand over everything. Or... **controlled disclosure** — show what's visible, protect the rest. Same demand, very different blast radius."
**JA:** 軽く笑いを取る。緊張を一度ほぐす。

## [03:10] Slide 6 — What it is / isn't
**EN:** "Let me be precise. Phasmid is a **field-evaluation research prototype** for disclosure control — not casual file encryption, local-only by default. And it is **not** a replacement for audited full-disk encryption, not hardware-backed keys, not a magic delete button, and not a complete answer to compelled disclosure. I'll keep drawing that line the whole way through."
**JA:** 誠実さを最初に宣言。IS/NOTを左右で。

## [04:00] Slide 7 — Core idea: Janus
**EN:** "The core idea is **Janus** — two faces. A two-slot model. **Slot A** is what a capture-visible surface shows: plausible, ordinary, disclosed under pressure. **Slot B** is protected local state, kept off the visible path, bound to local conditions — not just a password. What you show is not all there is."
**JA:** 概念の核。左右のスロットを指す。ゆっくり。必ず持ち帰らせる。

## [05:10] Slide 8 — Adversary model
**EN:** "Who does it defend against? Five in-scope adversaries — physical captor, passive observer, local active attacker, local-network attacker, and a coercing authority. And, just as important, five explicitly **out** of scope: a compromised kernel, hardware implants, remote attackers, supply-chain, and breaking the crypto itself. If the host is owned, no user-space tool saves you — and I won't pretend otherwise."
**JA:** 左=戦う相手、右=戦わない相手。誠実さの要。

## [06:25] Slide 9 — STRIDE + LINDDUN
**EN:** "I didn't just hand-wave the threats. **Eighteen scenarios**, each tagged with STRIDE and LINDDUN — offline cracking, session replay, header leakage, timing side-channels, object-cue spoofing, coerced disclosure. Here are a few; the full matrix is in the repo. If you want to argue about any of these, find me after — I'd enjoy it."
**JA:** 表は全部読まない。代表2〜3行を指す。遅れていたらここを最短で。

## [07:10] Slide 10 — Architecture boundary
**EN:** "Architecturally, four things stay **explicit**. Two-slot storage. Local access-key mixing — keys come from local state, not a passphrase alone. A restricted-action policy that gates anything sensitive or recovery-related. And capture-visible discipline: normal flows never expose the structure, the recovery path, or the order you'd try things in."
**JA:** 4点を順に。専門聴衆が頷く箇所。

## [08:10] Slide 11 — Layers & document map
**EN:** "Underneath, narrow local layers — entry points, the restricted-action policy, the crypto core, local state, and the deployment boundary. And none of this is folklore: it's documented — a full specification, the threat model, the formal Janus spec, and the delaying-architecture design. Read it, poke holes in it."
**JA:** 流し気味。文書充実＝真剣な研究。

## [08:50] Slide 12 — Three pillars
**EN:** "Three moving parts. One — an **encrypted local vessel**: authenticated encryption, password-derived keys. Two — **object-cue operation**; I'll come right back to this, it's the fun part. Three — **controlled disclosure**: workflows that separate what's shown from what's protected."
**JA:** ②を予告して引っ張る。

## [09:40] Slide 13 — The object is a cue, not a key　★見せ場
**EN:** "Here's the fun part. You show an everyday **object** to the camera to operate the access gate — nothing to type, nothing that looks like a secret. But this is the part people get wrong, so let me be clear: the object is a **cue, not a key**. It drives operation and policy checks. It is **not** the encryption key. A photo of the object unlocks nothing. The crypto stays with Argon2id and AES-GCM — the object just decides whether you get to act."
**JA:** ゆっくり。cue≠key を二度言う。手元の物体を掲げると効果的。

## [11:00] Slide 14 — Coercion-safe delaying
**EN:** "This is what makes it coercion-*safe*. **Silent Standby** — a hotkey drops the sensitive UI into a harmless state; recovery needs re-auth. A **plausible dummy dataset**, prepared *before* any coercion and scored for plausibility. And **context profiles** — travel, field engineer, researcher — that shape what 'normal' looks like. In coercion-safe mode, a low-confidence match routes to the dummy path instead of failing loudly. The goal isn't magic invisibility — it's uncertainty and delay."
**JA:** Silent Standby をデモで見せると予告。認識モードの帯を指す。

## [12:20] Slide 15 — Design principles
**EN:** "The design principle is **restraint**. The vault file alone isn't meant to be enough. Normal flows don't reveal structure or recovery. And metadata reduction is best-effort — I call it support, not sanitization. Restraint is the feature, not a limitation."
**JA:** 流す。誠実トーン維持。

## [13:05] Slide 16 — Flow: Prepare → Bind → Operate → Disclose
**EN:** "Operationally it's four steps: **Prepare** a vessel, **Bind** it to local state and the object cue, **Operate** through CLI, TUI, or local WebUI, and **Disclose** — controlled, under documented assumptions. Keep this in your head — it's the map for the demo in a few minutes."
**JA:** 4ステップを順に指す。デモの地図と予告。

## [13:50] Slide 17 — Tech: small, local, boring
**EN:** "Small, local, boring by design. **Argon2id** for key derivation, **AES-GCM** for authenticated encryption, WebUI bound to **localhost**, on a **Pi Zero 2 W**. Tuned parameters for that little board, per-record encryption, no plaintext header. Boring is good — boring is auditable."
**JA:** 数値は帯を指す程度。詳細は次/Q&A。

## [14:40] Slide 18 — Field hardware（実機）　★エンゲージ
**EN:** "And here's the actual thing. A Pi Zero 2 W in a 3D-printed case, a camera for the object cue, on a little tripod. By default the WebUI binds **localhost only** — on-device access, no network. If you want to reach it from a laptop over the USB link, that's an explicit opt-in, and it binds **that one USB interface** — never all interfaces, never Wi-Fi. It's meant to read as an unremarkable small gadget. It's right here on the table — come look, and try it, after the talk."
**JA:** 現物を指す／持ち上げる。卓上デモ・Q&Aへの導線。

## [15:40] Slide 19 — Cryptographic core (v3)
**EN:** "For the crypto people: Argon2id with mixed-in local access-key material and device binding, an optional external secret as a third factor, AES-GCM per record with authenticated metadata, and no plaintext marker in the vault. Startup self-tests check the primitives first. Details are in the repo — happy to go deep in Q&A."
**JA:** 全部読まない。左列3点を指す。深掘りはQ&Aへ。

## [16:25] Slide 20 — Operational guards
**EN:** "The WebUI is hardened, not an afterthought: localhost binding, per-process tokens, a restricted-confirmation session that's HttpOnly and short-lived, attempt limiting, rate limiting, inactivity auto-kill, hardened headers, and an opt-in HMAC-chained audit log. Defense in depth around a local surface."
**JA:** 俯瞰で。個別値はQ&A。

## [17:05] Slide 21 — Design ethics: will & won't　★倫理
**EN:** "Now the ethics — and this matters, especially in this room. Phasmid **allows** plausible controlled disclosure, standby, ambiguity-preserving workflows. It **explicitly disallows** rootkits, kernel-level hiding, anti-forensic destruction, forensic-tool bypass, and fabricating false events or timestamps. It increases uncertainty and delays confident conclusions — it does **not** claim forensic invisibility. This line is deliberate, and it's in the code."
**JA:** フォレンジック/法執行の聴衆へ誠実に。目を合わせる。信頼獲得点。

## [18:15] Slide 22 — Scope, honestly drawn
**EN:** "Scope, drawn honestly. Software-existence concealment: **out**. Data-existence deniability: **partial**. Controlled disclosure: **in, and central**. Coercion-aware fallback: **in**. And what it never claims — perfect deniability, forensic immunity, secure deletion on flash, protection from a compromised host. No snake oil. Okay — enough talk. Let me show you."
**JA:** 誠実さの締め。最後の一文でデモへ橋渡し。

## [19:05] Slide 23 — LIVE DEMO（章扉）
**EN:** "Alright — live demo."
**JA:** 呼吸を整え実機へ。プロジェクタ入力をTUIへ切替。**バックアップ録画の頭出しを確認。**

## [19:20] Slide 24 — Live demo（実TUI）　★中心 / 約7分
**EN（最小限・手を動かしながら）:** "This is the real TUI — **Local Disclosure Control**. I'll **create a vessel**, set the object cue under **Faces**, run the **Guided** flow, check dummy-profile plausibility in **Audit**, launch the local **WebUI**, then trigger **Silent Standby** and show the dummy disclosure. Watch the bottom bar."
**JA:** 詳細手順は別紙 **Phasmid_Demo_Runbook** を参照。話しすぎない／画面を指す／各ステップで一呼吸。**7分で切り上げ、Q&Aに15分以上を残す。** 失敗時は録画へ切替し設計点を口頭補強。

## [26:20] Slide 25 — Quick start
**EN:** "Want to try it? Clone the repo, cd in, run `./phasmid` — first run sets up a venv and opens the console. Research software, Apache-2.0. Evaluate it locally, in field-test conditions — not as production protection."
**JA:** URLを指す。ステッカーへ繋ぐ。

## [26:50] Slide 26 — Closing → Q&A
**EN:** "That's **Phasmid** — local-only, coercion-aware storage, honest limits included. Code, threat model, and architecture are all on GitHub at **01rabbit**. Grab a sticker — and please, come break it. I've got time for questions."
**JA:** 約27分で着地。残り約18分をQ&A・卓上デモ・交流へ。**45分で必ず終了。**

---

# Q&A 誘導 & 想定問答 / Q&A funnel
壇上で深入りしそうな話題は、以下のフレーズでQ&Aへ送る：
- "Great question — let's go deep on that in Q&A / come find me after."
- "The full matrix / parameters are in the repo; I'll point you to the exact file."

**想定問答（要点のみ）:**
- **「LUKSとの関係は?」** → TUIのLUKS連携に触れつつ、Phasmidは*開示制御の層*でありFDEの代替ではない（Slide 6・22）。
- **「否認可能性は?」** → データ存在の否認は*部分的*、完全否認は*非主張*（Slide 22）。
- **「押収後、本当に守れるのか?」** → ホスト侵害・カーネル奪取は*対象外*（Slide 8）。増やすのは不確実性と時間（Slide 21）。
- **「object-cueは生体認証/鍵?」** → 否。*cueであってkeyではない*（Slide 13）。
- **「法的に問題は?」** → 破壊・偽造・アンチフォレンジックは*設計上禁止*（Slide 21）。合法性は管轄依存であり助言はしない。

# コンティンジェンシー / Contingency
- **押している（+3分以上）:** Slide 9・19・20 を各1行に圧縮。Slide 11 は口頭一言でスキップ可。
- **巻いている（-3分以上）:** Slide 8・14・21 を丁寧に。デモで Audit と WebUI を実演拡張。
- **デモ不調:** 章扉（23）で頭出しした録画へ即切替。「設計点は録画でも成立する」と明言し、口頭で Prepare→Bind→Operate→Disclose を辿る。
- **時計運用:** 19:20 でデモ開始、**26:00 を超えたら残手順を口頭要約**して締めへ。45:00 厳守。
