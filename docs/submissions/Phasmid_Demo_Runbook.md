# Phasmid — Live Demo 実施細部要領 / Demo Runbook

**対象:** DEF CON Demo Labs 本番の実機デモ（Deck Slide 24）。プレゼン30分のうち**約7分**を割り当て、**Q&A/交流15分を必ず確保**する。
**画面:** 実TUI（Local Disclosure Control）＋**ローカルWebUI（物体キューの提示に必須）**。

> **情報の確度について**
> - **本書は 0.3.0 実機（Pi Zero 2 W / Raspberry Pi OS Trixie）で全手順を通した結果に基づく。** 〔要確認〕は原則として解消済み。実機で確認していない項目のみ §9 末尾に明示する。
> - **前版からの重要な変更:** Step 2 の画面が違っていた（Faces ではなく Open Vessel 系）。Step 4 の参照先が違っていた（Operator Log ではなく Audit）。物体キューの提示は **WebUI が主、TUI が従**に変わった。Generate Plausibility は**実測4分のため壇上から外した**。
> - **注意:** 0.1.4 までは起動直後が Expert 相当の単層画面だった。それ以前の手順書のキー順は**そのままでは通らない**。

---

## 0. 本番でやってはいけないこと（先に読む）

鍛錬中に実際に踏んだものだけを挙げる。

| やってはいけない | 理由 | 代わりに |
|---|---|---|
| **マウスでボタンを押す** | SSH越しのターミナルではクリックイベントがTextualに届かない。ボタンはフォーカスされるだけで発火しない | **`Tab` / `Shift+Tab` で移動し `Enter`**。全操作をキーボードで行う |
| **壇上で Generate Plausibility を実行** | 64 MiB / 15% で**実測約4分**。枠は1:20 | **事前生成**しておき、壇上では **Inspect Plausibility** のみ |
| **`d`（Doctor）を開く** | Dummy Profile の4件は旧 `vault.bin` 層を見ており、生成済みでも `0 B / LOW` と報告する。Audit画面と矛盾して見える | 可信性の話は **`a`（Audit）** で行う |
| **素の `phasmid` で起動** | libcamera のログがTUIを破壊する／WebUIがラップトップから見えない／トークンが毎回変わる／`Ctrl+S` が効かないことがある | **`scripts/pi_zero2w/run_demo_console.sh`** を使う |
| **成功例だけを見せる** | 物体キューが効いていることの証明にならない。観客にはただのパスワード復号に見える | **物体なしの失敗を必ず見せる**（Step 3b） |

---

## 1. 制約と時間予算 / Constraints & budget（合計 ~7:00）

| # | フェーズ | 目安 | 画面 | 対応スライド概念 |
|---|---|---|---|---|
| 0 | オリエンテーション | 0:20 | TUI Simple | TUIホーム提示 |
| 1 | Vessel 作成（Create） | 0:50 | TUI Simple | Prepare |
| 2 | 物体キュー登録（Bind） | 1:10 | **WebUI** | Bind（cue≠key） |
| 3a | 復元 成功（Operate） | 0:40 | **WebUI** | Operate |
| 3b | **復元 失敗（物体なし）** | 0:40 | **WebUI** | **★cue≠key の証明** |
| 4 | Audit（plausibility） | 0:50 | TUI Expert | 誠実性の可視化 |
| 5 | Silent Standby | 1:20 | TUI | Disclose / 山場 |
| 6 | ラップ | 0:10 | TUI Simple | 締め |

> **時計運用:** 開始 ~19:20。**26:00 を超えたら残手順を口頭要約**して締めへ。
> **旧版との違い:** WebUI 単独ステップ（旧 Step 5）を廃止し Step 2/3 に統合、Step 3b を新設した。

---

## 2. 事前準備チェックリスト / Pre-flight

### T-30分（設営時）

- [ ] 実機（Pi Zero 2 W + カメラ + 三脚）を卓上に設置、電源・給電確認。
- [ ] 表示系: TUIを映す経路と、**ラップトップのブラウザを映す経路**の両方を確保。**入力切替キーを把握**（Step 1→2 と Step 3b→4 で2回切り替える）。
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
- [ ] **【重要】Generate Plausibility を事前実行しておく**（約4分）。
      `e` → `f` → パスフレーズ2つ → `Tab` で Generate → `Enter`。
      経過時間が表示され画面は固まらない。完了後 `Plausibility Profile` が
      `Level: HIGH` になっていることを確認。
- [ ] ラップトップのブラウザで `http://10.12.194.1:8000/unlock` を開き、
      トークン（既定 `phasmid-demo-token`）を入力して**Homeまで進めた状態でタブを用意**。
      ※ `phasmid-pi.local` は使わない。**IPアドレス直指定**。
- [ ] **バックアップ録画**（全手順を通した2〜3分クリップ）を再生機に用意し**頭出し**。
- [ ] 予備電源／ケーブル。会場ネットワークは不要（WebUIはUSBガジェット面のみ）。

### T-5分（登壇直前）

