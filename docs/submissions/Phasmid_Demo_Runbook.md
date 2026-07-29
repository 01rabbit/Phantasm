# Phasmid — Live Demo 実施細部要領 / Demo Runbook

**対象:** DEF CON Demo Labs 本番の実機デモ（Deck Slide 24）。プレゼン30分のうち**約7分**を割り当て、**Q&A/交流15分を必ず確保**する。
**画面:** 実TUI（Local Disclosure Control）が本編。ローカルWebUI は Step 5 のローカル境界の提示にのみ使う（Store/Retrieve は本編と同じ Vessel を操作するが、この統合経路は壇上ではまだ実機で通しておらず、判定が物体キュー照合に依存しCIでは検証できないため本編には含めない）。

> **情報の確度について**
> - **本書は 0.3.0 実機（Pi Zero 2 W / Raspberry Pi OS Trixie）で全手順を通した結果に基づく。** 〔要確認〕は原則として解消済み。実機で確認していない項目のみ §9 末尾に明示する。
> - **前版からの重要な変更:** Step 2 の画面が違っていた（Faces ではなく Open Vessel の `Add File`）。Step 4 の参照先が違っていた（Operator Log ではなく Audit）。Step 3b（物体なしでの失敗）を新設した。Fill Free Space は**実測4分のため壇上から外した**。**囮ファイルは運用者が用意する**ものとし、生成機能は空き領域の填充に位置づけ直した。
> - **WebUI の Store/Retrieve は Vessel 経路に統一済み。** かつては TUI が `*.vessel`、WebUI が別の `vault.bin` を操作しており話が繋がらなかったが、現在は両者とも `resolve_web_vessel()` が解決した同じ Vessel を `VesselWorkflowService` 経由で操作する（Vessel 未登録時のみ旧 `vault.bin` にフォールバック）。Doctor の Dummy Profile 助言は、既定パスの存在有無ではなく `PHASMID_DUMMY_PROFILE_DIR` / `PHASMID_DUMMY_CONTAINER_PATH` が設定されているかどうかで判定するよう変更し、未設定端末での永久警告を解消した（#157）。運用者が自分の素材を指させれば分量を報告する。
> - **注意:** 0.1.4 までは起動直後が Expert 相当の単層画面だった。それ以前の手順書のキー順は**そのままでは通らない**。

---

## 0. 本番でやってはいけないこと（先に読む）

鍛錬中に実際に踏んだものだけを挙げる。

| やってはいけない | 理由 | 代わりに |
|---|---|---|
| **マウスでボタンを押す** | SSH越しのターミナルではクリックイベントがTextualに届かない。ボタンはフォーカスされるだけで発火しない | **`Tab` / `Shift+Tab` で移動し `Enter`**。全操作をキーボードで行う |
| **壇上で Fill Free Space を実行** | 64 MiB / 15% で**実測約4分**。枠は1:20 | **事前に埋めておき**、壇上では **Inspect Free Space** のみ |
| **囮ファイルをツールに作らせる** | 生成される填充物は汎用ファイルであり、開示材料としての真実味がない | **囮は運用者が用意する。** 真のファイルによく似た偽ファイルを自分で保存する |
| **素の `phasmid` で起動** | libcamera のログがTUIを破壊する／WebUIがラップトップから見えない／トークンが毎回変わる／`Ctrl+S` が効かないことがある | **`scripts/pi_zero2w/run_demo_console.sh`** を使う |
| **成功例だけを見せる** | 物体キューが効いていることの証明にならない。観客にはただのパスワード復号に見える | **物体なしの失敗を必ず見せる**（Step 3b） |

---

## 1. 制約と時間予算 / Constraints & budget（合計 ~7:00）

