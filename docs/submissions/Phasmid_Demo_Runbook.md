# Phasmid — Live Demo 実施細部要領 / Demo Runbook

**対象:** DEF CON Demo Labs 本番の実機デモ（Deck Slide 24）。プレゼン30分のうち**約7分半**を割り当て、**Q&A/交流15分を必ず確保**する。
**画面:** TUI（Local Disclosure Control）で Prepare・Refuse・Disclose を、**ローカルWebUI で Bind・Operate（登録・復元）** を行う。プロジェクタ切替は **Step 2→3 と Step 4 の手前の1往復のみ**。

> **情報の確度について**
> - **本書は 0.4.0 実機（Pi Zero 2 W / Raspberry Pi OS Trixie）で全手順を通した結果に基づく。** 〔要確認〕は原則として解消済み。実機で確認していない項目のみ §9 末尾に明示する。
> - **前版からの重要な変更（Issue #169・Phase 1 実装済み）:** TUI の **Add File** と Expert 画面の **Doctor・Inspect を非活性化**した — いずれも役割別トークンで保護された WebUI（`/store`、`/operator/doctor`、`/operator/inspect`）と完全に重複するため。**Recover File と Audit はあえて非活性化していない** — Recover File は cue≠key の否定証明（Step 4）を実証できる唯一の検証済み経路であり、Audit は本デモ Step 5 でキー1つで直接使う。どちらも WebUI 側の同等機能が今回のセッションでは十分に検証・統合されていないため、対応する WebUI 移行が済むまで TUI に残した。**削除ではなく非活性化** — 内部のサービス呼び出し・画面コードはそのまま残しており、リハーサルで問題が出れば1行で復元できる。
> - **デモ構成もこれに合わせて改訂した。** Step 2「Bind」と Step 3「Operate（正しい物体での復元）」を **WebUI の Store/Retrieve 画面**に移した — 登録・復元の統合経路は実機で検証済み。**Step 4「物体を完全に外して失敗させる」は引き続き TUI の Recover File で行う**（この否定証明は今回のセッションでは WebUI 側で再検証していない。本番前に一度試すことを推奨。§9 末尾参照）。
> - **Expert フッタの安全端末幅が 145→124 桁に下がった**（Doctor/Inspect の非活性化でフッタの項目数が減ったため。Audit は残っているので115桁までは下がらない）。
> - **囮ファイルは運用者が用意する**ものとし、生成機能は空き領域の填充に位置づけ直している（v4 からの変更点、引き続き有効）。

---

## 0. 本番でやってはいけないこと（先に読む）

鍛錬中に実際に踏んだものだけを挙げる。

| やってはいけない | 理由 | 代わりに |
|---|---|---|
| **マウスでボタンを押す** | SSH越しのターミナルではクリックイベントがTextualに届かない。ボタンはフォーカスされるだけで発火しない | **`Tab` / `Shift+Tab` で移動し `Enter`**。全操作をキーボードで行う |
| **壇上で Fill Free Space を実行** | 64 MiB / 15% で**実測約4分**。枠は1:20 | **事前に埋めておき**、壇上では **Inspect Free Space** のみ |
| **囮ファイルをツールに作らせる** | 生成される填充物は汎用ファイルであり、開示材料としての真実味がない | **囮は運用者が用意する。** 真のファイルによく似た偽ファイルを自分で保存する |
| **素の `phasmid` で起動** | libcamera のログがTUIを破壊する／WebUIがラップトップから見えない／トークンが毎回変わる／`Ctrl+S` が効かないことがある | **`scripts/pi_zero2w/run_demo_console.sh`** を使う |
| **成功例だけを見せる** | 物体キューが効いていることの証明にならない。観客にはただのパスワード復号に見える | **物体なしの失敗を必ず見せる**（Step 4） |
| **TUI で Add File を探す** | #169 で非活性化済み。Operation セレクタには Recover File・List Files・Remove File しか出ない | **Bind（Face登録）は WebUI** で行う。復元は Step 3 が WebUI、Step 4 は TUI の Recover File のまま |

---

## 1. 制約と時間予算 / Constraints & budget（合計 ~7:30）

| # | フェーズ | 目安 | 画面 | 対応スライド概念 |
|---|---|---|---|---|
| 0 | オリエンテーション | 0:20 | TUI Simple | TUIホーム提示 |
| 1 | Vessel 作成（Create） | 0:50 | TUI Simple | Prepare |
| 2 | Bind — Face 1・Face 2 登録 | 1:30 | **WebUI**（store トークン） | Bind（cue≠key の準備） |
| 3 | Operate — 復元 成功／役割の境界 | 0:50 | **WebUI**（store・recover トークン） | Operate |
| 4 | **復元 失敗（物体なし）** | 0:50 | TUI | **★★cue≠key の証明** |
| 5 | Audit（空き領域と境界） | 0:50 | TUI Expert | 誠実性の可視化 |
| 6 | Silent Standby | 1:20 | TUI | Disclose / 山場 |
| 7 | ラップ | 0:10 | TUI Simple | 締め |

