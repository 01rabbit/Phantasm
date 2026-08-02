# Phasmid — DEF CON Demo Labs 台本（30分プレゼン版 / Full Script）

**Deck:** Phasmid_DEFCON_DemoLabs.pptx（全26枚 / 各スライドに同内容のスピーカーノート埋め込み済み）
**Presenter:** Makoto Sugita (Mr.Rabbit / 01rabbit)
**改訂 v6（0.6.0・実機検証済み）:** 物体キューの登録を**2段階撮影**（空シーン→物体）に変更 — 従来は視野全体を鍵にしており、**物体を隠しても開いてしまっていた**（#184/#187）。**Step 4「物体なしでの失敗」を WebUI に移した** — 実機で WebUI 経路の拒否を確認したため。Step 3（成功）と Step 4（失敗）が**同じタブで連続**し、物体の有無だけが変わる。プロジェクタ切替は Step 1→2 と Step 4→5 の**1往復のみ**。**Step 4b（強要下でデータを守る）を任意ステップとして追加** — **同じ画面の同じ入力欄に破壊パスワードを入れると、かざしている Face が消える**（#189/#191）。画面は何も変わらず、応答は打ち間違えと同じ。もう一方の Face は無傷。
> 旧 v5（0.4.0）: Slide 24 のデモ構成を、実機で検証済みの WebUI 中心の Bind/Operate に更新。**Step 2「Bind」と Step 3「Operate（正しい物体での復元）」は WebUI**（役割別トークン: store / recover）で行い、**Step 4「物体なしでの失敗」だけを TUI に残す**（この否定証明はWebUI側で今回のセッションでは未再検証のため）。プロジェクタ切替は Step 1→2 と Step 3→4 の**1往復のみ**に抑制。Issue #169（TUI の Add File・Doctor・Inspect を非活性化、WebUIと重複するため）を反映し、Slide 24 の手順表と Q&A の一部を更新。
**改訂 v4:** 製品モデルの確定を反映。**囮ファイルはツールが作らない — 利用者が用意する。** 生成機能は「空き領域の填充」へ降格し、Slide 14・21・22 の記述を差し替え。**強要下では開示しない**（制限パスフレーズは破壊資格であり取出資格ではない）ことを Slide 21 で明言。**パスフレーズは3つ**（真の復号／真の破壊／偽の復号）を Slide 12 に明示。Slide 24 のデモ手順を実機ランブック（8ステップ）と一致させ、**Step 3b（物体なしでの失敗）** を山場として新設。**ステッカーは未作成のため Slide 25・26 の言及を削除**し、卓上デモへの導線に差し替え。
> 旧 v3: 実装（silent_brick／purge／emergency_daemon）と整合させ、Slide 6・21 の「破壊しない」記述を撤回。核心を「**Phasmid destroys, but never fabricates**（破壊はする／偽造・隠蔽はしない）」へ変更し、owner-triggered destruction の存在と §2232 リスクを開示。
> 旧 v2: 軍歴＝着想源＋inverse framing（Slide 2）、REAL CASE(2026)（Slide 4）、国境事案 Q&A を追加。

## 枠のルール / Format
- **1枠45分・毎時00分開始・45分ハード停止（非交渉）。** 推奨は「コンテンツ30分＋Q&A/交流15分」。
- 本台本は**安全側でコンテンツ約27〜28分**に設計。開始遅延・デモ延伸を吸収し、Q&Aを15分以上確保する。
- **英語**＝壇上で話す言葉。**日本語**＝演出・進行指示（読み上げない）。行頭 `[MM:SS]` は開始からの**経過時刻の目安**。