| # | フェーズ | 目安 | 画面 | 対応スライド概念 |
|---|---|---|---|---|
| 0 | オリエンテーション | 0:20 | TUI Simple | TUIホーム提示 |
| 1 | Vessel 作成（Create） | 0:50 | TUI Simple | Prepare |
| 2 | 物体キュー登録（Bind） | 1:10 | TUI | Bind（cue≠key） |
| 3a | 復元 成功（Operate） | 0:40 | TUI | Operate |
| 3b | **復元 失敗（物体なし）** | 0:40 | TUI | **★cue≠key の証明** |
| 4 | Audit（空き領域と境界） | 0:50 | TUI Expert | 誠実性の可視化 |
| 5 | WebUI（ローカル境界） | 0:40 | WebUI | ローカル境界 |
| 6 | Silent Standby | 1:20 | TUI | Disclose / 山場 |
| 7 | ラップ | 0:10 | TUI Simple | 締め |

> **時計運用:** 開始 ~19:20。**26:00 を超えたら残手順を口頭要約**して締めへ。
> **Step 3b は新設。** 物体の有無だけを変えた対比がなければ、cue≠key は実証されない。
> **Step 2〜3b は TUI で行う。** WebUI の Store/Retrieve は本編と同じ Vessel を操作するが、
> 統合経路を壇上ではまだ実機で通しておらず、判定が物体キュー照合に依存しCIでは検証できないため、
> デモ本編には含めない（§4 Step 2 の注記を参照）。

---

## 2. 事前準備チェックリスト / Pre-flight

### T-30分（設営時）

- [ ] 実機（Pi Zero 2 W + カメラ + 三脚）を卓上に設置、電源・給電確認。
- [ ] 表示系: TUIを映す経路と、**ラップトップのブラウザを映す経路**の両方を確保。**入力切替キーを把握**（Step 2〜4 はすべてTUIなので切替は不要。切り替えるのは Step 4→5 でTUIからブラウザへ、Step 5→6 でTUIに戻す1箇所のみ）。
- [ ] **端末幅を123桁以上にする**（`tput cols` で確認）。これを下回ると Expert フッタから
      `w WebUI` が**無言で消える** — 露出したWebUIを引っ込めるキーが画面から失われる。
      省略記号は出ないので、狭いことに気付けない（→ §9）。
- [ ] カメラのピント・画角・照明を確認（物体が安定認識される距離に三脚固定）。
- [ ] **デモ用プロファイルで初期化**（実運用の秘匿データは載せない）。
- [ ] **起動は必ず次のスクリプトで:**
      ```bash
      cd ~/Phasmid && bash scripts/pi_zero2w/run_demo_console.sh
      ```
      `LIBCAMERA_LOG_LEVELS` / `PHASMID_WEBUI_EXPOSE_GADGET` / `PHASMID_WEB_TOKEN` /
      `PHASMID_RECOGNITION_MODE=demo` と `stty -ixon` を設定する。**素の起動では
      デモが成立しない**（→ §0）。
- [ ] **【重要】囮ファイルを自分で用意し、開示する Face に保存しておく。**
      真のファイルによく似た、公開して差し支えない偽ファイルを1つ作る
      （例: 同種の書式・同程度の分量の下書き）。`o` → `Add File` で
      **開示用 Face（face_a）** に、**偽ファイル用パスフレーズ**で保存する。
      **ツールに囮を生成させない。** 生成される填充物は空き領域を埋めるだけで、
      開示材料にはならない。
- [ ] 真のファイルを **face_b** に、**真ファイル用パスフレーズ**と
      **破壊用パスフレーズ**で保存しておく。用意するパスフレーズは3つ:
      真の復号用・真の破壊用・偽の復号用。
- [ ] （任意）**Fill Free Space を事前実行**（約4分）。空き領域を埋め、
      容器が不自然に空でないようにする。経過時間が表示され画面は固まらない。
- [ ] ラップトップのブラウザで `http://10.12.194.1:8000/unlock` を開き、
      トークン（既定 `phasmid-demo-token`）を入力して**Homeまで進めた状態でタブを用意**。
      ※ `phasmid-pi.local` は使わない。**IPアドレス直指定**。
- [ ] **バックアップ録画**（全手順を通した2〜3分クリップ）を再生機に用意し**頭出し**。
- [ ] 予備電源／ケーブル。会場ネットワークは不要（WebUIはUSBガジェット面のみ）。