> **時計運用:** 開始 ~19:20。**26:00 を超えたら Step 2〜3 を口頭要約**して締めへ。
> **プロジェクタ切替は1往復だけ。** Step 1 の終わりに TUI→ブラウザへ、Step 3 の終わりにブラウザ→TUI へ。以降 Step 4〜7 は切替なし。
> **Step 4 は cue≠key の唯一の実証。** 物体の有無だけを変えた対比がなければ実証にならない。

---

## 2. 事前準備チェックリスト / Pre-flight

### T-30分（設営時）

- [ ] 実機（Pi Zero 2 W + カメラ + 三脚）を卓上に設置、電源・給電確認。
- [ ] 表示系: TUIを映す経路と、**ラップトップのブラウザを映す経路**の両方を確保。**入力切替キーを把握**（切り替えるのは Step 1→2 でTUIからブラウザへ、Step 3→4 でTUIに戻す1箇所のみ）。
- [ ] **端末幅を124桁以上にする**（`tput cols` で確認）。これを下回ると Expert フッタから
      `w WebUI` が**無言で消える** — 露出したWebUIを引っ込めるキーが画面から失われる。
      省略記号は出ないので、狭いことに気付けない（→ §9）。
- [ ] カメラのピント・画角・照明を確認（物体が安定認識される距離に三脚固定）。
- [ ] **デモ用プロファイルで初期化**（実運用の秘匿データは載せない）。
- [ ] **前回デモの Vessel が残っていれば `delete`（Delete Vessel）で完全に削除**してから
      新規作成する。物体キューの残留は Vessel 新規作成時に自動でクリアされる（0.4.0）。
- [ ] **起動は必ず次のスクリプトで:**
      ```bash
      cd ~/Phasmid && bash scripts/pi_zero2w/run_demo_console.sh
      ```
      `LIBCAMERA_LOG_LEVELS` / `PHASMID_WEBUI_EXPOSE_GADGET` /
      `PHASMID_STORE_TOKEN` / `PHASMID_RECOVER_TOKEN` /
      `PHASMID_RECOGNITION_MODE=demo` と `stty -ixon` を設定する。**素の起動では
      デモが成立しない**（→ §0）。役割トークンが1つでも発行されると
      `PHASMID_WEB_TOKEN` は `/unlock` に受理されなくなる点に注意。
- [ ] **【重要】囮ファイルと真のファイルを自分で用意しておく。** 真のファイルによく似た、
      公開して差し支えない偽ファイルを1つ作る（例: 同種の書式・同程度の分量の下書き）。
      **どちらも Step 2 で WebUI から保存する** — TUI の `Add File` は #169 で
      非活性化済みなので使わない（`Recover File` は Step 4 のために引き続き有効）。
- [ ] 用意するパスフレーズは3つ: 真の復号用・真の破壊用・偽の復号用。
- [ ] （任意）**Fill Free Space を事前実行**（約4分）。空き領域を埋め、
      容器が不自然に空でないようにする。経過時間が表示され画面は固まらない。
- [ ] ラップトップのブラウザで `http://10.12.194.1:8000/unlock` を開き、
      **store トークン**（既定 `phasmid-demo-store-token`）で **Home まで進めた
      タブを1つ**、**recover トークン**（既定 `phasmid-demo-recover-token`）で
      **Home まで進めたタブをもう1つ**、それぞれ用意してブックマーク。
      ※ `phasmid-pi.local` は使わない。**IPアドレス直指定**。
- [ ] **バックアップ録画**（全手順を通した2〜3分クリップ）を再生機に用意し**頭出し**。
- [ ] 予備電源／ケーブル。会場ネットワークは不要（WebUIはUSBガジェット面のみ）。
- [ ] **本番前に確認すること（推奨・時間があれば）:** Step 4「物体を完全に外して
      失敗させる」を WebUI Retrieve でも一度試しておく。成功すれば Step 4 も WebUI
      側に統合でき、TUI への切り戻しが不要になり切替が0往復になる。今回のセッションでは
      時間の都合でこの1点だけ未検証のまま残した。

### T-5分（登壇直前）

- [ ] TUIを **Simple Operator 画面**で待機。
- [ ] **`! SYSTEM: n WARN` は Simple 画面には出ない**（Expert専用）。内容を確認したい場合は
      `e` を押し、**確認後 `Esc` で Simple に戻しておくこと。**
- [ ] WARN の内訳を把握（→ §6）。すべてホスト自身の事実。質問された場合の答えを用意。
- [ ] デモ用パスフレーズ／物体プロップ（2つ、区別できるもの）を手元に。**実秘匿は使わない**。
- [ ] Silent Standby は **`Ctrl+S`**（既定）。復帰は **`Ctrl+R`** または **`Esc`**。
      **フッタに出ないので指で覚えておく。**