## 進行原則 / Delivery principles
1. 各スライドは「経過時刻」を目標に。**遅れたら深掘りスライド（STRIDE / Crypto core / Guards）を短縮**して取り戻す。
2. デモは山場。**約7分で切り上げ**、時計を見て延伸しない。
3. 深い技術論争は歓迎しつつ**Q&Aへ誘導**（"find me after" / "let's go deep in Q&A"）。
4. **必ず明瞭に言い切る3点。** ①object-cue の「cue≠key」、②**囮は利用者が用意する（ツールは偽造しない）**、③倫理（Allowed/Disallowed／強要下では開示しない）。信頼の核。

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
| **デモ（TUI+WebUI・8ステップ、切替は1往復）** | 23 Divider → 24 Demo | 19:05–26:20 |
| 締め | 25 Quick start → 26 Closing | 26:20–~27:30 |
| **Q&A・卓上デモ・交流** | — | ~27:30–45:00 |

---

# 台本 / Script

## [00:00] Slide 1 — Title（バナー）
**EN:** "Hey, thanks for coming. This is **Phasmid** — the reference build of what I call the **Janus Eidolon System**. Local-only, coercion-aware storage, built for the moment someone has both your device *and* you. I'm Makoto Sugita — Mr. Rabbit."
**JA:** 掴みは短く。バナーを一度指す。時計スタート。

## [00:30] Slide 2 — whoami（軍歴＝着想源 / inverse framing）
**EN:** "A quick note on where I come from: like a lot of people in this room, I started in uniform — a former Japan Ground Self-Defense Force officer, a Second Lieutenant, in a cyber unit. My work since has mostly been offensive — and offensive work is really about the **person, not just the algorithm**; the weakest link is human. Phasmid points that lesson the other way: **it doesn't protect the key, it protects the person holding it.** Day-to-day I'm a senior engineer at **GMO Cybersecurity by Ierae** in Tokyo — security research and open-source tools, pen tester, CISSP — you may have seen the Azazel system or the PAKURI family at Black Hat Arsenal, BSides, SecTor, CODE BLUE. Find me at **01rabbit** on GitHub."
**JA:** 経歴は着想源として淡々と、武勇伝化しない。"person, not the algorithm" と "protects the person" は必ず言い切る。左カード先頭に軍歴1行あり。ハンドルを指す。約0:55。

## [01:10] Slide 3 — Agenda
**EN:** "Here's the plan for the next half hour. First the problem — compelled access. Then the core idea, **Janus**. How it works — the object cue and coercion-safe delaying. A look under the hood — crypto, guards, the actual hardware. Then the honest limits — ethics and scope. And I'll finish with a **live demo** and how to run it yourself. I'll keep time for questions at the end."
**JA:** 6項目を指でなぞる。期待値を固定。

## [01:40] Slide 4 — The Problem（＋実事例 REAL CASE）
**EN:** "Here's what Phasmid is built for. Attackers today don't need to break your crypto. They take the **device** — at a border, a checkpoint, an arrest — and they ask you to **unlock it**. And full-disk encryption is all-or-nothing: the moment you open it under pressure, **everything** is exposed. That's over-disclosure. And this isn't theoretical anymore: this year a US citizen was federally charged after a duress feature wiped his phone at a border search — the first known case of its kind. **The scenario on this slide now has a court date.**"
**JA:** 3枚を左→右で指す。淡々と、しかし重く。最後に下段の **REAL CASE** 行を一度指す。係争中の個別事案の是非には踏み込まない（事実の提示のみ）。

## [02:40] Slide 5 — Meme（pick your fate）
**EN:** "So you get three bad options. **Refuse** — and you escalate. **Comply** with full-disk encryption — and you hand over everything. Or... **controlled disclosure** — show what's visible, protect the rest. Same demand, very different blast radius."
**JA:** 軽く笑いを取る。緊張を一度ほぐす。

## [03:10] Slide 6 — What it is / isn't
**EN:** "Let me be precise. Phasmid is a **field-evaluation research prototype** for disclosure control — not casual file encryption, local-only by default. And it is **not** a replacement for audited full-disk encryption, not hardware-backed keys, not a risk-free delete — it *can* destroy data, and that is legally hazardous — and not a complete answer to compelled disclosure. I'll keep drawing that line the whole way through."
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

