# Phasmid — Live Demo 実施細部要領 / Demo Runbook

**対象:** DEF CON Demo Labs 本番の実機デモ（Deck Slide 24）。プレゼン30分のうち**約7分半**を割り当て、**Q&A/交流15分を必ず確保**する。
**画面:** TUI（Local Disclosure Control）で Prepare・Refuse・Disclose を、**ローカルWebUI で Bind・Operate（登録・復元・否定証明）** を行う。プロジェクタ切替は **Step 1→2 と Step 4→5 の1往復のみ**。

> **情報の確度について**
> - **本書は 0.6.0 実機（Pi Zero 2 W / Raspberry Pi OS Trixie）で全手順を通した結果に基づく。** 〔要確認〕は原則として解消済み。実機で確認していない項目のみ §9 末尾に明示する。
> - **物体の登録が2段階撮影になった（0.6.0・#184/#187）。** `1 · Capture empty scene`（物体をフレーム外にして空の視野を撮る）→ `2 · Capture access object`（物体をかざして撮る）の順。**この2枚の差分が物体の領域を決め、その領域だけが特徴として登録される。** 従来は視野全体を登録していたため、三脚固定の背景そのものが鍵になり、**物体を隠しても開いてしまっていた**。加えて **保存の瞬間にも物体の一致が再確認される** — 撮影後に物体を下ろして `Protect file` を押すと拒否される（→ §0・Step 2）。
> - **Step 4（物体なし→拒否）を WebUI Retrieve に移した。** 0.6.0 実機で WebUI 経路でも拒否されることを確認済み。**これで Step 3（成功）と Step 4（失敗）が同じ画面で連続する** — 物体の有無だけを変えた対比を画面切替なしで見せられるため、cue≠key の実証としては従来より強い。TUI の `Recover File` は**フォールバックとして残す**（→ §5）。
> - **破壊はパスワードで制御する（#191）。** Step 3・4 と**同じ Retrieve 画面の同じ入力欄**に、アクセスパスワードではなく**破壊パスワード**を入れると、**かざしている物体の Face が消える**。画面は何も変わらず、応答は打ち間違えたときと**完全に同じ** `No valid entry found.`。もう一方の Face は無傷。**「パスワードを強要されても守る」を、追加の操作なしで実演できる。** 確認も成功表示も無いのは設計上の代償で、成否は「その Face がもう開かないこと」でしか分からない（→ Step 4b）。
> - **明示的な破壊経路も残してある（#189）。** 従来この操作は `phasmid emergency destroy-face` だけにあり、**このツールが存在する理由そのものである「強要されてもデータは守る」シナリオだけがブラウザから落ちてターミナルに残っていた**。Retrieve 画面の「Clear this entry instead of opening it」から、**かざした物体のエントリ**を、その**破壊パスワード**と確認語 `DESTROY FACE` で消せる。消す対象を画面で選ばせないのは意図的 — 選択肢を出すこと自体が「2つある」ことを漏らすため。落ち着いた状況で意図的に片付けるための監査可能な手段で、**壇上では使わない**（画面が変わると対比が弱まる）。実機検証で不具合が出て修正済み（#190・#192）— 詳細は §9.0.2。
> - **Issue #169・Phase 1:** TUI の **Add File** と Expert 画面の **Doctor・Inspect を非活性化**した — いずれも役割別トークンで保護された WebUI（`/store`、`/operator/doctor`、`/operator/inspect`）と完全に重複するため。**Recover File と Audit はあえて非活性化していない** — Audit は本デモ Step 5 でキー1つで直接使う。Recover File は Step 4 の WebUI 移行で本編からは外れたが、**壇上で WebUI が使えなくなった場合に否定証明を成立させる唯一の代替経路**なので残す。**削除ではなく非活性化** — 内部のサービス呼び出し・画面コードはそのまま残しており、リハーサルで問題が出れば1行で復元できる。
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
| **TUI で Add File を探す** | #169 で非活性化済み。Operation セレクタには Recover File・List Files・Remove File しか出ない | **Bind も復元も否定証明も WebUI**（Step 2〜4）。TUI の `Recover File` は WebUI が使えない時の代替 |
| **物体を撮ってから下ろして `Protect file`** | 0.6.0 から**保存の瞬間にも一致を再確認する**（#186）。下ろすと `That entry is already set up...` で拒否される | **撮影から保存まで物体をかざし続ける。** 押す前にオーバーレイが `MATCH` になっていることを確認 |
| **物体をかざしたまま `Capture empty scene`** | 空の視野に物体が写り込むと、差分が物体を切り出せない | **1枚目は必ず物体をフレーム外に。** 順序は空シーン→物体（#184） |

---

## 1. 制約と時間予算 / Constraints & budget（合計 ~7:30）

