# Phasmid — Live Demo 実施細部要領 / Demo Runbook

**対象:** DEF CON Demo Labs 本番の実機デモ（Deck Slide 24）。プレゼン30分のうち**約7分**を割り当て、**Q&A/交流15分を必ず確保**する。
**画面:** 実TUI（Local Disclosure Control）＋必要に応じてローカルWebUI（127.0.0.1）。

> **情報の確度について**
> - **確定（TUI実画面で確認済み）:** 下部コマンドバーのキー — `o Open / c Create / i Inspect / f Faces / g Guided / a Audit / d Doctor / s Settings / l LUKS / ? Help / q Quit / w WebUI / ^p palette`、パネル構成（Vessels「Deniable container files」/ Vessel Status / Operator Log）、Operator Log の Dummy Profile 指標（Size / File Count / Occupancy Ratio / Plausibility assessment）、上部警告 `! SYSTEM: n WARN`。
> - **本番前に確定（ビルド依存・要確認）:** 各キー押下後のサブダイアログの項目名・入力順、**Silent Standby の割当キー**、Faces の物体登録手順の細部、demo/coercion_safe モードの切替UI。→ 本書では 〔要確認〕 と明示。

---

## 1. 制約と時間予算 / Constraints & budget（合計 ~7:00）
| # | フェーズ | 目安 | 対応スライド概念 |
|---|---|---|---|
| 0 | オリエンテーション | 0:20 | TUIホーム提示 |
| 1 | Vessel 作成（Create） | 1:00 | Prepare |
| 2 | 物体キュー登録（Faces） | 1:20 | Bind（cue≠key） |
| 3 | Guided（prepare→bind→operate） | 1:30 | Operate |
| 4 | Audit（plausibility） | 0:50 | 誠実性の可視化 |
| 5 | WebUI 起動 | 0:50 | ローカル境界 |
| 6 | Silent Standby → dummy_disclosure | 1:00 | Disclose / 山場 |
| 7 | ラップ | 0:10 | 締め |

> **時計運用:** 開始 ~19:20。**26:00 を超えたら残手順を口頭要約**して締めへ。

---

## 2. 事前準備チェックリスト / Pre-flight

### T-30分（設営時）
- [ ] 実機（Pi Zero 2 W + カメラ + 三脚）を卓上に設置、電源・給電確認。
- [ ] 表示系: TUIを映すHDMI/USB-C出力、またはPCへの画面ミラー経路を確立。**プロジェクタ入力の切替キーを把握**。
- [ ] カメラのピント・画角・照明を確認（物体が安定認識される距離に三脚固定）。
- [ ] **デモ用プロファイルで初期化**（実運用の秘匿データは載せない）。認識モードは **`demo` または `coercion_safe`** に設定 〔要確認: 切替UI〕。
- [ ] **バックアップ録画**（全手順を通した2〜3分クリップ）を再生機に用意し**頭出し**。
- [ ] 予備電源／ケーブル、ネットワーク不要（WebUIはUSB/localhost）を再確認。

### T-5分（登壇直前）
- [ ] TUIをホーム画面（`PHASMID / LOCAL DISCLOSURE CONTROL`）で待機。
- [ ] `! SYSTEM: n WARN` の内容を `press to review` で事前確認し、想定内であることを把握（聴衆に説明できる状態に）。
- [ ] デモ用パスフレーズ／物体プロップを手元に。**実秘匿は使わない**。
- [ ] Silent Standby の割当キーを最終確認 〔要確認〕。指が迷わない位置に。

---

## 3. 初期状態 & リセット / Initial state & reset
- **初期状態:** Vessels は空（"No vessels registered"）または既知のデモVesselのみ。Operator Log はクリーンまたはデモ用ログ。
- **各サイクル後リセット:** デモVesselを削除/初期化し、Silent Standby を `active` に戻す。次回のために §7 を実施。

---