### T-5分（登壇直前）

- [ ] TUIを **Simple Operator 画面**で待機。
- [ ] **`! SYSTEM: n WARN` は Simple 画面には出ない**（Expert専用）。内容を確認したい場合は
      `e` を押し、**確認後 `Esc` で Simple に戻しておくこと。**
- [ ] WARN の内訳を把握（→ §6）。すべてホスト自身の事実。質問された場合の答えを用意。
- [ ] デモ用パスフレーズ／物体プロップを手元に。**実秘匿は使わない**。
- [ ] Silent Standby は **`Ctrl+S`**（既定）。復帰は **`Ctrl+R`** または **`Esc`**。
      **フッタに出ないので指で覚えておく。**

---

## 3. 初期状態 & リセット / Initial state & reset

- **初期状態:** Simple Operator 画面。Vessels は空（`No protected storage found.`）。
- **囮と真のファイル:** **運用者が用意した2ファイルを保存済みの Vessel を別途用意しておく。**
  Step 1 で作る Vessel は空のままでよく、Step 2〜4 では準備済みの方を使う。
  **囮をツールに生成させないこと。壇上で空き領域の填充も実行しないこと。**
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
- **注意（旧版の誤り）:** **`! SYSTEM: n WARN` はこの画面には出ない。** 誠実性の話は Step 4 で行う。

### Step 1 — Create a Vessel（0:50｜Prepare｜TUI Simple）

- **操作:** **`n` (New)** → `vessel-path` → **`vessel-size` を `64M` に変更**（Select、
  既定は `512M`。**既定のまま作らないこと** — 下記参照）→
  `vessel-label`（"Non-sensitive label"、任意）→ `create-btn`。
- **発話（EN）:** "First I create a **vessel** — a deniable container file. This is the Prepare step. It has no header and no magic bytes: on disk it is indistinguishable from random data."
- **画面期待:** `PROTECTED STORAGE` に新規Vesselが出現。
  **下段のパネルが `Choose an action:` に変わること**（空状態メッセージが消える）。
- **注意:** Vessel を作ると **Face が2つ自動生成される**（`face_a` / `face_b`、ともに `available`）。
  **Create Face を押す必要はない。デモ手順に含めない。**
- **任意:** `e` → `i`（Inspect）で `Header absent` / `Magic Bytes absent` /
  `Entropy high / random-like (8.00 bits/byte)` を見せると Slide 19 の直接的裏付けになる。
- **【重要】サイズは既定のままにしない。** 作成はコンテナ全体を乱数で埋める。
  512 MiB を指定すると Pi Zero 2 W では**書き込みに時間がかかり、枠の0:50に収まらない**。
  実機では 512 MiB 指定で**プロセスが OOM kill された**（2026-07-29）。原因は
  `os.urandom(container_size)` がコンテナ全体を一度にメモリへ確保していたことで、
  チャンク書き込みに修正済み。修正後もサイズなりの時間はかかるため、**壇上は `64M`**。
- **失敗時:** 作成が滞れば既存デモVesselを **`o` (Open)** して以降を継続。

### Step 2 — Object cue: Bind（1:10｜Bind, ★cue≠key｜TUI）