| # | フェーズ | 目安 | 画面 | 対応スライド概念 |
|---|---|---|---|---|
| 0 | オリエンテーション | 0:20 | TUI Simple | TUIホーム提示 |
| 1 | Vessel 作成（Create） | 0:50 | TUI Simple | Prepare |
| 2 | Bind — Face 1・Face 2 登録 | 1:30 | **WebUI**（store トークン） | Bind（cue≠key の準備） |
| 3 | Operate — 復元 成功／役割の境界 | 0:50 | **WebUI**（store・recover トークン） | Operate |
| 4 | **復元 失敗（物体なし）** | 0:50 | **WebUI**（Step 3 と同じタブ） | **★★cue≠key の証明** |
| 4b | （任意）強要下でデータを守る | 0:40 | **WebUI**（同じ画面・同じ入力欄） | **パスワードだけが違う。** 破壊資格の分離。**不可逆** |
| 5 | Audit（空き領域と境界） | 0:50 | TUI Expert | 誠実性の可視化 |
| 6 | Silent Standby | 1:20 | TUI | Disclose / 山場 |
| 7 | ラップ | 0:10 | TUI Simple | 締め |

> **時計運用:** 開始 ~19:20。**26:00 を超えたら Step 2〜3 を口頭要約**して締めへ。
> **プロジェクタ切替は1往復だけ。** Step 1 の終わりに TUI→ブラウザへ、Step 4 の終わりにブラウザ→TUI へ。Step 2〜4 は同じブラウザ画面で連続する。
> **Step 4 は cue≠key の唯一の実証。** 物体の有無だけを変えた対比がなければ実証にならない。**Step 3 と同じ画面・同じファイル・同じパスワードで、物体だけを外す** — 画面が切り替わらないことが「他は何も変えていない」ことの担保になる。

---

## 2. 事前準備チェックリスト / Pre-flight

### T-30分（設営時）

- [ ] 実機（Pi Zero 2 W + カメラ + 三脚）を卓上に設置、電源・給電確認。
- [ ] 表示系: TUIを映す経路と、**ラップトップのブラウザを映す経路**の両方を確保。**入力切替キーを把握**（切り替えるのは Step 1→2 でTUIからブラウザへ、Step 4→5 でTUIに戻す1箇所のみ）。
- [ ] **端末幅を124桁以上にする**（`tput cols` で確認）。これを下回ると Expert フッタから
      `w WebUI` が**無言で消える** — 露出したWebUIを引っ込めるキーが画面から失われる。
      省略記号は出ないので、狭いことに気付けない（→ §9）。
- [ ] カメラのピント・画角・照明を確認（物体が安定認識される距離に三脚固定）。
      **2段階撮影は三脚が動かないことが前提** — 1枚目と2枚目の差分で物体を切り出すため、
      間にカメラが動くと `Too much of the view changed.` で拒否される。
      **卓上の背景は無地に近い方が確実**（0.6.0 実機では無地の壁で1回目に成功）。
- [ ] **デモ用プロファイルで初期化**（実運用の秘匿データは載せない）。
- [ ] **前回デモの Vessel が残っていれば `delete`（Delete Vessel）で完全に削除**してから
      新規作成する。物体キューは **Vessel 新規作成時**に加え、**最後の Vessel を削除した
      時点**でも自動でクリアされる（0.6.0・#187）。0.4.x では削除では消えず、次の登録が
      「このエントリには既に物体が紐づいている」で止まった。
- [ ] **起動は必ず次のスクリプトで:**
      ```bash
      cd ~/Phasmid && bash scripts/pi_zero2w/run_demo_console.sh
      ```
      `LIBCAMERA_LOG_LEVELS` / `PHASMID_WEBUI_EXPOSE_GADGET` /
      `PHASMID_STORE_TOKEN` / `PHASMID_RECOVER_TOKEN` /
      `PHASMID_RECOGNITION_MODE=demo` と `stty -ixon` を設定する。**素の起動では
      デモが成立しない**（→ §0）。役割トークンが1つでも発行されると
      `PHASMID_WEB_TOKEN` は `/unlock` に受理されなくなる点に注意。
      **`PHASMID_DURESS_MODE=0` / `PHASMID_PURGE_CONFIRMATION=1` も強制的に設定される**
      — どちらも「読んだだけ」の復元で開いていない側の Face を破壊するため、
      両面を順に開く本デモでは継承された値が致命的になる。継承値を上書きした場合は
      起動時に警告が出る。TUI の Doctor でも `Automatic Destruction` として確認できる。
- [ ] **【重要】囮ファイルと真のファイルを自分で用意しておく。** 真のファイルによく似た、
      公開して差し支えない偽ファイルを1つ作る（例: 同種の書式・同程度の分量の下書き）。
      **どちらも Step 2 で WebUI から保存する** — TUI の `Add File` は #169 で
      非活性化済みなので使わない（`Recover File` は §5 のフォールバック用に残してある）。
- [ ] 用意するパスフレーズは3つ: 真の復号用・真の破壊用・偽の復号用。
      **真の破壊用は Store 画面の「Advanced security options」→「Restricted recovery
      password」で設定する。** ここを空にしたまま進めると Step 4b が実演できない。
- [ ] （任意）**Fill Free Space を事前実行**（約4分）。空き領域を埋め、
      容器が不自然に空でないようにする。経過時間が表示され画面は固まらない。