- [ ] **WebUI はまだ起動しない。** Step 2 で初めて `w` を押す。

---

## 3. 初期状態 & リセット / Initial state & reset

- **初期状態:** Simple Operator 画面。Vessels は空（`No protected storage found.`）。
- **Step 1 で作る Vessel はそのまま Step 2〜6 で使う。** 物体キューは Vessel 新規作成時に
  自動でクリーンな状態から始まるので、以前のように `rm .state/store.bin .state/lock.bin`
  を手動で行う必要はない。
- **各サイクル後リセット:** §8 を実施。

---

## 4. 実施手順 / Step-by-step

> 表記: **キー** = キー押下。**すべてキーボード操作。マウスは使わない。**
> Select（ドロップダウン）は、フォーカスして `Enter` で開き、`↓` で選び `Enter` で確定。

### Step 0 — オリエンテーション（0:20｜TUI Simple）

- **操作:** Simple Operator 画面を提示。下部バーを指す。
- **発話（EN）:** "This is the real TUI — Local Disclosure Control. The home screen is deliberately small: open, new, guided, expert. Under pressure you do not want a wall of options. The full control set is one key away."
- **画面期待:** `PHASMID` ロゴ、`PROTECTED STORAGE` テーブル、下部バーは
  `o Open / n New / g Guided / e Expert / q Quit / w WebUI` の6項目。
- **注意:** この最小面こそが coercion-aware 設計の一部である旨を一言で。Slide 14 の Silent Standby に伏線として繋がる。
- **注意（旧版の誤り）:** **`! SYSTEM: n WARN` はこの画面には出ない。** 誠実性の話は Step 5 で行う。

### Step 1 — Create a Vessel（0:50｜Prepare｜TUI Simple）

- **操作:** **`n` (New)** → `vessel-path` → **`vessel-size` を `64M` に変更**（Select、
  既定は `512M`。**既定のまま作らないこと** — 下記参照）→
  `vessel-label`（"Non-sensitive label"、任意）→ `create-btn`。
- **発話（EN）:** "First I create a **vessel** — a deniable container file. This is the Prepare step. It has no header and no magic bytes: on disk it is indistinguishable from random data."
- **画面期待:** `PROTECTED STORAGE` に新規Vesselが出現。
  **下段のパネルが `Choose an action:` に変わること**（空状態メッセージが消える）。
- **注意:** Vessel を作ると **Face が2つ自動生成される**（`face_a` / `face_b`、ともに `available`）。
  新しい Vessel は物体キューも自動でクリーンな状態から始まる（0.4.0）。
  **Create Face を押す必要はない。デモ手順に含めない。**
- **任意:** `e` → `i`（Inspect）で `Header absent` / `Magic Bytes absent` /
  `Entropy high / random-like (8.00 bits/byte)` を見せると Slide 19 の直接的裏付けになる。
  （`i` は #169 で Expert フッタからは非活性化済みだが、コマンドパレット経由では
  引き続き到達できる。フッタで見せたい場合は先に §9 の非活性化一覧を確認すること。）
- **【重要】サイズは既定のままにしない。** 作成はコンテナ全体を乱数で埋める。
  512 MiB を指定すると Pi Zero 2 W では**書き込みに時間がかかり、枠の0:50に収まらない**。
  実機では 512 MiB 指定で**プロセスが OOM kill された**（2026-07-29）。原因は
  `os.urandom(container_size)` がコンテナ全体を一度にメモリへ確保していたことで、
  チャンク書き込みに修正済み。修正後もサイズなりの時間はかかるため、**壇上は `64M`**。
- **失敗時:** 作成が滞れば既存デモVesselを **`o` (Open)** して以降を継続。

### Step 2 — Bind: WebUI で Face 1・Face 2 を登録（1:30｜★BIND・切替①｜WebUI）

> **重要（#169・TUI の Add File は非活性化済み）:** TUI の Operation セレクタには
> **Recover File・List Files・Remove File しか出ない。** Face の登録は **WebUI の Store 画面**で行う。
> Store/Retrieve は Step 1 で作った Vessel と同じものを操作する（`resolve_web_vessel()` が
> 解決した Vessel に対し `VesselWorkflowService` を呼ぶ。Vessel 未登録時のみ旧
> `vault.bin` にフォールバック）。

- **操作:** TUI で **`w`** → プロジェクタをラップトップのブラウザへ切替 → 事前ブックマークの
  `/unlock` タブに **`store` トークン**を入力 → **Store** 画面。Step 1「Choose the entry」で
  **Entry 1** を選択 → ファイル選択 → パスワード入力 → **物体Aをカメラの前に配置** →
  `Capture access object` → `Protect file`。続けて Step 1 を **Entry 2** に切り替え →
  別ファイル → 別パスワード → **物体Bに差し替えて** `Capture access object` → `Protect file`。