> **重要（保管層は統一済み）:** WebUI の Store/Retrieve は現在、TUI と同じ Vessel 経路を通る。
>
> | 経路 | 操作対象 |
> |---|---|
> | TUI `o` Open Vessel | `*.vessel`（`VesselWorkflowService`） |
> | **WebUI Store / Retrieve** | **同じ `*.vessel`**（`resolve_web_vessel()` が解決した Vessel に対し `VesselWorkflowService` を呼ぶ。Vessel 未登録時のみ旧 `vault.bin` にフォールバック） |
> | TUI Audit / Inspect | `*.vessel` |
>
> **旧版時点では TUI と WebUI が別レイヤ（`*.vessel` / `vault.bin`）を操作していた。**
> 現在は統一済みで、WebUI で保存すれば
> Step 1 で作った Vessel に反映され、Step 4 の Audit にも現れる。
>
> それでも **Step 2〜3b は必ず TUI で行うこと。** 理由は保管層が分離しているからではない。
> 統合経路（WebUIがVesselを操作する現在の動作）を壇上ではまだ実機で通しておらず、
> Store/Retrieve の判定はどちらの経路でも物体キュー照合に依存するため、CIでは検証できない
> ——この2点による。
>
> 旧版が `f` (Faces) と記載していたのは誤り。Faces 画面はラベルと可信性プロファイルの
> 管理画面で、カメラに一切関与しない。物体キューを扱うのは `o` Open Vessel の
> `Add File` である（`capture_reference=True` を渡す唯一の経路）。

- **操作:** **`o`（Open）** → `Y` → Operation を **`Add File`** に変更
  （Select はフォーカスして `Enter` → `↓` → `Enter`）→ **Input file** にファイルパス →
  **Passphrase** と **Restricted recovery passphrase** → **物体をカメラの前に配置** →
  `Tab` で `Run Operation` → `Enter`。
- **画面期待:** `Stored N,NNN bytes in travel.vessel.`
  `VESSEL STATUS` の `Face Files` が増える。
- **発話（EN）:** "Now the object cue. I hold an everyday object in front of the camera while I store this file. Remember: this is a **cue, not a key**. It gates the operation; it is not the encryption key. A photograph of it unlocks nothing."
- **注意:** **TUI はカメラ映像も一致状態も表示しない**（→ #158）。この段階では観客に
  何が起きているか見えない。**だから Step 3b の対比が必須**である。
- **失敗時:** 認識が不安定なら距離/照明を微調整。起動スクリプトの既定
  `PHASMID_RECOGNITION_MODE=demo` で確定的に見せられる。

### Step 3a — 復元 成功（0:40｜Operate｜TUI）

- **操作:** **`o`（Open）** → `Y` → Operation は **`Recover File`**（既定）→
  **Output file** にパス → **Passphrase** → **物体をカメラの前に配置** → `Run Operation`。
- **画面期待:** `Recovered N,NNN bytes to <path>.`（緑）
- **発話（EN）:** "Same object, correct password — the file comes back."

### Step 3b — 復元 失敗（0:40｜★cue≠key の証明｜TUI）

> **本書で最も重要なステップ。旧版には存在しなかった。**
> 成功例だけでは物体キューが効いていることを**何も証明していない**。観客には
> 「パスワードを打ったらファイルが出た」としか見えない。**対比だけが証明になる。**
> **実機で検証済み**（両側を確認）。

- **操作:** **物体をカメラの視野から外す**（退ける、または手で覆う）。
  **他の項目は一切変えず**、もう一度 `Run Operation`。
- **画面期待:** 約10秒後、赤で **`Open Vessel / no bound object matched`**。
  出力ファイルは作られない。
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

### Step 4 — Audit: 空き領域と、ツールが判定しないこと（0:50｜誠実性の可視化｜TUI Expert）

- **操作:** **`e`（Expert）→ `a`（Audit）**。
  **`Free Space Filler` セクション**を指す。
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
- **任意:** **`d`（Doctor）を開いてよい。** 未設定の助言が警告を出さなくなったので、
  残る警告はこのホスト自身の事実だけになった（→ §6）。「ツールが自分の動作環境を
  正直に報告する」実例として使える。

### Step 5 — Local WebUI（0:40｜ローカル境界｜WebUI）

> **役割を限定すること。** WebUI の Store/Retrieve は本編と同じ Vessel を操作するようになったが、
> **この統合経路は壇上ではまだ実機で通していない**ため、
> **ここでファイルを保存したり復元したりしてはいけない。** このステップは**「同じ操作面が
> ローカル境界の内側にも用意されている」ことを見せるだけ**に留める。

- **操作:** TUI で **`w`** を押して起動。プロジェクタをラップトップのブラウザに切替、
  事前に `/unlock` を通しておいたタブを提示。**画面を見せるだけで操作はしない。**