## [08:50] Slide 12 — Three pillars（＋3つのパスフレーズ）
**EN:** "Three moving parts. One — an **encrypted local vessel**: authenticated encryption, password-derived keys. Two — **object-cue operation**; I'll come right back to this, it's the fun part. Three — **controlled disclosure**. And that third one is concrete, not a slogan: you set **three credentials**. One opens the real file. One opens the decoy. And one **destroys** the real file. Three passwords, three very different outcomes — and only you know which is which."
**JA:** ②を予告して引っ張る。**3パスフレーズはここが初出。** 指で3つ数えて見せると残る。破壊資格の意味は Slide 21 まで引っ張る。

## [09:40] Slide 13 — The object is a cue, not a key　★見せ場
**EN:** "Here's the fun part. You show an everyday **object** to the camera to operate the access gate — nothing to type, nothing that looks like a secret. But this is the part people get wrong, so let me be clear: the object is a **cue, not a key**. It drives operation and policy checks. It is **not** the encryption key. A photo of the object unlocks nothing. The crypto stays with Argon2id and AES-GCM — the object just decides whether you get to act. **And you'll watch this fail live in a few minutes** — same file, same password, no object."
**JA:** ゆっくり。cue≠key を二度言う。手元の物体を掲げると効果的。**最後の一文で Step 4 を予告する。** 実証を約束しておくとデモの山が強くなる。

## [11:00] Slide 14 — Coercion-safe delaying　★製品モデルの核心
**EN:** "This is what makes it coercion-*safe*. **Silent Standby** — a hotkey drops the sensitive UI into a harmless state; recovery needs re-auth. Then the material itself, and I want to be exact about this: **the file you would hand over is one *you* wrote and stored yourself**, before any coercion. **Phasmid does not manufacture your cover story.** A generated dataset would not survive five minutes of questioning by someone holding your passport — realism has to come from your own material, not from my random-text generator. What the tool *does* offer is a **filler** that occupies free space, so an otherwise empty container doesn't read as empty. That's a volume problem, and volume is something software can actually solve. And **context profiles** — travel, field engineer, researcher — tell you what 'normal' should look like, so you know what to prepare. In coercion-safe mode, a low-confidence match routes to the disclosure face instead of failing loudly. The goal isn't magic invisibility — it's **uncertainty and delay**."
**JA:** **本トークで最も誤解されやすい点。** 「ツールが囮を作る」と思われた瞬間に設計の真実味が全部落ちる。**「囮は利用者が用意する」と「填充は空き領域対策に過ぎない」を分けて言い切る。** Silent Standby はデモで見せると予告。認識モードの帯を指す。

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
**EN:** "And here's the actual thing. A Pi Zero 2 W in a 3D-printed case, a camera for the object cue, on a little tripod. The WebUI is reached over **USB at localhost** — it never touches a network. It's meant to read as an unremarkable small gadget. It's right here on the table — come look, and try it, after the talk."
**JA:** 現物を指す／持ち上げる。卓上デモ・Q&Aへの導線。

## [15:40] Slide 19 — Cryptographic core (v3)
**EN:** "For the crypto people: Argon2id with mixed-in local access-key material and device binding, an optional external secret as a third factor, AES-GCM per record with authenticated metadata, and no plaintext marker in the vault. Startup self-tests check the primitives first. Details are in the repo — happy to go deep in Q&A."
**JA:** 全部読まない。左列3点を指す。深掘りはQ&Aへ。

## [16:25] Slide 20 — Operational guards
**EN:** "The WebUI is hardened, not an afterthought: localhost binding, per-process tokens, a restricted-confirmation session that's HttpOnly and short-lived, attempt limiting, rate limiting, inactivity auto-kill, hardened headers, and an opt-in HMAC-chained audit log. Defense in depth around a local surface."
**JA:** 俯瞰で。個別値はQ&A。