- [ ] ラップトップのブラウザで `http://10.12.194.1:8000/unlock` を開き、
      **store トークン**（既定 `phasmid-demo-store-token`）で **Home まで進めた
      タブを1つ**、**recover トークン**（既定 `phasmid-demo-recover-token`）で
      **Home まで進めたタブをもう1つ**、それぞれ用意してブックマーク。
      ※ `phasmid-pi.local` は使わない。**IPアドレス直指定**。
- [ ] **バックアップ録画**（全手順を通した2〜3分クリップ）を再生機に用意し**頭出し**。
- [ ] 予備電源／ケーブル。会場ネットワークは不要（WebUIはUSBガジェット面のみ）。
- [ ] **物体キューのリハーサルを1回通す**（所要 約2分）。本番と同じ三脚位置・照明で:
      1. `1 · Capture empty scene` → `2 · Capture access object` が**1回で通ること**
      2. 物体を下ろして `Protect file` → **拒否されること**（`That entry is already set up...`）
      3. 物体をかざし直して `Protect file` → 保存できること
      4. Retrieve で**物体を隠して**正しいパスワード → **拒否されること**
      5. 物体を戻して同じパスワード → 復元できること
      6. （Step 4b をやるなら）**別の使い捨て Vessel で**破壊まで通す — 本番用の
         Vessel でリハーサルすると本番のデータが消える。**成功しても画面には何も出ない**
         ので、「そのあと同じ物体とアクセスパスワードで開かないこと」で確認する

      **4 と 5 は必ず対で確認する。** 4 だけでは「何をやっても拒否する状態」と区別がつかない。
      詳細な検証手順と観測すべき値は §9 冒頭を参照。
- [ ] **物体の余裕を測る。** 上のリハーサルは「一致するか」しか答えない。**一致の仕方が
      ぎりぎりなのか余裕なのかは画面に出ない**ので、閾値まであとどれだけあるかを実測する。
      コンソールを終了してから（カメラは排他）:

      ```
      .venv/bin/python scripts/pi_zero2w/measure_cue_margin.py --frames 30
      ```

      **最悪ケースの余裕が約 x1.5 を切っていたら、本番の照明で落ちる。** その場合は
      閾値ではなく**物体を先に替える** — キーポイントが増えると閾値も上がるが、
      スコアはそれ以上に上がる。キーポイントが 48 未満のときは下限が効いているので、
      `PHASMID_CUE_GOOD_MATCH_RATIO` を下げても**バーは動かない**（スクリプトがそう言う）。
      比率を下げた場合は、**物体を外した状態と別の物体でも測り直す** — 一致する側だけ
      確認しても何も確認したことにならない。

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
  **Entry 1** を選択 → ファイル選択 → パスワード入力 → **物体を手元に置いたまま
  `1 · Capture empty scene`** → **物体Aをかざして `2 · Capture access object`** →
  **物体Aをかざしたまま `Protect file`**。続けて Step 1 を **Entry 2** に切り替え →
  別ファイル → 別パスワード → **物体を外して `1 · Capture empty scene`** →
  **物体Bをかざして `2 · Capture access object`** → **かざしたまま `Protect file`**。
- **画面期待:** 1枚目で `Empty scene captured. Now hold the object in front of it.`、
  2枚目で `Object cue matched`。`Access object: Captured` に変わり、
  カメラプレビューのオーバーレイが `No object cue match` から一致表示に変わる。
  Entry を切り替えるたびに `Access object: Not captured` にリセットされ、
  **空シーンの撮り直しからやり直しになる**（前の空シーンは使い回されない）。
  `Protect file` 成功で緑のトースト。
- **発話（EN）:** "Now I switch to the browser — this device also serves a local WebUI, and I'm logged in with a token scoped to the store role. I register two Faces here. Notice it takes two shots: first the empty view, then the object. The difference between them is what the device keeps — otherwise it would be describing my wall, and my wall would open the file. Remember: this is a **cue, not a key**. It gates the operation; it is not the encryption key. A photograph of it unlocks nothing."
- **注意:** **Entry を切り替えたら必ず物体も差し替える**こと — 同じ物体を両方の Face に
  使おうとすると `Object binding failed` で拒否される（cue≠key を壊さないための安全装置。
  実機で確認済み）。
- **注意:** **撮影から保存まで物体を下ろさない。** 0.6.0 から保存の瞬間にも一致を
  再確認するため、下ろすと `That entry is already set up. Hold its access object in
  front of the camera until it matches, then save again.` で拒否される（#186）。
  **これは正常な挙動** — 慌てず物体をかざし直して押し直せばよい。
  ここで「Advanced: replace an existing protected space」パネルは**開かない**（開いたら 0.4.x）。
- **失敗時（メッセージ別）:**
  - `Object does not stand out from the scene behind it.` → 物体をカメラに近づけ、
    フレームに大きく写す。または背景を無地にする。
  - `Too much of the view changed.` → **三脚が動いた／照明が変わった。** カメラを
    固定し直して空シーンから撮り直す。
  - `Rejected: the cue still matches the empty scene` → **安全装置が働いた証拠。**
    その物体では背景と区別できていない。別の物体に替える。
  認識が不安定なら距離/照明を微調整。起動スクリプトの既定
  `PHASMID_RECOGNITION_MODE=demo` を既定にしてある。