- [ ] TUIを **Simple Operator 画面**で待機。
- [ ] **`! SYSTEM: n WARN` は Simple 画面には出ない**（Expert専用）。内容を確認したい場合は
      `e` を押し、**確認後 `Esc` で Simple に戻しておくこと。**
- [ ] WARN 7件の内訳を把握（→ §6）。質問された場合の答えを用意。
- [ ] デモ用パスフレーズ／物体プロップを手元に。**実秘匿は使わない**。
- [ ] Silent Standby は **`Ctrl+S`**（既定）。復帰は **`Ctrl+R`** または **`Esc`**。
      **フッタに出ないので指で覚えておく。**

---

## 3. 初期状態 & リセット / Initial state & reset

- **初期状態:** Simple Operator 画面。Vessels は空（`No protected storage found.`）。
- **可信性プロファイル:** **事前生成済みの Vessel を別途用意しておく。** Step 1 で作る
  Vessel は空のままでよく、Step 4 では生成済みの方を見せる。**壇上で生成しないこと。**
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

- **操作:** **`n` (New)** → `vessel-path` → `vessel-size`（Select、既定 `512M`）→
  `vessel-label`（"Non-sensitive label"、任意）→ `create-btn`。
- **発話（EN）:** "First I create a **vessel** — a deniable container file. This is the Prepare step. It has no header and no magic bytes: on disk it is indistinguishable from random data."
- **画面期待:** `PROTECTED STORAGE` に新規Vesselが出現。
  **下段のパネルが `Choose an action:` に変わること**（空状態メッセージが消える）。
- **注意:** Vessel を作ると **Face が2つ自動生成される**（`face_a` / `face_b`、ともに `available`）。
  **Create Face を押す必要はない。デモ手順に含めない。**
- **任意:** `e` → `i`（Inspect）で `Header absent` / `Magic Bytes absent` /
  `Entropy high / random-like (8.00 bits/byte)` を見せると Slide 19 の直接的裏付けになる。
- **失敗時:** 作成が滞れば既存デモVesselを **`o` (Open)** して以降を継続。

### Step 2 — Object cue via WebUI（1:10｜Bind, ★cue≠key）

> **旧版からの変更:** 旧版はこれを `f` (Faces) と記載していたが**誤り**。Faces 画面は
> ラベルと可信性プロファイルの管理画面で、**カメラに一切関与しない**。物体キューを
> 扱うのは Open Vessel 系のフロー（`Add File`）である。
> さらに、TUI には**カメラ映像も一致状態の表示もない**。観客には何も見えない。
> **WebUI にはライブ映像と一致バッジがある。ここは WebUI で見せる。**

- **操作:** TUI で **`w`** を押して WebUI を起動。プロジェクタをラップトップの
  ブラウザに切替。**Store** 画面へ。ファイルを選び、パスフレーズを入力し、
  **物体をカメラに提示**。
- **画面期待:**
  - **Camera Preview** にライブ映像
  - 右上の **`objectBadge`** が `Unavailable` → `Detected` → **`Matched`（緑）** と遷移
  - 一致するとカメラ枠が視覚的に強調される
- **発話（EN）:** "Now the object cue. I show an everyday object to the camera — you can see exactly what the device sees, and the badge turns green when it has a stable match. Remember: this is a **cue, not a key**. It gates the operation; it is not the encryption key. A photograph of this object unlocks nothing."
- **注意:** ここが概念の要。**必ず cue≠key を口頭で言い切る。**
- **失敗時:** 認識が不安定なら距離/照明を微調整。起動スクリプトの既定
  `PHASMID_RECOGNITION_MODE=demo` で確定的に見せられる。
- **TUIで代替する場合:** `o`（Open）→ Operation を **`Add File`** に変更 → 入力ファイル →
  パスフレーズ2つ → `Run Operation`。**ただし画面には何も表示されない**ので、
  Step 3b の失敗対比が一層重要になる。

### Step 3a — 復元 成功（0:40｜Operate｜WebUI）

- **操作:** **Retrieve** 画面へ。物体を提示し、バッジが **Matched** になるのを待ってから
  パスフレーズを入力して実行。
- **発話（EN）:** "Same object, correct password — the file comes back."
- **画面期待:** 復元成功。

### Step 3b — 復元 失敗（0:40｜★cue≠key の証明｜WebUI）

> **本書で最も重要なステップ。旧版には存在しなかった。**
> 成功例だけでは物体キューが効いていることを**何も証明していない**。観客には
> 「パスワードを打ったらファイルが出た」としか見えない。**対比だけが証明になる。**

- **操作:** **物体をカメラの視野から外す**（退ける、または手で覆う）。
  **パスフレーズは全く同じものを入力**して、もう一度 Retrieve を実行。
- **画面期待:** バッジが **Matched にならない**まま、約10秒後に失敗。
  TUIで同じことをすると `no bound object matched` のエラーになる。