- **画面期待:** ブラウザ上部に赤帯
  `WEBUI ACTIVE — INTERFACE IS EXPOSED — ACCESS FROM TRUSTED NETWORK ONLY`。
  TUI 側にも `WEBUI ACTIVE AT http://10.12.194.1:8000 - PRESS [w] TO RETRACT`。
- **発話（EN）:** "The same device also serves a local web interface — bound to loopback by default. Reaching it from a tethered laptop over USB is an explicit opt-in that binds only the USB interface, and it still needs an access token. It never touches a network. Both ends say plainly that the interface is exposed."
- **注意:** **`w` を押して30秒以内に `Ctrl+S` を押さないこと。** 起動通知には
  アクセストークンが含まれており、表示中に Standby へ入るとトークンが秘匿画面に残る。
  修正済みだが、余裕を持って進めること。
- **失敗時:** 起動が遅ければ口頭説明に留め、TUIへ戻る（時間優先）。

### Step 6 — Silent Standby（1:20｜★Disclose 山場｜TUI）

- **操作:** プロジェクタをTUIに戻す。**`Ctrl+S`** を押下。復帰は **`Ctrl+R`** または **`Esc`**。
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
- **WebUI も同時に落ちる。** ラップトップのブラウザを再読込すると接続が切れていることを
  見せられる（**これを演出に使う**）。復帰後に
  「WebUI was retracted when standby engaged.」の通知が出る。
- **Standby 発動時に未消化のトースト通知も消える。** WebUI 起動時の通知は30秒表示で、
  本文に**アクセスURLとトークンが入っている**。これを消さないと、秘匿画面のはずの
  Standby 画面にトークンが平文で残る。実機で一度再現し、修正済み。
  Standby 画面のフッタから `w WebUI` も消える（封緘中に再露出させないため）。
- **発話（EN）:** "Now the moment it's built for. One hotkey — **Silent Standby**. The sensitive surface drops away. And it is not just this screen: the web interface goes down with it, so a laptop tethered to this device loses access at the same instant. Recovery needs re-authentication. I'm not hiding from forensics — I'm buying **time** and **uncertainty**."
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
- **WebUI がラップトップから見えない:** `PHASMID_WEBUI_EXPOSE_GADGET=1` が効いているか、
  URLが **`10.12.194.1:8000`（IP直指定）** かを確認。`127.0.0.1` と `phasmid-pi.local` は
  ラップトップからは**到達しない**。最悪、**Step 5 を口頭説明のみに留めてスキップする**
  （Step 1〜4・6・7 はWebUIに依存しないため影響を受けない）。
- **時間超過:** 26:00 到達で Step 4 と Step 5 を飛ばし、**Step 3b と Step 6 だけは必ず見せる**。

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

---

## 8. 終了後リセット / Teardown（次サイクル・次回のため）

- [ ] デモVesselを削除/初期化。
- [ ] **次サイクル用に囮ファイルを保存し直す。** 空き領域の填充（約4分）まで戻す場合は、
      填充済みVesselを複数用意しておき差し替える。
- [ ] Silent Standby を `active` に復帰（`Ctrl+R`）。
- [ ] WebUIプロセス停止（`w`、またはinactivity auto-kill 10分待機）。
- [ ] ブラウザタブを `/unlock` 済みの状態に戻す。
- [ ] カメラ画角・三脚位置を再固定。

---

## 9. 実機で確認済みの挙動 / Verified on device

以下は 0.3.0 実機で実際に確認した。設計からの推測ではない。

**画面構成**