- **【重要・誤解を招いていた点】`demo` モードは、落ちた照合を拾い上げるものではない。**
  `_recognition_confidence()` は **ORB 照合がすでに成功しているときだけ** 1.0 を返し、
  それ以外は 0.0 を返す。したがって `demo` のフォールバック分岐
  （`confidence >= PHASMID_DUMMY_FALLBACK_THRESHOLD`）は、**一致しなかった場合には
  到達しない。** 一致しなければ何も開かない — 救済経路は存在しない。
  認識が不安定なら、モードではなく**物体・距離・照明・登録のやり直し**で解く。
  数値で切り分けるには → §9.0.4。

### Step 3 — Operate: 復元 成功、そして役割の境界（0:50｜WebUI）

- **操作:** 同じ `store` トークンのタブで **Retrieve** 画面へ。Face 1 の物体を提示 →
  パスワード入力 → `Open protected file`。続けて、事前に別タブで **`recover` トークン**
  で解錠しておいたウィンドウを一瞬提示 — ナビに `Store` / `Maintenance` へのリンクが
  **一切無い**ことを指す。
- **画面期待:** 緑のトーストで復元成功。`recover` タブのナビは `Home` / `Retrieve` /
  `Lock` だけ。
- **発話（EN）:** "Same object, correct password — the file comes back. And here's a second, narrower session, logged in with a different, role-scoped token. It can decrypt and destroy. It can never reach Face setup at all."
- **注意:** **画面はこのまま。** 次の Step 4 は同じタブ・同じファイル・同じパスワードで、
  物体だけを外す。切り替えないことが「他は何も変えていない」ことの担保になる。

### Step 4 — 復元 失敗（0:50｜★★cue≠key の証明｜WebUI・Step 3 と同じ画面）

> **本書で最も重要なステップ。**
> 成功例だけでは物体キューが効いていることを**何も証明していない**。観客には
> 「パスワードを打ったらファイルが出た」としか見えない。**対比だけが証明になる。**
> **画面を切り替えないこと自体が論証の一部。** Step 3 と同じタブ、同じファイル、
> 同じパスワードで、**物体だけ**を外す。切り替えれば「他にも何か変えたのでは」が残る。
> 0.6.0 実機で WebUI 経路の拒否を確認済み（#184/#187 の修正前は、背景が鍵に
> なっていたため**物体を隠しても開いてしまっていた** — 今はこれが直っている）。

- **操作:** Step 3 と同じ Retrieve 画面のまま。**物体をカメラの視野から完全に外す**
  （手で覆うのではなく、卓の下に下ろす）→ **オーバーレイが `No object cue match` に
  変わるのを待つ** → Face 1 と同じ **Passphrase** → `Open protected file`。
- **画面期待:** **`No valid entry found.`** のエラートースト。ファイルは出てこない。
  オーバーレイは `No object cue match` / `Present a bound object to continue`。
  **`/status` の `object_state` は `none`。**
- **発話（EN）:** "Same tab. Same file. Same password. Same everything — I have only taken the object away. And notice what it says: 'no valid entry found.' Not 'wrong object', not 'object missing' — it will not even tell you what it is waiting for. That is deliberate. That is what 'the cue gates the operation' means."
- **注意:** **ここで間を取る。** これが cue≠key の唯一の実証である。
  **この直後に物体を戻して同じパスワードで再実行し、成功させる**（0:15 ほど）。
  失敗→成功の往復まで見せないと「壊れたのではない」ことが示せない。
  **この往復は省略しない** — 省くと「何を入れても拒否する状態」と区別がつかない。
- **注意（ロックアウト｜WebUI に移したことで新たに効いてくる）:** WebUI の
  `/retrieve` は**物体なしの拒否も失敗として記録する**（`_access_attempts.record_failure`）。
  既定は **5回で60秒ロック**（`PHASMID_ACCESS_MAX_FAILURES=5` /
  `PHASMID_ACCESS_LOCKOUT_SECONDS=60`）。壇上では失敗は1回なので問題ないが、
  **直前のリハーサルで使い切ると本番の Step 4 が `Access temporarily unavailable.` で
  止まる。** リハーサルは TUI の `Recover File` で行うこと（TUI 経路は
  `limiter.check()` のみで失敗を記録しないため、何度失敗させてもロックしない）。
  ロックに入ってしまった場合は **60秒待つ**（→ §5）。
- **技術的裏付け（質問された場合）:** `collect_auth_sequence()` が
  `wait_for_reference_match(timeout=10.0)` を呼び、不一致なら `match_none` を返す。
  この値は復号の入力そのもの（`_read_face_namespace` に渡る）なので、
  **照合を迂回して復元することはできない。** 0.6.0 では加えて、参照テンプレート
  自体が**空シーンとの差分領域からのみ**作られ、作成直後に「空シーンに一致しないこと」を
  検証してから保存される（#184）— 背景が鍵になる経路を実装として塞いである。

### Step 4b — 強要下でデータを守る（0:40｜任意・WebUI・Step 4 と同じ画面）