## 4. 実施手順 / Step-by-step
> 表記: **キー** = TUI下部バーのキー押下（確定情報）。〔要確認〕= ビルド依存の細部。発話は最小限、手を動かすことを優先。

### Step 0 — オリエンテーション（0:20）
- **操作:** ホーム画面を提示。下部コマンドバーを指す。
- **発話（EN）:** "This is the real TUI — Local Disclosure Control. Watch the bottom bar; everything I do maps to one of these."
- **画面期待:** `PHASMID` ロゴ、Vessels / Vessel Status / Operator Log、下部バー表示。
- **注意:** 上部 `! SYSTEM: n WARN` が出ていれば一言で触れる（"and it's honest about its own warnings"）。

### Step 1 — Create a Vessel（1:00｜Prepare）
- **操作:** **`c` (Create)** → デモVessel名・サイズ等を入力 〔要確認: 項目/入力順〕。
- **発話（EN）:** "First I create a **vessel** — a deniable container file. This is the Prepare step."
- **画面期待:** Vessels 一覧に新規Vesselが出現、Vessel Status に容量/posture が反映。
- **失敗時:** 作成が滞れば既存デモVesselを **`o` (Open)** して以降を継続。

### Step 2 — Object cue via Faces（1:20｜Bind, ★cue≠key）
- **操作:** **`f` (Faces)** → カメラに物体プロップを提示し、キューとして登録/選択 〔要確認: 登録フロー〕。
- **発話（EN）:** "Now the object cue — under **Faces**. I show an everyday object to the camera. Remember: this is a **cue, not a key**. It gates the action; it is not the encryption key. A photo of it unlocks nothing."
- **画面期待:** キュー登録/一致のフィードバック表示。
- **注意:** ここが概念の要。**必ず cue≠key を口頭で言い切る。** 認識が不安定なら距離/照明を微調整、または `demo` モードで確定的に見せる 〔要確認〕。
- **失敗時:** 一致が得られなければ、`coercion_safe` の挙動（低信頼→ダミー経路）として**むしろ設計意図を説明**（Step 6の伏線）。

### Step 3 — Guided flow（1:30｜Operate）
- **操作:** **`g` (Guided)** → prepare → bind → operate の誘導に沿って進める。
- **発話（EN）:** "The **Guided** flow walks Prepare, Bind, Operate — the same four-step map from the slides. I bind the vessel to local state and the cue, then operate on the visible surface."
- **画面期待:** 各段階の状態遷移が Vessel Status / Operator Log に表示。
- **失敗時:** 個別操作（Open/Inspect）で代替し、フローの意味を口頭で補完。

### Step 4 — Audit: plausibility（0:50｜誠実性の可視化）
- **操作:** **`a` (Audit)**。Operator Log の Dummy Profile 指標を指す。
- **発話（EN）:** "**Audit** scores the dummy profile — size, file count, occupancy, and a **plausibility assessment**. If the decoy isn't plausible, the tool says so. No self-deception."
- **画面期待:** Operator Log に `Dummy Profile Size / File Count / Occupancy Ratio / Plausibility assessment: …`。
- **注意:** 「ツールが自分のダミーの弱さを正直に指摘する」点＝倫理スライドと接続。

### Step 5 — Local WebUI（0:50｜ローカル境界）
- **操作:** **`w` (WebUI)** で 127.0.0.1 起動 → 画面提示（任意でブラウザ側に切替）。
- **発話（EN）:** "The same controls are available over a **local WebUI** — bound to 127.0.0.1 by default. Reaching it from a tethered laptop over USB is an explicit opt-in that binds only the USB interface. It never touches a network."
- **画面期待:** WebUI 起動通知／localhost URL。TUIには露出バナー等 〔要確認〕。
- **注意:** ブラウザに切替える場合は**事前にタブ用意**。切替に手間取るならTUI内表示のみで可。ノートPCのブラウザからUSB経由で開く場合は、事前に `PHASMID_WEBUI_EXPOSE_GADGET=1` を設定しておくこと（既定はloopbackのみでノートPCからは到達不可）。TUIバナーには実際のbindアドレスが表示される。
- **失敗時:** 起動が遅ければ口頭説明に留め、TUIへ戻る（時間優先）。