| 画面 | フッタ |
|---|---|
| `SimpleHomeScreen`（起動時） | `o` Open · `n` New · `g` Guided · `e` Expert · `q` Quit · `w` WebUI |
| `HomeScreen`（`e` の後） | `Esc` Back · `o` · `x` · `c` · `i` · `f` · `g` · `a` · `d` · `s` · `l` · `?` · `q` · `w` |

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
- `OpenVesselScreen`（`o`）: `vessel-path` → `face-select` → `operation-select`
  （`Add File` / `List Files` / `Recover File` / `Remove File`、既定 `Recover File`）→
  `input-file` → `output-file` → `passphrase` → `restricted-passphrase` → `open-btn`
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
| TUI `o` Open Vessel（Add/Recover/List/Remove） | `*.vessel` | `VesselWorkflowService` |
| TUI Audit / Inspect | `*.vessel` | `AuditService` / `InspectionService` |
| **WebUI Store / Retrieve** | **同じ `*.vessel`**（`resolve_web_vessel()` が解決） | `web_server.py` が `VesselWorkflowService().add_payload` / `.retrieve_payload` を呼ぶ。Vessel 未登録時のみ `vault.bin` にフォールバック |

`web_server.py` は現在 `VesselWorkflowService` と
`services/web_target_service.resolve_web_vessel()` を import しており、Store/Retrieve は
TUI が使うのと同じ Vessel に対して動作する（Vessel が1つも登録されていない場合のみ
従来どおり `vault.bin` を使う）。`operator_inspect` はアップロードされたファイルを
読むだけで、デバイス上の Vessel には触れない点は変わらない。

**旧版時点では両経路が別レイヤ（TUI=`*.vessel` / WebUI=`vault.bin`）を操作していた。**
Doctor の Dummy Profile 助言は、`PHASMID_DUMMY_PROFILE_DIR` /
`PHASMID_DUMMY_CONTAINER_PATH` が空でない値に設定されているかどうかで判定するよう
変更した（#157）。既定パスの存在有無では判定しない — コンテナ側の既定値 `vault.bin`
は CLI の Vessel 既定名と同一のため、パス存在で判定すると一度でもファイルを保管した
全端末で警告が復活してしまう。運用者がどちらかの変数で自分の素材を指させれば、
検査はその分量を報告する。現時点でWebUIを本編から外している理由は保管層の分離ではなく、統合経路を壇上では
まだ実機で通していないことと、Store/Retrieve の判定がどちらの経路でも物体キュー照合に
依存しCIでは検証できないこと、の2点である。

**物体キューが実際に効いていることの根拠**

`Add File`（`capture_reference=True`）で参照画像を登録し、`Recover File` は
`collect_auth_sequence()` → `wait_for_reference_match(timeout=10.0)` で照合する。
不一致なら `match_none` が返り `ValueError("no bound object matched")` になる。
一致トークンは `_read_face_namespace` の入力そのものなので、**照合を迂回した復元は
成立しない。** ただし**TUIはこの過程を一切表示しない**（→ Step 3b の失敗対比が必須である理由）。

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

**最小端末幅: 123桁**（#160 で確定）

フッタのセルは端末幅に応じて詰められず、**固定座標に配置されてはみ出した分は
描画されない**。省略記号も出ないので、**フッタが不完全であることは画面から分からない。**

`w`（WebUI）はアプリレベルのバインディングでフッタの最後に付くため、
**露出したネットワーク面を retract するキーが真っ先に消える。**

| 幅 | Expert フッタ |
|---|---|
| 123桁以上 | 全項目表示 |
| 122桁以下 | `w WebUI` が画面外 |
| 114桁以下 | `q Quit` も画面外 |
| 106桁以下 | `? Help` も画面外 |

**投影端末は123桁以上を確保すること。** T-30 の設営時に確認する。
`l LUKS` は LUKS 無効時（既定）に非表示になったため、閾値は131桁から123桁へ下がった。
回帰テスト `test_expert_footer_shows_every_binding_at_the_documented_minimum_width`
が両側から固定しているので、バインディングを追加すると失敗して本表の更新を促す。

**未検証項目**

- なし（本節の項目はすべて実機または回帰テストで確定済み）。
  #157（Doctor の Dummy Profile 助言が既定パス判定のため未設定端末で永久に警告していた
  問題）は本改訂で解決済み。残る既知の未解決事項は #158（TUI の照合表示）のみ。