- **画面期待:** カメラプレビューに `Object cue matched` / `STABLE MATCH` の一致表示。
  Entry を切り替えるたびに `Access object: Not captured` にリセットされる。
  `Protect file` 成功で緑のトースト。
- **発話（EN）:** "Now I switch to the browser — this device also serves a local WebUI, and I'm logged in with a token scoped to the store role. I register two Faces here. For each one, I hold an everyday object in front of the camera. Remember: this is a **cue, not a key**. It gates the operation; it is not the encryption key. A photograph of it unlocks nothing."
- **注意:** **Entry を切り替えたら必ず物体も差し替える**こと — 同じ物体を両方の Face に
  使おうとすると `Object binding failed` で拒否される（cue≠key を壊さないための安全装置。
  実機で確認済み）。
- **失敗時:** 認識が不安定なら距離/照明を微調整。起動スクリプトの既定
  `PHASMID_RECOGNITION_MODE=demo` で確定的に見せられる。

### Step 3 — Operate: 復元 成功、そして役割の境界（0:50｜WebUI）

- **操作:** 同じ `store` トークンのタブで **Retrieve** 画面へ。Face 1 の物体を提示 →
  パスワード入力 → `Open protected file`。続けて、事前に別タブで **`recover` トークン**
  で解錠しておいたウィンドウを一瞬提示 — ナビに `Store` / `Maintenance` へのリンクが
  **一切無い**ことを指す。
- **画面期待:** 緑のトーストで復元成功。`recover` タブのナビは `Home` / `Retrieve` /
  `Lock` だけ。
- **発話（EN）:** "Same object, correct password — the file comes back. And here's a second, narrower session, logged in with a different, role-scoped token. It can decrypt and destroy. It can never reach Face setup at all."
- **注意:** 本編で WebUI の Store/Retrieve を実際に使うのはここまで。**次はプロジェクタを
  TUI に戻して**、最も強い対比（物体を完全に外す）を見せる — これが往復の折り返し。

### Step 4 — 復元 失敗（0:50｜★★cue≠key の証明｜TUI）

> **本書で最も重要なステップ。**
> 成功例だけでは物体キューが効いていることを**何も証明していない**。観客には
> 「パスワードを打ったらファイルが出た」としか見えない。**対比だけが証明になる。**
> この仕組みは **TUI 経由でのみ実機再検証済み**（WebUI Retrieve での「物体なし→拒否」は
> 今回のセッションでは未再検証 — 本番前に一度試すと Step 3 と地続きにでき、切替を
> 0往復にできる。§2 の T-30 チェックリスト参照）。

- **操作:** プロジェクタを TUI に戻す。**`o`（Open）** → `Y` → Operation は
  **`Recover File`**（既定。#169 で `Add File` は選択肢から消えたが、`Recover File`
  はこの Step 4 のために引き続き有効） → **Output file** にパス →
  Face 1 と同じ **Passphrase** → **物体はカメラに見せない**（最初から視野の外、
  または手で覆う）→ `Run Operation`。
- **画面期待:** 約10秒後、赤で **`Open Vessel / no bound object matched`**。
  出力ファイルは作られない。
- **将来的な改善案（未実施）:** WebUI Retrieve でも同じ「物体なし→拒否」を
  一度確認できれば、Step 4 も Step 3 と同じ WebUI タブで完結させ、TUI への
  切り戻しを不要にできる（切替を0往復にできる。§2 の「本番前に確認すること」参照）。
  それまでは TUI の `Recover File` を非活性化しない。
- **発話（EN）:** "Same file. Same password. Same everything — only the object is gone. The device waits ten seconds for a match, does not get one, and refuses. That is what 'the cue gates the operation' means — and notice it tells you almost nothing about *why* it failed. That is deliberate."
- **注意:** **ここで間を取る。** これが cue≠key の唯一の実証である。
  可能なら**この直後に物体を戻して再実行し、成功させる**。
  失敗→成功の往復まで見せると「壊れたのではない」ことまで示せる。
- **注意（ロックアウト）:** TUI 経路は失敗を記録しない（`retrieve_file` は
  `limiter.check()` のみで `record_failure` を呼ばない）ので、**何度失敗させても
  ロックしない。** WebUI 経路は5回失敗で60秒ロックするため、リハーサルは TUI で行うこと。
- **技術的裏付け（質問された場合）:** `collect_auth_sequence()` が
  `wait_for_reference_match(timeout=10.0)` を呼び、不一致なら `match_none` を返す。
  この値は復号の入力そのもの（`_read_face_namespace` に渡る）なので、
  **照合を迂回して復元することはできない。**

### Step 5 — Audit: 空き領域と、ツールが判定しないこと（0:50｜誠実性の可視化｜TUI Expert）

- **操作:** **`e`（Expert）→ `a`（Audit）**。`a` は #169 の非活性化対象から
  意図的に外している — 本 Step でキー1つで直接使うため。**`Free Space Filler`
  セクション**を指す。