## [17:05] Slide 21 — Design ethics: will & won't　★倫理
**EN:** "Now the ethics — and this matters, especially in this room. The line I draw is simple: **Phasmid destroys, but it never fabricates.** It will not plant rootkits, hide processes, bypass forensic tools, forge timestamps, fake system events, or tamper with metadata to deceive an examiner — **and it will not write your cover story for you either.** What it **does** give the owner is a duress response — **owner-triggered destruction**: a silent brick overwrites the whole container with random data, and purge drops one face. Now notice what that means for the three credentials I mentioned. **Under coercion, the restricted credential destroys. It does not quietly disclose something false.** There is no fake unlock that hands an examiner a forgery with my name on it — because the moment I fabricate evidence for you, I have built the thing I just said I wouldn't. I'm telling you plainly that destruction exists, because the honest thing is to also say it's **dangerous**. Destroying data at the moment of seizure can itself be a crime — that's the border case on the problem slide, charged under a US destruction-of-evidence statute. Phasmid gives you the capability; it does **not** advise using it against lawful process, and legality is jurisdiction-dependent. The auto-fire path especially: understand your jurisdiction before you ever enable it. I won't comment on that active case or give legal advice."
**JA:** 破壊機能の存在を隠さず認める。「destroyはする／fabricateはしない」を明確に言い切る。**「強要下では開示しない」＝制限パスフレーズは破壊資格であり取出資格ではない**——Slide 12 の3パスフレーズと結線する。§2232（border case）を利用者リスクとして開示。自動発火経路は特に危険——有効化前に管轄確認を促す。可視キャプションを指す。推奨・法律助言はしない。

## [18:15] Slide 22 — Scope, honestly drawn
**EN:** "Scope, drawn honestly. Software-existence concealment: **out**. Data-existence deniability: **partial**. Controlled disclosure: **in, and central**. Coercion-aware fallback: **in**. And what it never claims — perfect deniability, forensic immunity, secure deletion on flash, protection from a compromised host. **And one more it never claims: that your cover story is convincing.** It can tell you how much space is occupied. It cannot tell you whether anyone will believe you, and it doesn't pretend to. No snake oil. Okay — enough talk. Let me show you."
**JA:** 誠実さの締め。**非主張リストの5つ目「説得力は判定しない」は口頭で足す**（スライドは下段キャプション）。最後の一文でデモへ橋渡し。

## [19:05] Slide 23 — LIVE DEMO（章扉）
**EN:** "Alright — live demo."
**JA:** 呼吸を整え実機へ。プロジェクタ入力をTUIへ切替。**バックアップ録画の頭出しを確認。**

## [19:20] Slide 24 — Live demo（TUI + WebUI）　★中心 / 約7分半
**EN（最小限・手を動かしながら）:** "This is the real system — the **TUI** handles prepare, refuse, and disclose; the local **WebUI**, reached over USB, handles bind and operate. I'll **create a vessel** here. Then I switch to the browser, log in with a store-scoped token, and **register two Faces**. Each one takes two shots: first the empty view, then the object — the difference between them is what the device keeps, so it describes the object and not my wall. I'll open one back with the correct object — it comes back — and show you a second, narrower session that can never reach Face setup at all. Then, **without switching anything**, the important part: **same tab, same file, same password — I only take the object away.** It refuses. That is what 'the cue gates the operation' means. Then I come back here for **Audit** — notice what it *doesn't* claim — and **Silent Standby**. Watch the bottom bar."

**JA デモ手順:** 詳細は別紙 **`docs/submissions/Phasmid_Demo_Runbook.md`（8ステップ、合計 ~7:30）** に従う。要点のみ：