> **本番でやるかは当日判断。枠が押していれば省略**し、Step 6 の Silent Standby に
> 時間を回す（合計は 7:30 → 8:10 になる）。Step 4 と同じ画面・同じ入力欄で続けるので
> **追加の画面切替も、追加の操作手順も無い。**
> **不可逆。** 実施すると片方の Face は戻らない。次の Step 5（Audit）の数字は
> **消した後の状態**を映すので、`Faces with little or no filler` などが事前の想定と
> 変わる — これは不都合ではなく、**「今消したものが空として読める」ことを見せる材料**に
> なる。数字を事前の想定どおりに見せたい場合は 4b を省略すること。

「パスワードを強要されてもデータだけは守る」というこのツールの立ち位置を、
実演で示すステップ。**画面は何ひとつ変わらず、入れるパスワードだけが違う。**

- **操作:** Step 3・4 と**まったく同じ** Retrieve 画面。**消したい Face の物体を
  かざす** → パスワード欄に、そのアクセスパスワードではなく **Clearing password**
  （Store の Advanced security options で設定した2つめのパスワード）を入力 →
  `Open protected file`。
- **画面期待:** **`No valid entry found.`** — パスワードを打ち間違えたときと
  **完全に同じ表示**。ファイルは出てこない。**これが正しい挙動。**
  その後、同じ物体と**アクセス**パスワードで開こうとしても、もう復元されない。
  **もう一方の Face は無傷**で、そちらは物体とパスワードで開ける。
- **発話（EN）:** "Now watch this screen, because nothing on it is going to change. Same tab, same object, same field, same button. The only thing I am doing differently is typing a different password. — And it says what it says when you mistype: no valid entry found. Except that entry is not locked. It is gone. The other one is untouched, and I can still open it. That is the answer to 'they will just make you type the password.' **The password they can compel is not the only one there is.**"
- **注意（消えるのは「かざした Face」）:** 対象は画面の選択肢ではなく**カメラの物体**で
  決まる。**真の Face を消すには真の物体を出す必要がある** — 強要下では「真の物体を
  出すこと自体が情報になる」という設計上の論点があり、質問されたら**隠さずそう答える**。
  他方の Face の物体をかざした状態で Face 1 の破壊パスワードを入れても、**何も起きない**
  （どちらの Face も無事）。
- **注意（資格の分離）:** アクセスパスワードでは破壊できず、破壊パスワードでは
  ファイルが開かない。**強要してアクセスパスワードを得た側は、破壊資格を得ていない。**
- **注意（確認が無い）:** 確認ダイアログも、成功の表示も無い。**それが狙い** — 見ている
  相手に何も伝えないための設計であり、その代償として**操作者にも成否が伝わらない。**
  成功したかどうかは「その Face がもう開かないこと」でしか確認できない。
  **リハーサルで一度通しておくこと。**
- **前提（Store 時に設定していないと動かない）:** 破壊パスワードは Store 画面の
  **Advanced security options → Restricted recovery password** に入力し、その状態で
  `Protect file` を押した時に設定される。**入力しただけ／押さずに離れた場合は
  設定されない。** 未設定の Face では 4b は**ただの失敗**になり、画面上は区別できない。
- **明示的に片付けたい場合:** Retrieve 画面の
  **「Clear this entry instead of opening it」** から、破壊パスワードと確認語
  `DESTROY FACE` で消す経路も残してある。落ち着いた状況で意図的に片付けるための、
  監査可能な手段。**壇上ではこちらは使わない** — 画面が変わると対比が弱まる。
- **フォールバック:** WebUI が使えない場合は CLI —
  `phasmid emergency destroy-face <vessel> --face face_a --camera-object --confirm "DESTROY FACE"`
  （破壊パスワードは対話プロンプト）。

### Step 5 — Audit: 空き領域と、ツールが判定しないこと（0:50｜誠実性の可視化｜TUI Expert）

- **操作:** **ここでプロジェクタを TUI に戻す**（往復の折り返し。以降 Step 5〜7 は切替なし）。
  **`e`（Expert）→ `a`（Audit）**。`a` は #169 の非活性化対象から
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
  `phasmid-pi.local` はラップトップからは**到達しない**。
  **Step 2〜3（Bind・復元成功）を口頭要約に切り替え、Step 4 は TUI の `Recover File` で
  実施する** — Step 4 だけは省略してはならない（→ 下の項）。Step 0・1・5・6・7 は
  WebUI に依存しないのでそのまま実機で続行。
- **Step 4 の代替経路（WebUI が使えない場合）:** TUI で **`o`（Open）** → `Y` →
  Operation **`Recover File`**（#169 で非活性化していないのはこのため） →
  **Output file** にパス → Face 1 と同じ **Passphrase** → **物体は視野の外** →
  `Run Operation`。約10秒後、赤で **`Open Vessel / no bound object matched`**。
  WebUI 版と違い**失敗を記録しないのでロックしない**。0.4.0 実機で検証済み。
- **`Access temporarily unavailable.` が出た（WebUI ロックアウト）:** 直前の
  リハーサルで失敗を5回使い切っている。**60秒待てば解除される。** 待てない場合は
  上の TUI 代替経路に切り替える。
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