- **画面期待:**
  ```
  Free Space Filler
    Tracked Vessels                     1
    Tracked Faces                       2
    Faces with free space filled        1
    Faces partially filled              0
    Faces with little or no filler      1
    Disclosure material                 operator-supplied; filler is not
                                        disclosure material
  ```
- **発話（EN）:** "**Audit** reports per face. Note what it does *not* claim: it does not tell me my cover story is convincing. The file I would hand over is one I wrote and stored myself — the tool cannot judge whether it is believable, and it does not pretend to. All it reports here is how much free space is filled, so an otherwise empty container does not read as empty. Judging the cover story is the operator's job, and the tool is honest about that boundary."
- **注意（旧版の誤り）:** 旧版は「**Operator Log の Dummy Profile 指標を指す**」と
  指示していたが、あの4行は Doctor 由来で Vessel を反映しなかった。**検査自体は
  削除していない**（#157 で解決済み。Doctor 側は環境変数 `PHASMID_DUMMY_PROFILE_DIR` /
  `PHASMID_DUMMY_CONTAINER_PATH` が未設定なら `not configured` を返すだけであり、
  空き領域の実測値は Vessel を反映する Audit 画面が担う）。可信性ではなく空き領域の
  話として、**Audit 画面を指すこと。**
- **任意:** **`d`（Doctor）を開いてよい**（同じくフッタからは非活性化済みだが
  コマンドパレット経由で到達できる）。未設定の助言が警告を出さなくなったので、
  残る警告はこのホスト自身の事実だけになった（→ §6）。「ツールが自分の動作環境を
  正直に報告する」実例として使える。

### Step 6 — Silent Standby（1:20｜★Disclose 山場｜TUI）

- **操作:** **`Ctrl+S`** を押下。復帰は **`Ctrl+R`** または **`Esc`**。
- **注意（キーの所在）:** `Ctrl+S` はフッタに表示されない設計。**指で覚えておくこと。**
  起動スクリプトが `stty -ixon` を実行しているので、ターミナルのフロー制御（XOFF）に
  食われることはない。**素の起動だと押しても無反応になりうる。**
- **画面期待:**
  ```
  SYSTEM STATUS
    Storage integrity check: OK
    Configuration directory: accessible
    Local services: idle
    Background tasks: none
    System clock: synchronized
  Time: ...  |  Host: phasmid-pi
  [ Re-authenticate to continue ]
  ```
  フッタは `^r Re-authenticate` のみ。
- **WebUI も同時に落ちる。** Step 2〜3 で開いた2つのブラウザタブを再読込すると接続が
  切れていることを見せられる（**これを演出に使う**）。復帰後に
  「WebUI was retracted when standby engaged.」の通知が出る。
- **Standby 発動時に未消化のトースト通知も消える。** WebUI 起動時の通知は30秒表示で、
  本文に**アクセスURLとトークンが入っている**。これを消さないと、秘匿画面のはずの
  Standby 画面にトークンが平文で残る。実機で一度再現し、修正済み。
  Standby 画面のフッタから `w WebUI` も消える（封緘中に再露出させないため）。
- **発話（EN）:** "Now the moment it's built for. One hotkey — **Silent Standby**. The sensitive surface drops away. And it is not just this screen: the web interface goes down with it, so a laptop tethered to this device loses access at the same instant — including the two browser tabs I just used. Recovery needs re-authentication. I'm not hiding from forensics — I'm buying **time** and **uncertainty**."
- **注意:** **本デモの山。** ゆっくり、間を取る。倫理（Slide 21）に接続して締める。
- **失敗時:** 遷移が出なければ録画の該当箇所を提示。「これが唯一の"魔法に見える"部分。実体はStateマシンです」と補足。

### Step 7 — ラップ（0:10）

- **発話（EN）:** "That's Prepare, Bind, Operate, Disclose — on real hardware. Come try it at the table."
- **操作:** **`Esc`** で Simple Operator へ戻す。プロジェクタ入力をスライドへ復帰（Slide 25）。

---

## 5. フォールバック方針 / Fallbacks

- **個別ステップ:** 各 Step の「失敗時」に従い、**止まらず前進**（最大15秒で見切り）。
- **全体（実機不調）:** 章扉（Slide 23）で頭出しした**録画に即切替**。
  "The design points stand either way." と明言し、Prepare→Bind→Operate→Disclose を録画上で辿る。
- **認識不安定:** 起動スクリプトの既定が `demo` モード。それでも不安定なら
  `coercion_safe` の低信頼→ダミー経路を**設計意図として逆手に説明**。