- **発話（EN）:** "Same file. Same password. Only the object is gone. The device waits ten seconds for a match, does not get one, and refuses. That is what 'the cue gates the operation' means — and notice it tells you almost nothing about *why* it failed. That is deliberate."
- **注意:** **ここで間を取る。** これが cue≠key の唯一の実証である。
- **技術的裏付け（質問された場合）:** `collect_auth_sequence()` が
  `wait_for_reference_match(timeout=10.0)` を呼び、不一致なら `match_none` を返す。
  この値は復号の入力そのもの（`_read_face_namespace` に渡る）なので、
  **照合を迂回して復元することはできない。**

### Step 4 — Audit: plausibility（0:50｜誠実性の可視化｜TUI Expert）

- **操作:** プロジェクタをTUIに戻す。**`e`（Expert）→ `a`（Audit）**。
  **`Plausibility Baseline` セクション**を指す。
- **画面期待:**
  ```
  Plausibility Baseline
    Tracked Vessels        1
    Tracked Faces          2
    High baseline faces    1
    Medium baseline faces  0
    Low baseline faces     1
  ```
- **発話（EN）:** "**Audit** scores each face independently. One face has a high-plausibility decoy profile; the other is still weak, and the tool says so rather than letting me believe otherwise. If the decoy isn't plausible, you should know before you need it."
- **注意（旧版の誤り）:** 旧版は「**Operator Log の Dummy Profile 指標を指す**」と
  指示していたが、**あの4行は Doctor 由来で、Vessel の生成結果を反映しない**
  （旧 `vault.bin` / `.state/dummy_profile` 層を見ている）。生成済みでも `0 B / LOW` と
  出るため、読み上げると矛盾が露見する。**必ず Audit 画面を指すこと。**
- **注意:** **`d`（Doctor）は開かない。** 上部の `! SYSTEM: 7 WARN — press [d] to review`
  について質問された場合は §6 の答えを使う。

### Step 5 — Silent Standby（1:20｜★Disclose 山場｜TUI）

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

### Step 6 — ラップ（0:10）

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
  ラップトップからは**到達しない**。最悪、Step 2/3 をTUIに落とす
  （ただし Step 3b の失敗対比だけは必ず見せる）。
- **時間超過:** 26:00 到達で Step 4 を飛ばし、**Step 3b と Step 5 だけは必ず見せる**。

---

## 6. `! SYSTEM: 7 WARN` の内訳（質問対策）

Expert画面に出る7件の内訳。**いずれも想定内**である。

| 件数 | 内容 | 説明 |
|---|---|---|
| 4 | Dummy Profile Size / File Count / Occupancy Ratio / Plausibility | **既知の不整合。** これらは旧 `vault.bin` / `.state/dummy_profile` を検査しており、Vessel の Face に生成した可信性プロファイルを参照しない。Vessel側の実態は Audit 画面（Step 4）が示す |
| 2 | Swap active / Compressed swap (zram) enabled | ツールが**自ホストを正直に報告**している。無効化すれば消えるが、Pi Zero 2 W では実用上有効にしている |
| 1 | `/tmp` is world-writable | 同上 |

- **発話（EN、質問された場合）:** "It warns about its own host — swap is on, so pages can hit disk. It's telling me the truth about an environment it doesn't control. Four of those warnings point at a legacy check path we're consolidating; the Vessel-level view is under Audit."

---

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
- [ ] **次サイクル用に Plausibility を再生成（約4分）。** サイクル間に時間がない場合は、
      生成済みVesselを複数用意しておき差し替える。
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

- `CreateVesselScreen`（`n`）: `vessel-path` → `vessel-size`（Select、既定 `512M`）→
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

**物体キューが実際に効いていることの根拠**

`Add File`（`capture_reference=True`）で参照画像を登録し、`Recover File` は
`collect_auth_sequence()` → `wait_for_reference_match(timeout=10.0)` で照合する。
不一致なら `match_none` が返り `ValueError("no bound object matched")` になる。
一致トークンは `_read_face_namespace` の入力そのものなので、**照合を迂回した復元は
成立しない。** ただし**TUIはこの過程を一切表示しない**（→ Step 2 を WebUI で行う理由）。

**性能実測（Pi Zero 2 W）**

| 操作 | 実測 |
|---|---|
| Generate Plausibility（64 MiB / 15% ≒ 9.6 MB） | **約4分** |
| カメラ初期化（libcamera / imx708） | 約0.6秒 |
| 物体照合タイムアウト | 10秒（`collect_auth_sequence`） |
| Textual アイドル時CPU | 約20〜25%（画面フォーカス時 約50%） |

デバイスアイドル時 48.9 °C、`get_throttled=0x0`。卓上デモの排熱・電源計画の参考。

**Doctor の baseline（新品状態）**

`run_doctor_checks()`（非TUI、`services/doctor_service.py`）は27チェックを返し、
うち **7 WARN**（内訳は §6）。zram を無効化すれば5件まで下がる。

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
  残る既知の未解決事項は Issue #157（Doctor の参照層）と #158（TUI の照合表示）を参照。