以下は実機で実際に確認した。設計からの推測ではない。物体キュー関連は **0.6.0**
（2026-07-30、Pi Zero 2 W / picamera2 / 320×240 @ 4fps）、それ以外は 0.4.0。

### 9.0 物体キュー — 0.6.0 実機検証結果（2026-07-30）

**背景:** 0.4.x では参照テンプレートが視野全体から作られており、三脚固定の背景
そのものが一致条件を満たしていた。実機で **物体を隠したまま正しいパスワードで
復号できてしまう**ことが報告され、これはデモの中心的主張の否定にあたる。
2段階撮影（#184）とその実装不具合の修正（#187）を経て、以下を実機で確認した。

| 検証項目 | 結果 |
|---|---|
| `1 · Capture empty scene`（物体をフレーム外） | 成功 |
| `2 · Capture access object`（無地の壁を背景に） | **1回で成功**（撮り直し不要） |
| 物体を下ろして `Protect file` | **拒否** — `That entry is already set up...`。**置換パネルは開かない** |
| 物体をかざし直して `Protect file` | 成功 |
| **WebUI Retrieve・物体を隠して正しいパスワード** | **拒否**（★中心的主張） |
| WebUI Retrieve・物体を戻して同じパスワード | 復元成功 |
| 登録していない別の物体 | 拒否 |
| Vessel 削除 → 新規作成 → 再登録 | 成功（0.4.x では「既に紐づいている」で止まった） |

**この結果から確定したこと:**

- **Step 4 を WebUI に移せる。** 否定証明が WebUI 経路で成立する。プロジェクタ切替は
  Step 4→5 の1回だけになり、Step 3（成功）と Step 4（失敗）が同じ画面で連続する。
- **Step 2 は 1:30 に収まる。** 撮影が2回に増えたが、1回で通れば所要は従来と同等。
- **TUI `Recover File` は本編から外れる**が、WebUI 不調時の唯一の代替経路として残す（→ §5）。

**観測に使う値:** `GET /status` の **`object_state`**（`none` / `detected` /
`matched` / `ambiguous`）。画面表示ではなくこの値で判定する。物体を隠したとき
`none` であることが、拒否の根拠が物体の不在であることの確認になる。

### 9.0.1 復元時の照合が厳しすぎた件（0.6.0 で調整）

実機で「登録はできるが Retrieve でなかなか一致しない」という症状が出た。原因は
**閾値がマスク導入前の値のまま**だったこと。`MIN_GOOD_MATCHES=50` /
`MIN_INLIERS=30` は参照テンプレートが視野全体（400〜900キーポイント）だった
時代の絶対値で、マスク後は**無地の壁で72キーポイント**しかない。

72キーポイントのテンプレートでの実測:

| 提示のしかた | good | inliers | 旧閾値 50/30 |
|---|---|---|---|
| 撮影と同一のフレーム | 62 | 62 | 一致 |
| ±6 の階調ノイズのみ | 42 | 41 | **拒否** |
| 5px ずれ＋ノイズ | 32 | 32 | **拒否** |
| 10% 近づく＋ノイズ | 35 | 34 | **拒否** |

**6通りの提示のうち一致したのは1つだけ**で、しかも壊した要因（±6のノイズ）は
実機のセンサーノイズより小さい。inliers が good にほぼ一致しているので幾何は
合っており、落としていたのは絶対数だけだった。

**0.6.0 では閾値をテンプレートのキーポイント数に対する割合にした**
（既定 good 25% / inliers 15%、絶対値を上限、下限は 12/8）。**上限があるので
従来より厳しくなることはない。** 割合化しても識別性は落ちない — 同じ場面で
**空シーンも別の物体も good=0** であり、余裕は「42 対 49」ではなく「42 対 0」だから。
調整後は6通りすべてが一致し、負例4通りはすべて拒否のまま。

### 9.0.2 破壊経路の実機検証で出た3つの不具合（0.6.0・#190 で修正）

Step 4b を実機で試したところ「60秒ロックが延々と続き、破壊パスワードを受け付けない」
という報告が出た。原因は**独立した3つのバグ**だった。

| # | 症状 | 原因 |
|---|---|---|
| 1 | 60秒待ってもロックが続く | 失敗カウンタが**成功でしか0に戻らなかった**。60秒経過後も5回のまま残り、次の1回の失敗で即座に再ロック。成功を出せない状況では永久に抜けられない |
| 2 | （CLI/TUI 側）ロックが数えられない | `FileAttemptLimiter` が**2回目の失敗を保存できなかった** — 同じ phase への書き直しが「不正な状態遷移」として拒否されていた。CLI 側のロックは実は一度も1回を超えて数えていない |
| 3 | 正しい破壊パスワードが通らない | `destroy_face` が**レジストリの `object_binding` 指紋を要求**していたが、**WebUI はこれを一切書かない**（WebUI は ORB キューで縛る）。WebUI で保存した Face は例外なく `object binding not registered` になり、それが `Operation rejected.` として表示されるので**パスワード間違いと見分けがつかなかった** |