- **WebUI がラップトップから見えない、または不安定:** `PHASMID_WEBUI_EXPOSE_GADGET=1` が
  効いているか、URLが **`10.12.194.1:8000`（IP直指定）** かを確認。`127.0.0.1` と
  `phasmid-pi.local` はラップトップからは**到達しない**。**Step 2〜3（Bind・WebUI 部分）を
  口頭要約に切り替え、Step 0・1・4・5・6・7 は実機で続行**（これらは WebUI に依存しない）。
- **時間超過:** 26:00 到達で Step 2〜3 を口頭要約に切り替え、**Step 4 と Step 6 だけは必ず見せる**。

---

## 6. `! SYSTEM: n WARN` の内訳（質疑対策）

Expert画面の警告は**すべてこのホスト自身についての事実**である。実測（新品状態）:

| 件数 | 内容 | 説明 |
|---|---|---|
| 1 | `/tmp` is world-writable | 取り出したファイルが他ユーザーから読める |
| 2 | Swap active / Compressed swap (zram) enabled | Pi Zero 2 W では実用上有効にしている。無効化すれば消える |

**かつて出ていた Dummy Profile 4件の警告は解消した**（#157）。この検査は
`PHASMID_DUMMY_PROFILE_DIR` / `PHASMID_DUMMY_CONTAINER_PATH` で**運用者が
自分の用意した素材を指させる助言機能**だが（`docs/CONFIGURATION.md`）、判定は
**この2つの環境変数が空でない値に設定されているかどうか**で行うよう変更した。
既定パスの存在有無では判定しない — コンテナ側の既定値は `vault.bin` で、これは
CLI の Vessel 既定名と同一であるため、パス存在で判定すると**一度でもファイルを
保管した全端末で警告が復活する**ことになる。未設定時は `not configured` として
報告する。**検査自体は残っている** —
運用者が環境変数で素材を指させば、その**分量**（サイズ・ファイル数・占有率）を報告する。
**説得力があるかどうかは判定しない。** それは運用者の領分である。

- **発話（EN、質問された場合）:** "It warns about its own host — swap is on, so pages can hit disk, and /tmp is world-writable. It is telling me the truth about an environment it does not control. It used to warn about the quality of a decoy as well; we removed that, because the file you would hand over is one you wrote, and the tool has no way to judge whether it is believable."

## 7. 安全・運用注意 / Safety

- **実秘匿データを絶対に投影しない。** デモ用プロファイル／ダミーのみ。
- パスフレーズはカメラ・投影に映さない。物体プロップは公開して問題ないものを使用。
- WebUIはUSBガジェット面のみ。**会場ネットワークに晒さない。** 固定トークンは
  デモ専用値であり、実運用に流用しない。
- **Face ラベルは Vessel ファイルに入らないローカルメタデータ**なので、押収された
  Vessel からラベルは読めない。ただし**デバイス上には残る**。両ラベルとも無害な語に
  すること（`travel` / `backup`）。**片方を "real" や "secret" と名付けると、
  壇上で設計思想を自ら否定することになる。**
- 監査ログ（opt-in）を使う場合、秘匿情報が記録されない設定であることを確認。
- **実地では TUI を強要下で開かない。** 本書 Step 5 で Audit を見せるのは、壇上で
  二面構造を*説明している*からこそ成立する。TUI は意図的に構造が見える研究・検査面で
  あり（`Tracked Faces 2`、Simple 画面の Files 列は全Face合計）、強要者の前で開けば
  隠している側の存在と分量を自分から渡すことになる。実運用では
  `PHASMID_FIELD_MODE=1` を設定し、開示は recover ロールの WebUI 経由に限る
  （Face セレクタも Face 数も出ない）。
- **Vessel レジストリは2分割済み**（#178 で対応）。`vessel_registry.json`（config dir）は
  Vessel の発見インデックスだけを平文で持ち、Face の分量・どちらが填充済みか・物体の
  知覚ハッシュ・破壊用パスフレーズの検証子は `vessel_registry.bin`（state dir）に
  local state key で封入される。**purge 済みの Face と未使用の Face は平文側では
  区別できない。** ただし state key を復元された場合は sidecar も復号されるため、
  デモ機では引き続き本番用の物体・パスフレーズを使わないこと。詳細は
  `docs/THREAT_MODEL.md` の Configuration Directory Surface を参照。

---

## 8. 終了後リセット / Teardown（次サイクル・次回のため）

- [ ] Expert Home で **`delete`（Delete Vessel）** してデモ用 Vessel を完全に削除。
      次サイクルの Vessel 新規作成時に物体キューも自動でクリーンな状態になるため、
      以前必要だった手動の `rm .state/store.bin .state/lock.bin` は不要。
- [ ] **次サイクル用に囮ファイルを保存し直す。** 空き領域の填充（約4分）まで戻す場合は、
      填充済みVesselを複数用意しておき差し替える。
- [ ] Silent Standby を `active` に復帰（`Ctrl+R`）。
- [ ] WebUIプロセス停止（`w`、またはinactivity auto-kill 10分待機）。
- [ ] ブラウザタブ（store・recover 両方）を `/unlock` 済みの状態に戻す。
- [ ] カメラ画角・三脚位置を再固定。