| # | 手順 | 目安 | 画面 | 要点 |
|---|---|---|---|---|
| 0 | オリエンテーション | 0:20 | TUI | Simple 画面の6キーを指す。最小面も coercion-aware 設計の一部 |
| 1 | `n` Create Vessel | 0:50 | TUI | ヘッダなし・マジックバイトなし |
| 2 | Bind — Face 1・Face 2 登録 | 1:30 | **WebUI**（store） | **プロジェクタ切替①。** **空シーン→物体の2枚撮り。** 物体は Face ごとに差し替え、**撮影から保存まで下ろさない** |
| 3 | Operate — 復元成功／役割の境界 | 0:50 | **WebUI**（store・recover） | recover トークンには Store/Maintenance への導線が無いことを見せる |
| 4 | **復元 失敗（物体なし）** | 0:50 | **WebUI**（Step 3 と同じタブ） | **★本デモ唯一の証明。画面を切り替えないこと自体が論証。** 間を取り、**必ず物体を戻して成功まで往復させる** |
| 4b | （任意）**強要下でデータを守る** | 0:40 | **WebUI**（同じ画面・同じ入力欄） | **画面は何も変わらない。パスワードだけが違う。** 不可逆。枠が押していれば省略 |
| 5 | `e` → `a` Audit | 0:50 | TUI Expert | **プロジェクタ切替②。** `Free Space Filler` を指す。**判定しないことを誇る** |
| 6 | `Ctrl+S` Silent Standby | 1:20 | TUI | **山場。** WebUI も同時に落ちる。ゆっくり |
| 7 | `Esc` で復帰・ラップ | 0:10 | TUI | Prepare→Bind→Operate→Disclose を一言で |

**JA 注意:**
- **マウスは使わない。** SSH越しではクリックが Textual に届かない。`Tab` / `Enter` のみ。
- **端末幅124桁以上。** 下回ると Expert フッタから `w WebUI` が無言で消える。
- **プロジェクタ切替は1往復だけ。** Step 1→2 でTUIからブラウザへ、Step 3→4 でブラウザからTUIへ。以降は切替なし。
- **`Fill Free Space` は壇上で実行しない**（実測約4分）。事前に埋めておき `Inspect` のみ。
- **囮ファイルは事前に自分で用意しておく。** 壇上でツールに生成させない。保存自体は Step 2 の WebUI で行う（#169 で TUI の `Add File` は非活性化済み）。
- **成功例だけを見せない。** Step 4 の対比が無ければ cue≠key は何も証明していない。
- **Step 4b は不可逆で、成功しても画面には何も出ない。** 「打ち間違えたときと同じ表示」が正解。やるなら Step 5 の Audit の数字が「消した後」になることを承知の上で。省略しても本筋は通る。
- **7分半で切り上げ、Q&Aに15分以上を残す。** 26:00 を超えたら Step 2〜3 を口頭要約。失敗時は録画へ切替し設計点を口頭補強。

## [26:20] Slide 25 — Quick start
**EN:** "Want to try it? Clone the repo, cd in, run `./phasmid` — first run sets up a venv and opens the console. Research software, Apache-2.0. Evaluate it locally, in field-test conditions — not as production protection."
**JA:** URLを指す。**ステッカーは作成していないので言及しない。** 卓上デモ（実機を触ってもらう）へ繋ぐ。

## [26:50] Slide 26 — Closing → Q&A
**EN:** "That's **Phasmid** — local-only, coercion-aware storage, honest limits included. Code, threat model, and architecture are all on GitHub at **01rabbit**. The device is right here on the table — come try it, and please, come break it. I've got time for questions."
**JA:** 約27分で着地。残り約18分をQ&A・卓上デモ・交流へ。**ステッカーは未作成のため実機体験への導線に差し替え済み。45分で必ず終了。**

---

# Q&A 誘導 & 想定問答 / Q&A funnel
壇上で深入りしそうな話題は、以下のフレーズでQ&Aへ送る：
- "Great question — let's go deep on that in Q&A / come find me after."
- "The full matrix / parameters are in the repo; I'll point you to the exact file."