3 は CLI のフォールバック（`phasmid emergency destroy-face`）にも同じ穴があり、
**WebUI で保存したデータは CLI からも破壊できなかった。** 現在は2つの縛り方の
どちらでも受け付ける — **証明の方法が違うだけで、どちらも「今その物体をかざしている
こと」は要求する。**

実測（WebUI で保存した Face・修正後）: 正しい物体＋正しい破壊パスワード → 破壊成功。
**もう一方の Face は無傷で開く。** 消した側は正しい物体＋アクセスパスワードでも開かない。
物体なし／別の物体／パスワード違いはいずれも拒否。

**現地で更に調整が必要な場合**（照明が極端、物体が小さいなど）:

```bash
# 一致しにくい → 割合を下げる（0 にすると下限 12/8 まで緩む）
PHASMID_CUE_GOOD_MATCH_RATIO=0.15 PHASMID_CUE_INLIER_RATIO=0.10 \
  bash scripts/pi_zero2w/run_demo_console.sh
```

**下げたら必ず否定証明を再確認すること**（物体を隠して拒否されるか／別の物体で
開かないか）。**緩めた状態で Step 4 が成立しなければ、デモの主張そのものが崩れる。**

### 9.0.3 背景が変わると認識しない件（0.6.1 で修正）

**実機で報告された最も重大な欠陥。** 登録した場所と違う背景では、**同じ物体でも
認識しなかった。** つまり「暗号化したときと同じ環境でないと取り出せない」— 持ち歩いて
別の場所で使う前提の道具として、これは仕様の否定にあたる。

**原因:** `to_gray` が `cv2.equalizeHist`（**フレーム全体**の大域的な階調変換）を
使っていた。2段階撮影（#184）でテンプレートの**範囲**は物体に限定できていたが、
その画素の**値**は「背景を含む全体のヒストグラム」から決まる写像を通していた。
背景が変われば写像が変わり、**物体のバイト列が同一でも記述子が変わる。**

同一の物体画素を別の背景に合成した実測（バーは good>12）:

| 背景 | equalizeHist（旧） | CLAHE（新） |
|---|---|---|
| 登録した壁と同じ | good 25 → 一致 | good 502 → 一致 |
| 暗い壁 | **good 4 → 拒否** | good 212 → 一致 |
| 明るい壁 | good 25 → 一致 | good 426 → 一致 |
| 別の部屋（模様のある壁） | **good 1 → 拒否** | good 243 → 一致 |
| （否定）物体なしの空シーン | 0 | **0** |
| （否定）別の物体 | 0 | **0** |

**CLAHE（タイルごとの局所的な平坦化・16×16）に変更した。** 遠くの領域が変わっても
物体のタイルの写像は変わらない。**否定側は 0 のまま**なので、cue≠key の主張は保たれる。

副次的な効果として、無地の壁でのテンプレートのキーポイントが **25 → 505** に増えた
（大域変換は無地の壁のヒストグラムに支配され、物体自身のコントラストを潰していた）。

**その結果 `PHASMID_CUE_GOOD_MATCH_RATIO` を 0.25 → 0.18 に下げた。** キーポイントが
増えると「割合」のバーは絶対値として上がるため、**5度傾けた提示**と**1割寄せた提示**が
逆に落ちるようになったため。0.18 はその2つが戻る**最小の値**で、それ以上は緩めていない。

> **【重要・移行】登録済みの物体は登録し直しが必要。** 記述子は切り出した階調空間の
> 中でしか比較できないので、旧版で登録したテンプレートは新版では一致しない。
> **黙って一致しなくなるのを避けるため、旧空間のテンプレートは「未登録」として扱う**
> （`ObjectCueStore.DESCRIPTOR_SPACE`）。Store 画面で撮り直せばよい。

### 9.0.4 「登録はできるが認識しない」を数値で切り分ける

閾値をいじる前に、**どこで落ちているか**を先に確定させる。当てずっぽうで緩めると
否定証明（Step 4）まで一緒に壊れる。

映像を見ながら数字を出す:

```bash
PHASMID_CUE_DEBUG=1 bash scripts/pi_zero2w/run_demo_console.sh
```

`w` → Store / Retrieve のページ → 物体をかざす。プレビュー下端に
`entry N  tpl 213  frame 900  good 5/50  inliers 5/30` が出る。
記録が要るなら（コンソールを止めて）:

```bash
.venv/bin/python scripts/pi_zero2w/measure_cue_margin.py --frames 10 --save /tmp/cue
```

| 症状 | 読み方 | 効く手 |
|---|---|---|
| `frame` が **0〜数十** | カメラが見えていない（ボケ・暗い・黒画像） | ピント・照明。**閾値をいじっても無駄** |
| `frame` は数百、`good` が**ひと桁** | テンプレートがかざした物と**対応していない** | 登録し直す。照明が変わっていれば特に |
| `good` は多いが `inliers` が**極端に少ない** | **幾何が合っていない = 立体物を別角度で見せている** | `PHASMID_CUE_RANSAC_PX` を上げる（例 `12`）。本筋は**平面のプロップに替える** |
| `good`・`inliers` とも閾値の**8割前後** | あと一歩 | `PHASMID_CUE_GOOD_MATCH_RATIO` / `..._INLIER_RATIO` を下げる |