---

## 9. 実機で確認済みの挙動 / Verified on device

以下は 0.4.0 実機で実際に確認した。設計からの推測ではない。

**画面構成**

| 画面 | フッタ |
|---|---|
| `SimpleHomeScreen`（起動時） | `o` Open · `n` New · `g` Guided · `e` Expert · `q` Quit · `w` WebUI |
| `HomeScreen`（`e` の後、#169適用後） | `Esc` Back · `o` · `x` · `delete` · `c` · `f` · `g` · `a` · `s` · `t` · `l` · `?` · `q` · `w` |

`d`（Doctor）と `i`（Inspect）は #169 でフッタから非活性化されたため、上表には
含まれない。`a`（Audit）はあえて残した — Step 5 でキー1つで直接使うため。
`HomeScreen.check_action` が `False` を返すことでフッタから消えるが（LUKS 非活性時と
同じ仕組み）、対応する `action_doctor` / `action_inspect_vessel` メソッド自体は
変更しておらず、コマンドパレット経由では引き続き到達できる。

`Ctrl+S` が Silent Standby、`Ctrl+R` / `Esc` が復帰。`show=False` なのでフッタに出ない。
`w` はアプリ全体のバインド（`tui/app.py`）で、どの画面からも効く。**ただし standby 中は
WebUI を起動できない**（封緘状態の再露出を防ぐため）。
Standby ホットキーの既定は `config.py` の `PHASMID_STANDBY_HOTKEY`（既定 `ctrl+s`）。

**ダイアログ項目**

- `CreateVesselScreen`（`n`）: `vessel-path` → `vessel-size`（Select、既定 `512M`。
  **デモでは `64M` に変更する** → Step 1）→
  `vessel-label`（任意）→ `create-btn`
- `FaceManagerScreen`（`e` → `f`）: `face-id`（Select）→ `new-label` → `add-label-btn` →
  `passphrase` → `restricted-passphrase` → `target-occupancy`（既定 `15%`）→
  `inspect-` / `generate-` / `clear-plausibility-btn`
- `OpenVesselScreen`（`o`）: `vessel-path` → `operation-select`
  （**`Recover File` / `List Files` / `Remove File`、既定 `Recover File`** — #169 で
  `Add File` だけを Select の選択肢から外した。`Recover File` は Step 4 の cue≠key
  証明のために残している。内部の `add` コードパスはそのまま残しており、選択肢に
  戻すだけで復元できる）→
  `passphrase` → `open-btn`。**`face-select` / `input-file` / `restricted-passphrase` は
  `Remove File` の時だけ表示される**（`List Files` では非表示。どちらの面が開いたかは
  パスフレーズと object cue から解決されるので、画面上で面を選ばせない — 選ばせること
  自体が「面が2つある」ことを漏らしてしまうため）。
- `SettingsScreen`（`s`）: `vessel-dir`, `output-dir`, `container-size`, `theme`,
  `recent-tracking`, `compact-banner`, `save-btn`。**認識モードのUIは存在しない**
  （`PHASMID_RECOGNITION_MODE` は環境変数のみ。既定 `strict`、
  `strict|coercion_safe|demo` を受け付ける）

**Vessel の挙動**

Vessel を作ると **Face が2つ自動生成される**（`face_a` / `face_b`、ともに `available`）。
`add-label-btn` は `Face id` Select で選んだ**既存スロットに対して**
`create_face(vessel.path, face_id, label=...)` を呼ぶので、3つ目の Face は作れない。

**生成済みスロットへのラベル付けは安全**（#159 で検証済み）。可信性プロファイルを
生成した face に対して `create_face(label=...)` を実行しても、
`dummy_file_count` / `dummy_total_size` / plausibility level・score はすべて保持される。
回帰テスト `test_labelling_a_face_preserves_its_generated_dummy_profile` で固定した。

**保管層は Vessel 経路に統一済み（ソース確認済み）**

| 経路 | 操作対象 | 根拠 |
|---|---|---|
| TUI `o` Open Vessel（Recover/List/Remove。Addは#169で非活性化） | `*.vessel` | `VesselWorkflowService` |
| TUI Audit（フッタに残存） / Doctor・Inspect（#169でフッタ非活性化、パレットからは到達可） | `*.vessel` | `AuditService` / `DoctorService` / `InspectionService` |
| **WebUI Store / Retrieve** | **同じ `*.vessel`**（`resolve_web_vessel()` が解決） | `web_server.py` が `VesselWorkflowService().add_payload` / `.retrieve_payload` を呼ぶ。Vessel 未登録時のみ `vault.bin` にフォールバック |