**想定問答（要点のみ）:**
- **「LUKSとの関係は?」** → TUIのLUKS連携に触れつつ、Phasmidは*開示制御の層*でありFDEの代替ではない（Slide 6・22）。
- **「否認可能性は?」** → データ存在の否認は*部分的*、完全否認は*非主張*（Slide 22）。
- **「押収後、本当に守れるのか?」** → ホスト侵害・カーネル奪取は*対象外*（Slide 8）。増やすのは不確実性と時間（Slide 21）。
- **「object-cueは生体認証/鍵?」** → 否。*cueであってkeyではない*（Slide 13）。壇上で失敗を実演済み（Step 4）。
- **「囮ファイルはツールが作るのか?」** → **否。利用者が用意する。** *"The tool has no idea what a believable version of your life looks like. You do. What it generates is filler for free space — that's a volume problem, and it says so. It never claims the filler is what you hand over."*（Slide 14・22）
- **「plausibility score は何を測っているのか?」** → **空き領域の占有率であって、説得力ではない。** Audit も Doctor も**分量しか報告しない**。旧版はこれを可信性として表示していたが、判定できないものを判定しているように見えるため撤去した。
- **「強要されてパスワードを言わされたら?」** → 渡すのは**偽ファイル用のパスフレーズ**で、自分で用意した囮が開く。**制限（duress）パスフレーズは破壊資格であり、開示はしない。** 偽の中身を自動生成して差し出す経路は**意図的に持っていない**——それは偽造だから（Slide 21）。
- **「WebUIとTUIで見えるものが違うのでは?」** → **保管層は統一済み。** 以前は TUI が `*.vessel`、WebUI が別の `vault.bin` を操作していたが、現在は両者とも同じ Vessel を操作する。**デモ本編でも Step 2・3 は実際に WebUI で Face 登録と復元を行っており**、実機で検証済み。唯一まだ WebUI 側で再検証していないのは Step 4 の「物体なし→拒否」という否定証明1点だけで、それだけは引き続き TUI の `Recover File` で行っている。"The only piece I haven't re-confirmed through the browser yet is the negative case — object completely absent. Everything else you saw tonight, store and retrieve both, ran through the same WebUI."
- **「法的に問題は?」** → 偽造・改ざん・隠蔽（fabricate/forge/hide）は*行わない*。一方 **owner-triggered の破壊（silent-brick／purge）は実装されており、法的に危険**（§2232型）。合法性は管轄依存であり助言はしない（Slide 21）。
- **「あの国境の duress-wipe 訴追事案をどう見る?」** → *"That case turns on a destructive act. Phasmid actually **includes** owner-triggered destruction — silent-brick and purge — so this risk applies directly to anyone who uses it. I'm not going to pretend otherwise, and I'm not going to advise using it against lawful process. Legality is jurisdiction-dependent, this is a research prototype, and I won't comment on an active prosecution or give legal advice. The design principle is that Phasmid destroys but never fabricates."* 個別事案の是非・政治的背景には立ち入らない。破壊機能の存在は隠さず、利用者リスクとして開示する。

# コンティンジェンシー / Contingency
- **押している（+3分以上）:** Slide 9・19・20 を各1行に圧縮。Slide 11 は口頭一言でスキップ可。
- **巻いている（-3分以上）:** Slide 8・14・21 を丁寧に。デモで Audit と Doctor を実演拡張。
- **デモ不調:** 章扉（23）で頭出しした録画へ即切替。「設計点は録画でも成立する」と明言し、口頭で Prepare→Bind→Operate→Disclose を辿る。
- **物体認識が不安定:** 起動スクリプトの既定は `demo` モード。それでも不安定なら `coercion_safe` の低信頼→開示面ルートを**設計意図として逆手に説明**する。
- **時計運用:** 19:20 でデモ開始、**26:00 を超えたら Step 2〜3 を口頭要約**して締めへ。**Step 4 と Step 6 だけは何があっても見せる。** 45:00 厳守。