### Step 6 — Silent Standby → dummy_disclosure（1:00｜★Disclose 山場）
- **操作:** **Silent Standby 割当キー** 〔要確認〕を押下 → 状態が `active → standby`（必要に応じ `sealed`）→ **`dummy_disclosure`** へ。
- **発話（EN）:** "Now the moment it's built for. One hotkey — **Silent Standby**. The sensitive surface drops away, and under pressure I can present a **dummy disclosure**. Recovery needs re-auth. I'm not hiding from forensics — I'm buying **time** and **uncertainty**."
- **画面期待:** UIが非機微状態へ遷移、ダミー開示ビュー提示。状態表示 `dummy_disclosure`。
- **注意:** **本デモの山**。ゆっくり、間を取る。倫理（Slide 21）に接続して締める。
- **失敗時:** 遷移が出なければ録画の該当箇所を提示。「これが唯一の“魔法に見える”部分。実体はStateマシンです」と補足。

### Step 7 — ラップ（0:10）
- **発話（EN）:** "That's Prepare, Bind, Operate, Disclose — on real hardware. Come try it at the table."
- **操作:** ホームへ戻す。プロジェクタ入力をスライドへ復帰（Slide 25）。

---

## 5. フォールバック方針 / Fallbacks
- **個別ステップ:** 上記各 Step の「失敗時」に従い、**止まらず前進**。1ステップに固執しない（最大15秒で見切り）。
- **全体（実機不調）:** 章扉（Slide 23）で頭出しした**録画に即切替**。"The design points stand either way." と明言し、Prepare→Bind→Operate→Disclose を録画上で辿る。
- **認識不安定:** `demo` モードで確定的に見せる 〔要確認〕。または `coercion_safe` の低信頼→ダミー挙動を**設計意図として逆手に説明**。
- **時間超過:** 26:00 到達で Step 5 以降を口頭要約し Step 6 の山だけ見せる。

---

## 6. 安全・運用注意 / Safety
- **実秘匿データを絶対に投影しない。** デモ用プロファイル／ダミーのみ。
- パスフレーズはカメラ・投影に映さない。物体プロップは公開して問題ないものを使用。
- WebUIはlocalhost/USBのみ。会場ネットワークに晒さない。
- 監査ログ（opt-in）を使う場合、秘匿情報が記録されない設定であることを確認 〔要確認〕。

---

## 7. 終了後リセット / Teardown（次サイクル・次回のため）
- [ ] デモVesselを削除/初期化。
- [ ] Silent Standby を `active` に復帰。
- [ ] Operator Log をデモ用初期状態へ。
- [ ] WebUIプロセス停止（またはinactivity auto-kill 10分待機を利用）。
- [ ] カメラ画角・三脚位置を再固定。

---

## 8. 本番前に確定する項目 / Fill-ins（作者のみ設定可）
- [ ] **Silent Standby の割当キー**（Step 6）。
- [ ] Create ダイアログの項目名・入力順（Step 1）。
- [ ] Faces の物体登録フロー詳細（Step 2）。
- [ ] 認識モード切替UI（`demo` / `coercion_safe`）の操作（設営時／失敗時）。
- [ ] WebUI 提示方法（TUI内表示 or ブラウザ切替）と露出バナー挙動（Step 5）。
- [ ] デモ用パスフレーズ・物体プロップ・デモVessel名。
- [ ] バックアップ録画ファイルと頭出し位置。

> 上記〔要確認〕は**ビルドの実挙動に合わせて1行ずつ確定**すれば、本書はそのまま本番運用可能な粒度になります。