`web_server.py` は現在 `VesselWorkflowService` と
`services/web_target_service.resolve_web_vessel()` を import しており、Store/Retrieve は
TUI が使うのと同じ Vessel に対して動作する（Vessel が1つも登録されていない場合のみ
従来どおり `vault.bin` を使う）。`operator_inspect` はアップロードされたファイルを
読むだけで、デバイス上の Vessel には触れない点は変わらない。

**Bind/Operate は実機で WebUI 経由の統合経路を検証済み（0.4.0）**

Face 1・Face 2 の登録から復元まで、WebUI の Store/Retrieve 画面だけで完結する流れを
実機で確認した（本ドキュメントの Step 2〜3 はこの結果を反映している）。ただし
「物体を完全に外して失敗させる」という Step 4 の否定証明は、今回のセッションでは
**TUI 経由でのみ再検証済み**で、WebUI 経由では未検証のまま残っている。

**物体キューが実際に効いていることの根拠**

WebUI の `Capture access object`（Store画面）で参照画像を登録し、Retrieve は
`collect_auth_sequence()` → `wait_for_reference_match(timeout=10.0)` で照合する。
不一致なら `match_none` が返り復元が拒否される。
一致トークンは `_read_face_namespace` の入力そのものなので、**照合を迂回した復元は
成立しない。** TUI 経由の Recover File（#169 では非活性化せず残した）も同じ照合
ロジックを使うが、**この過程を一切表示しない**（→ #158。WebUI は `STABLE MATCH`
バッジとライブ映像でこれを表示できるが、Step 4 の「物体なし→拒否」自体は WebUI 側で
まだ再検証していないため、この否定証明そのものは引き続き TUI で行う）。

**性能実測（Pi Zero 2 W）**

| 操作 | 実測 |
|---|---|
| Fill Free Space（64 MiB / 15% ≒ 9.6 MB） | **約4分** |
| カメラ初期化（libcamera / imx708） | 約0.6秒 |
| 物体照合タイムアウト | 10秒（`collect_auth_sequence`） |
| Textual アイドル時CPU | 約20〜25%（画面フォーカス時 約50%） |

デバイスアイドル時 48.9 °C、`get_throttled=0x0`。卓上デモの排熱・電源計画の参考。

**Doctor の baseline（新品状態）**

`run_doctor_checks()`（非TUI、`services/doctor_service.py`）は27チェックを返す。
Dummy Profile 助言が未設定時に警告しなくなった結果（#157）、警告は**ホスト自身の
事実のみ**になった: `/tmp` world-writable、Swap、Compressed swap の3件（この開発
コンテナでは1件）。zram と swap を無効化すれば1件まで下がる。

**最小端末幅: 124桁**（#160 で確定、#168 の `t Tokens` 追加で123→133、
Delete Vessel追加で133→145、#169 の Doctor/Inspect 非活性化で145→124に更新。
Audit はフッタに残したため、Doctor/Audit/Inspect すべてを非活性化した場合の115桁までは
下がっていない）

フッタのセルは端末幅に応じて詰められず、**固定座標に配置されてはみ出した分は
描画されない**。省略記号も出ないので、**フッタが不完全であることは画面から分からない。**

`w`（WebUI）はアプリレベルのバインディングでフッタの最後に付くため、
**露出したネットワーク面を retract するキーが真っ先に消える。**

| 幅 | Expert フッタ |
|---|---|
| 124桁以上 | 全項目表示 |
| 115〜123桁 | `w WebUI` が画面外 |
| 107〜114桁 | `q Quit` も画面外 |
| 99〜106桁 | `? Help` も画面外 |
| 89〜98桁 | `t Tokens` も画面外 |
| 77〜88桁 | `s Settings` も画面外 |
| 68〜76桁 | `a Audit` も画面外 |

**投影端末は124桁以上を確保すること。** T-30 の設営時に確認する。
`l LUKS` は LUKS 無効時（既定）に非表示になったため、閾値は131桁から123桁へ下がった
（#160）。#168 で `t Tokens` バインディングを追加したことで133桁へ、
Delete Vessel（`delete`キー）バインディング追加で145桁へ上がったが、
#169 で Doctor・Inspect の2バインディングをフッタから非活性化したことで124桁へ
下がった（Audit は意図的に残したため、3つとも非活性化した場合の115桁までは下がらない）。
回帰テスト `test_expert_footer_shows_every_binding_at_the_documented_minimum_width`
が両側から固定しているので、バインディングを追加・削除すると失敗して本表の更新を促す。

**未検証項目**

- Step 4「物体を完全に外して失敗させる」を WebUI Retrieve 経由で行った場合の挙動。
  ロジックは TUI と共通（`wait_for_reference_match` を経由）だが、今回のセッションでは
  WebUI 経由でのこの特定のケースを直接は再確認していない。本番前に一度試すことを推奨。
  #157（Doctor の Dummy Profile 助言が既定パス判定のため未設定端末で永久に警告していた
  問題）は解決済み。残る既知の未解決事項は #158（TUI の照合表示）のみ。