**閾値調整で届くのは最後の行だけ。** `good` が閾値の1割しか出ていない状態は、
どんなに緩めても届かない — 原因が別のところにある。

**照明で変わる件:** カメラは **NoIR**（IR カットフィルタ無し）なので、昼光と室内 LED
では同じ物体でも写り方が大きく変わる。**「昨日は認識したのに今日はしない」の第一容疑は
これ。** テンプレートは撮った瞬間の光の記録でしかないので、**本番と同じ照明で登録し直す**
のがいちばん確実で、所要1分。

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
  `Add File` だけを Select の選択肢から外した。`Recover File` は 0.6.0 で Step 4 が
  WebUI に移った後も、**WebUI 不調時に否定証明を成立させる唯一の代替経路**として
  残している。内部の `add` コードパスはそのまま残しており、選択肢に
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

**Bind/Operate/否定証明とも実機で WebUI 経由を検証済み（0.6.0）**

Face 1・Face 2 の登録から復元、そして**物体を隠したときの拒否**まで、WebUI の
Store/Retrieve 画面だけで完結する流れを実機で確認した（→ §9.0）。Step 2〜4 は
この結果を反映している。

**物体キューが実際に効いていることの根拠**

WebUI の2段階撮影（Store画面）で参照テンプレートを登録し、Retrieve は
`collect_auth_sequence()` → `wait_for_reference_match(timeout=10.0)` で照合する。
不一致なら `match_none` が返り復元が拒否される。
一致トークンは `_read_face_namespace` の入力そのものなので、**照合を迂回した復元は
成立しない。**

**ただし 0.4.x では、この論証は実装によって空洞化していた。** 参照テンプレートが
視野全体から作られていたため背景そのものが一致条件を満たし、`wait_for_reference_match`
は物体が無くても一致を返していた。0.6.0 では (a) テンプレートを空シーンとの差分領域
からのみ作り、(b) 作成直後に「空シーンに一致しないこと」を検証してから保存する
（#184/#187）。**上の論証が成り立つのはこの2点があってのこと** — 照合ロジックの
存在だけでは足りない、というのがこの不具合の教訓である。

TUI 経由の Recover File も同じ照合ロジックを使うが、**この過程を一切表示しない**
（→ #158。WebUI は `STABLE MATCH` バッジとライブ映像でこれを表示できる）。

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

- **物体キューの否定証明（Step 4）は WebUI・TUI 双方で検証済みになった**（0.6.0・→ §9.0）。
  0.4.x 版で残していた「WebUI 経由未検証」はこれで解消。
- **画像ファイルからの参照登録は 2段階撮影を経ていない。** `/register_key` に画像を
  アップロードする経路は空シーンを持たないため、**視野全体からテンプレートを作る
  0.4.x と同じ方式のまま**である。部屋が写り込んだ写真を使うと背景が一致条件を
  満たしうる。デモでは使わないが、質問された場合は**この差を隠さず答えること**
  （物体だけを切り抜いた写真なら問題ない）。
- **CLI と TUI の登録経路も 2段階撮影に未移行。** 本デモは WebUI で登録するため
  影響しないが、これらの経路で登録した参照は同じ弱点を持つ。
- **Step 4b（パスワードによる破壊）は実機で確認済み**（0.6.0・#191）。物体A＋破壊
  パスワードで Face A が消え、Face A はもう開かず、Face B は無傷で開くところまで
  実機で通した。**画面に何も出ないのが正しい挙動**なので、確認は必ず「そのあと開かない
  こと」で行う。
- **明示的な `Clear this entry` パネル（`/destroy_face`）は実機で動作未確認。**
  復号成功後にカメラが解放されて物体が見えなくなる問題は #192 で修正したが、
  **修正版を実機で通してはいない**。**壇上では使わない経路**なので本番には影響しない。
- **閾値は #188 で割合ベースに変更済み**（good 25% / inliers 15%、下限 12/8、絶対値が
  上限）。§9.0.1 の実測に基づく。**ただし調整の根拠は合成画像**で、実機で余裕が
  どれだけあるかは測っていない。照明・距離が大きく変われば再調整が要る
  （`PHASMID_CUE_GOOD_MATCH_RATIO` / `PHASMID_CUE_INLIER_RATIO`）。
**残課題（本番までに必須ではないが、残っているもの）**

- **画像ファイルからの参照登録は 2段階撮影を経ていない**（上記・issue #193）。
- **CLI と TUI の登録経路も 2段階撮影に未移行**（上記・issue #193）。
- **Doctor の `Automatic Destruction` は破壊パスワードを知らない。** 環境変数2つ
  （`PHASMID_DURESS_MODE` / `PHASMID_PURGE_CONFIRMATION`）しか見ていないので、
  「この Face には、通常の入力欄に入れると黙って消えるパスワードが設定されている」
  ことは報告されない。ただし env 変数と違い**操作者がそのパスワードを打たない限り
  発火しない**ので、優先度は低い（issue #194）。
- #157（Doctor の Dummy Profile 助言が既定パス判定のため未設定端末で永久に警告していた
  問題）は解決済み。残る既知の未解決事項は #158（TUI の照合表示）。
