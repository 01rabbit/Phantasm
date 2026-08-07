# Phasmid — Live Demo 実施細部要領 / Demo Runbook

**対象:** DEF CON Demo Labs 本番の実機デモ（Deck Slide 24）。プレゼン30分のうち**約8分半**を割り当て、**Q&A/交流15分を必ず確保**する。
**画面:** TUI（Local Disclosure Control）で Prepare を見せ、**以降はすべてローカル WebUI** で行う。**画面切替は SCENE 1→2 の片道1回だけで、TUI には戻らない。**

> **情報の確度について**
> - **本書は 0.6.0 実機（Pi Zero 2 W / Raspberry Pi OS Trixie）で全手順を通した結果に基づく。** 〔要確認〕は原則として解消済み。実機で確認していない項目のみ §9 末尾に明示する。
> - **物体の登録が2段階撮影になった（0.6.0・#184/#187）。** `1 · Capture empty scene`（物体をフレーム外にして空の視野を撮る）→ `2 · Capture access object`（物体をかざして撮る）の順。**この2枚の差分が物体の領域を決め、その領域だけが特徴として登録される。** 従来は視野全体を登録していたため、三脚固定の背景そのものが鍵になり、**物体を隠しても開いてしまっていた**。加えて **保存の瞬間にも物体の一致が再確認される** — 撮影後に物体を下ろして `Protect file` を押すと拒否される（→ §0・SCENE 3）。
> - **物体なし→拒否を WebUI Retrieve に移した。** 0.6.0 実機で WebUI 経路でも拒否されることを確認済み。**これで成功と失敗が同じ画面で連続する** — 物体の有無だけを変えた対比を画面切替なしで見せられるため、cue≠key の実証としては従来より強い（→ SCENE 6・7）。TUI の `Recover File` は**フォールバックとして残す**（→ §5）。
> - **破壊はパスワードで制御する（#191）。** Step 3・4 と**同じ Retrieve 画面の同じ入力欄**に、アクセスパスワードではなく**破壊パスワード**を入れると、**かざしている物体の Face が消える**。画面は何も変わらず、応答は打ち間違えたときと**完全に同じ** `No valid entry found.`。もう一方の Face は無傷。**「パスワードを強要されても守る」を、追加の操作なしで実演できる。** 確認も成功表示も無いのは設計上の代償で、成否は「その Face がもう開かないこと」でしか分からない（→ SCENE 9・10）。
> - **明示的な破壊経路も残してある（#189）。** 従来この操作は `phasmid emergency destroy-face` だけにあり、**このツールが存在する理由そのものである「強要されてもデータは守る」シナリオだけがブラウザから落ちてターミナルに残っていた**。Retrieve 画面の「Clear this entry instead of opening it」から、**かざした物体のエントリ**を、その**破壊パスワード**と確認語 `DESTROY FACE` で消せる。消す対象を画面で選ばせないのは意図的 — 選択肢を出すこと自体が「2つある」ことを漏らすため。落ち着いた状況で意図的に片付けるための監査可能な手段で、**壇上では使わない**（画面が変わると対比が弱まる）。実機検証で不具合が出て修正済み（#190・#192）— 詳細は §9.0.2。
> - **Issue #169・Phase 1:** TUI の **Add File** と Expert 画面の **Doctor・Inspect を非活性化**した — いずれも役割別トークンで保護された WebUI（`/store`、`/operator/doctor`、`/operator/inspect`）と完全に重複するため。**Recover File と Audit はあえて非活性化していない** — Audit は本改訂で壇上の演目からは外れたが、**卓上デモと質疑で使う**（→ §4「実演から外したもの」）。Recover File は否定証明が WebUI に移って本編からは外れたが、**壇上で WebUI が使えなくなった場合に否定証明を成立させる唯一の代替経路**なので残す。**削除ではなく非活性化** — 内部のサービス呼び出し・画面コードはそのまま残しており、リハーサルで問題が出れば1行で復元できる。
> - **Expert フッタの安全端末幅が 145→124 桁に下がった**（Doctor/Inspect の非活性化でフッタの項目数が減ったため。Audit は残っているので115桁までは下がらない）。
> - **囮ファイルは運用者が用意する**ものとし、生成機能は空き領域の填充に位置づけ直している（v4 からの変更点、引き続き有効）。
> - **本番構成を 12 シーンに組み直した（本改訂）。** 変更は4点。**(1) SCENE 1 で作った容器をディスク上の実物として見せる** — `ls` / `file` / `od` の3行。以降は必ずファイル名で参照する。これが無いと、2つのファイルが出てきても観客には「別々の入れ物から出た」としか見えず、デモの主張が丸ごと伝わらない。**(2) 対比を両方向にした** — 物体だけ違う（SCENE 6）と、パスワードだけ違う（SCENE 7）の両方を見せる。**(3) 強要と破壊を独立したシーンにした**（SCENE 8・9・10）。**(4) Silent Standby と Audit を実演から外した** — 理由は §0 の表と §4 の各注記に書いた。
> - **画面切替が往復から片道1回になった。** TUI に戻るシーンが無くなったため。ラップトップ1台で「スライド／ターミナル／ブラウザ」を切り替える構成なら、フルスクリーンのスペースを順送りするだけで済む（→ §2）。

---

## 0. 本番でやってはいけないこと（先に読む）

鍛錬中に実際に踏んだものだけを挙げる。

| やってはいけない | 理由 | 代わりに |
|---|---|---|
| **マウスでボタンを押す** | SSH越しのターミナルではクリックイベントがTextualに届かない。ボタンはフォーカスされるだけで発火しない | **`Tab` / `Shift+Tab` で移動し `Enter`**。全操作をキーボードで行う |
| **壇上で Fill Free Space を実行** | 64 MiB / 15% で**実測約4分**。枠は1:20 | **事前に埋めておき**、壇上では **Inspect Free Space** のみ |
| **囮ファイルをツールに作らせる** | 生成される填充物は汎用ファイルであり、開示材料としての真実味がない | **囮は運用者が用意する。** 真のファイルによく似た偽ファイルを自分で保存する |
| **素の `phasmid` で起動** | libcamera のログがTUIを破壊する／WebUIがラップトップから見えない／トークンが毎回変わる／`Ctrl+S` が効かないことがある | **`scripts/pi_zero2w/run_demo_console.sh`** を使う |
| **成功例だけを見せる** | 物体キューが効いていることの証明にならない。観客にはただのパスワード復号に見える | **失敗を両方向で見せる**（SCENE 6・7） |
| **TUI で Add File を探す** | #169 で非活性化済み。Operation セレクタには Recover File・List Files・Remove File しか出ない | **Bind も復元も否定証明も WebUI**（SCENE 3〜10）。TUI の `Recover File` は WebUI が使えない時の代替 |
| **Silent Standby を壇上で見せる** | 「WebUI ごと落ちる」と言っても、ブラウザ側には痕跡が残る。**実装が主張に追いついていないものを壇上に出すと、質疑で崩れる** | **演目から外す。** 概念は Slide 14 で説明済み。実装が固まるまで、実演は卓上デモに留める |
| **Audit を壇上で開く** | 上段で `Header absent / Magic bytes absent` と言いながら、下段で `Tracked Faces 2` と数える。**その数字の出どころは容器ではなく手元の台帳**で、SCENE 1 で16進ダンプまで見せた直後にこれを出すと、自分で作った印象を自分で崩す | **演目から外し、SCENE 10 の最後の3行で「判定しないこと」だけを言う。** 画面は卓上デモと質疑の持ち札に回す（→ §5） |
| **別タブに recover トークンのセッションを並べる** | **同一ブラウザでは成立しない。** セッションはクッキー1つ（`phasmid_ui_session`）で全タブ共有なので、2つ目のタブで解錠すると1つ目のセッションも置き換わる | **役割分離は SCENE 2 で口頭説明のみ。** 実演したいならプライベートウィンドウか別ブラウザが要るが、壇上でやる価値はない |
| **ダウンロードフォルダを空にせずに始める** | 復元ファイル名は Face によらず `retrieved_payload.bin`。2つ目が `retrieved_payload(1).bin` になり、**SCENE 6 の「違うファイルが出た」が名前の違いに見えてしまう** | **事前に空にする。** 違いは必ず**中身**で見せる |
| **通知を切らずに投影する** | ラップトップ1台構成では、Slack もメールもカレンダーも投影画面に出る | **集中モードをオンにする。** スペースを3つに固定し、デスクトップと Dock を映さない |
| **物体を撮ってから下ろして `Protect file`** | 0.6.0 から**保存の瞬間にも一致を再確認する**（#186）。下ろすと `That entry is already set up...` で拒否される | **撮影から保存まで物体をかざし続ける。** 押す前にオーバーレイが `MATCH` になっていることを確認 |
| **物体をかざしたまま `Capture empty scene`** | 空の視野に物体が写り込むと、差分が物体を切り出せない | **1枚目は必ず物体をフレーム外に。** 順序は空シーン→物体（#184） |

---

## 1. 制約と時間予算 / Constraints & budget（合計 ~8:30）

| # | シーン | 目安 | 画面 | 役割 |
|---|---|---|---|---|
| 0 | The console | 0:20 | TUI Simple | TUIホーム提示 |
| 1 | **One file on disk** | 1:10 | TUI Simple + シェル | Prepare。**「1つの容器」を焼き付ける** |
| ⟶ | **画面切替（片道1回・以降 TUI に戻らない）** | — | — | — |
| 2 | Into the browser | 0:50 | **WebUI**（store トークン） | ログイン＋役割分離の口頭説明 |
| 3 | Slot A — the file you would hand over | 0:50 | **WebUI** | Bind。**cue≠key の説明はここ** |
| 4 | Slot B — the file you would not | 1:00 | **WebUI** | Bind。破壊パスワードもここで設定 |
| 5 | Slot A opens | 0:20 | **WebUI** | 機能確認のみ。意味づけは SCENE 8 |
| 6 | **The object alone is not enough** | 1:00 | **WebUI**（同じ画面） | **★★Slot A / Slot B の実証** |
| 7 | **The password alone is not enough either** | 0:40 | **WebUI**（同じ画面） | **★★cue≠key の実証** |
| 8 | Coercion — hand over Slot A | 0:30 | **WebUI**（同じ画面） | SCENE 5 と同一操作。意味だけが違う |
| 9 | **The other password** | 0:50 | **WebUI**（同じ画面） | **★山場。不可逆** |
| 10 | Nothing left to open | 0:50 | **WebUI**（同じ画面） | 破壊の確認＋**主張しないことの明示** |
| 11 | ラップ | 0:10 | **WebUI** | 締め |

> **時計運用:** 開始 ~19:20。**26:00 を超えたら SCENE 5 と SCENE 8 を落とす** — 落とす順はこの2つ。SCENE 5 は機能確認、SCENE 8 は SCENE 5 と同一操作なので、片方だけ残せば筋は通る。**SCENE 1・6・7・9・10 は何があっても残す。**
> **画面切替は片道1回だけ。** SCENE 1 の終わりに TUI→ブラウザへ移り、**そのまま最後まで戻らない**。SCENE 2〜11 は同じブラウザ画面で連続する。
> **SCENE 1 が全体の前提を作る。** ここでディスク上の実物（`ls` / `file` / `od`）を見せ、以降ファイル名で参照し続けることで初めて「**1つの容器から**2つ出た」が成立する。これを飛ばすと、以降のシーンが全部「別々の入れ物を順に開いただけ」に見える。
> **SCENE 6 と 7 は対になっている。** 6 は物体だけを変えて失敗させ、7 はパスワードだけを変えて失敗させる。**片方だけでは「物体が鍵だ」とも「パスワードが鍵だ」とも取れてしまう。** 両方向を見せて初めて「両方が要る／どちらも鍵ではない」が実証になる。
> **SCENE 9 が山場。** 同じ画面・同じ物体・同じ入力欄・同じボタンで、**打ち間違えたときと文字通り同じ表示**が出る。外から区別がつかないこと自体が主張なので、ここは手を速く動かさない。

---

## 2. 事前準備チェックリスト / Pre-flight

### T-30分（設営時）

- [ ] 実機（Pi Zero 2 W + カメラ + 三脚）を卓上に設置、電源・給電確認。
- [ ] 表示系: **ラップトップ1台をプロジェクタに繋ぎ、その中で3つのスペースを切り替える。**
      左から「スライド」「ターミナル（TUI への ssh）」「ブラウザ（WebUI）」の順に
      **フルスクリーンのスペースを3つ固定**し、`Ctrl+←→` だけで移動する。
      こうするとデスクトップも Dock も一度も映らない。**切り替えるのは SCENE 1→2 の
      片道1回だけで、TUI には戻らない**（ラップの後にスライドへ戻る1回を除く）。
- [ ] **集中モード（おやすみモード）をオンにする。** 1台構成では Slack もメールも
      カレンダーも投影画面に出る。物理切替構成には無かったリスクなので、明示的に潰す。
- [ ] **ブラウザのダウンロードフォルダを空にする。** 復元ファイル名は Face によらず
      `retrieved_payload.bin` で、2つ目は `retrieved_payload(1).bin` になる。
      **SCENE 6 の「違うファイルが出た」が名前の違いに見えてしまう**ため、
      違いは必ず中身で見せる。空にしておけば混乱しない。
- [ ] **SCENE 1 で叩くコマンドが実機にあることを確認する。** 実機は Raspberry Pi OS Lite で、
      **`xxd` は入っていない**（旧 `vim-common`／現 `xxd` パッケージが無い）。壇上で
      `command not found` を出さないため、設営時に一度通す:

      ```bash
      for c in ls file od; do command -v $c || echo "MISSING: $c"; done
      ```

      `od` は coreutils なので必ずある。**デバイスに何かを追加インストールして解決しない** —
      ネットワークに出さない前提そのものを崩す。
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
      **どちらも SCENE 3・4 で WebUI から保存する** — TUI の `Add File` は #169 で
      非活性化済みなので使わない（`Recover File` は §5 のフォールバック用に残してある）。
- [ ] 用意するパスフレーズは3つ: 真の復号用・真の破壊用・偽の復号用。
      **真の破壊用は Store 画面の「Advanced security options」→「Restricted recovery
      password」で設定する。** ここを空にしたまま進めると SCENE 9 が実演できない。
- [ ] （任意）**Fill Free Space を事前実行**（約4分）。空き領域を埋め、
      容器が不自然に空でないようにする。経過時間が表示され画面は固まらない。
- [ ] ラップトップのブラウザで `http://10.12.194.1:8000/unlock` を開き、
      **store トークン**（既定 `phasmid-demo-store-token`）で **Home まで進めた
      タブを1つだけ**用意してブックマーク。
      ※ `phasmid-pi.local` は使わない。**IPアドレス直指定**。
      ※ **recover トークンのタブは用意しない。** セッションはクッキー1つ
      （`phasmid_ui_session`）で全タブ共有なので、2つ目のタブで解錠すると1つ目の
      セッションも置き換わる。**同一ブラウザで2つの役割を並べることはできない。**
      役割分離は SCENE 2 で口頭説明するに留める。
- [ ] **バックアップ録画**（全手順を通した2〜3分クリップ）を再生機に用意し**頭出し**。
- [ ] 予備電源／ケーブル。会場ネットワークは不要（WebUIはUSBガジェット面のみ）。
- [ ] **物体キューのリハーサルを1回通す**（所要 約2分）。本番と同じ三脚位置・照明で:
      1. `1 · Capture empty scene` → `2 · Capture access object` が**1回で通ること**
      2. 物体を下ろして `Protect file` → **拒否されること**（`That entry is already set up...`）
      3. 物体をかざし直して `Protect file` → 保存できること
      4. Retrieve で**物体を隠して**正しいパスワード → **拒否されること**
      5. 物体を戻して同じパスワード → 復元できること
      6. （SCENE 9 のために）**別の使い捨て Vessel で**破壊まで通す — 本番用の
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
- [ ] **リハーサルの復元失敗は TUI の `Recover File` で行うこと。** WebUI の `/retrieve` は
      物体なしの拒否も失敗として記録し、**5回で60秒ロック**する
      （`PHASMID_ACCESS_MAX_FAILURES=5` / `PHASMID_ACCESS_LOCKOUT_SECONDS=60`）。
      直前のリハーサルで使い切ると本番の SCENE 6 が `Access temporarily unavailable.`
      で止まる。TUI 経路は失敗を記録しないので何度でも試せる。
      **本番の失敗は SCENE 6・7・10 の3回だが、間に成功が挟まるたびカウンタが 0 に戻る**
      ため、実際のピークは1回で余裕がある（→ §9.0.6）。
- [ ] Silent Standby は **`Ctrl+S`**（既定）。復帰は **`Ctrl+R`** または **`Esc`**。
      **フッタに出ないので指で覚えておく。演目には含めないが、誤爆した場合の復帰に要る。**
- [ ] **`w` は押さない。** 役割トークンを起動スクリプトで固定しているので、`w` が表示する
      旧来の共有トークンは `/unlock` に受理されない。押す用がないうえ、**1画面構成では
      表示されたトークンを投影から逃がせない**。WebUI は起動スクリプトが既に上げている。

---

## 3. 初期状態 & リセット / Initial state & reset

- **初期状態:** Simple Operator 画面。Vessels は空（`No protected storage found.`）。
- **SCENE 1 で作る Vessel はそのまま最後まで使う。** 物体キューは Vessel 新規作成時に
  自動でクリーンな状態から始まるので、以前のように `rm .state/store.bin .state/lock.bin`
  を手動で行う必要はない。
- **各サイクル後リセット:** §8 を実施。

---

## 4. 実施手順 / Scene-by-scene

> 表記: **キー** = キー押下。**すべてキーボード操作。マウスは使わない。**
> Select（ドロップダウン）は、フォーカスして `Enter` で開き、`↓` で選び `Enter` で確定。
> 発話は英文1行＝1息。**カタカナ付きの読み上げ台本は Word 版（`Phasmid_Demo_RunOfShow.docx`）にある。**

### SCENE 0 — The console（0:20｜TUI Simple）

- **操作:** Simple Operator 画面を提示。下部のバー（`o Open · n New · g Guided · e Expert`）を指す。まだ何も操作しない。
- **画面期待:** `PROTECTED STORAGE` は空（`No protected storage found.`）。
- **発話（EN）:** "This is the real console. Local Disclosure Control. The home screen is deliberately small. Open. New. Guided. Expert. Under pressure, you do not want a wall of options. The full control set is one key away."

### SCENE 1 — One file on disk（1:10｜Prepare｜TUI Simple + シェル）

> **このシーンが全体の前提を作る。** ここでディスク上の実物を見せ、以降ファイル名で参照し
> 続けることで初めて「**1つの容器から**2つ出た」が成立する。飛ばすと、以降のシーンが全部
> 「別々の入れ物を順に開いただけ」に見える。**削ってはいけない。**

- **操作:** **`n` (New)** → `vessel-path` に `demo.vessel` → **`vessel-size` を `64M` に変更**（Select、既定は `512M`。**既定のまま作らない**）→ `vessel-label`（"Non-sensitive label"、任意）→ `create-btn`。
  続けてシェルに切り替え、実物を見せる:
  ```bash
  ls -lh demo.vessel                    # 1つのファイル、64M
  file demo.vessel                      # "data" — 何も分からない
  od -A x -t x1z -N 96 demo.vessel      # 6行だけ出る
  ```
- **画面期待:** `PROTECTED STORAGE` に新規 Vessel が出現。**下段のパネルが `Choose an action:` に変わること**（空状態メッセージが消える）。`file` は `data` を返す。
- **発話（EN）:** "First, I make a vessel. A deniable container. One file. Sixty-four megabytes. Let me show you what that looks like on disk. `ls` — one file. That is all there is. `file` — it says 'data'. It has nothing to say, because there is nothing to read. No header. No magic bytes. No format at all. On disk, this is random. Remember the name. Demo dot vessel. Everything from here comes out of this one file."
- **注意:** Vessel を作ると **Face が2つ自動生成される**（`face_a` / `face_b`、ともに `available`）。物体キューも自動でクリーンな状態から始まる（0.4.0）。**Create Face を押す必要はない。手順に含めない。**
- **注意（`xxd` ではなく `od`）:** **`xxd` は実機に入っていない。** Raspberry Pi OS Lite は
  `xxd` パッケージ（旧 `vim-common`）を含まないので、壇上で `command not found` になる。
  **`od` は coreutils なので必ずある。** `-A x` で16進オフセット、`-t x1z` で
  16進＋右端に ASCII、`-N 96` で96バイト＝6行に切る — `head` へのパイプも要らない。
  実機で踏んだ（→ §9.0.6）。
- **注意（副産物）:** この16進ダンプは Slide 6 の「ヘッダも magic bytes も無い」を**実物で裏付ける**。旧構成にはこの裏付けが無く、主張がスライドの中だけで完結していた。

### ⟶ 画面切替（片道1回・以降 TUI に戻らない）

- **操作:** スペースをターミナルからブラウザへ（`Ctrl+→`）。**これ以降 TUI には戻らない。**
- **注意:** ラップの後にスライドへ戻る1回を除き、切替はこれだけ。旧構成の往復が無くなったので、入力切替の事故そのものが起こらない。

### SCENE 2 — Into the browser（0:50｜WebUI）

- **操作:** ブックマークした `/unlock` タブで **store トークン**を入力してログイン。トークンの役割分離は**口頭のみ**で説明する。
- **画面期待:** Home。ナビは `Home / Store / Retrieve / Maintenance / Diagnostics / Audit / Workflows / Inspect / Lock`。
- **発話（EN）:** "The device also serves a local web interface. I am logging in now. One word about these tokens, because it matters. In real use, you issue two of them. A full-control token — used once, somewhere safe, to set things up. And a recovery token, that can decrypt and nothing else. That is the one you carry into a bad situation. It cannot reach setup, so it cannot give setup away. Today I use one token, for time. Just know the split is there."
- **注意（実演しない理由）:** 旧構成には「別タブで recover トークンのセッションを提示し、ナビに `Store` / `Maintenance` が無いことを指す」という手順があった。**これは同一ブラウザでは成立しない。** ナビの出し分け自体は実装されている（`base.html` の `{% if store_role %}`）が、セッションはクッキー1つ（`phasmid_ui_session`）で全タブ共有なので、**2つ目のタブで解錠すると1つ目のセッションも置き換わる**。プライベートウィンドウか別ブラウザが要る。壇上でやる価値はないので口頭説明に落とした。

### SCENE 3 — Slot A: the file you would hand over（0:50｜★BIND｜WebUI）

> **重要（#169・TUI の Add File は非活性化済み）:** TUI の Operation セレクタには
> **Recover File・List Files・Remove File しか出ない。** Face の登録は **WebUI の Store 画面**で行う。

- **操作:** **Store** 画面 → Step 1「Choose the slot」で **Slot A** を選択 → **偽装用ファイル**を選択 → **パスワードA** → **物体を手元に置いたまま `1 · Capture empty scene`** → **物体Aをかざして `2 · Capture access object`** → **かざしたまま `Protect file`**。
- **画面期待:** 1枚目で `Empty scene captured. Now hold the object in front of it.`、2枚目で `Object cue matched`。`Access object: Captured` に変わり、カメラプレビューのオーバーレイが `No object cue match` から一致表示に変わる。`Protect file` 成功で緑のトースト。
- **発話（EN）:** "Slot A. This is the file I would hand over. Now watch the camera. It takes two shots. First, the empty scene. Just my table. Then the same view, with the object in it. The device keeps the difference between them. Not my table. Not the room. The object. And this is a cue, not a key. It does not encrypt anything. It decides whether the operation may start at all. A photograph of it opens nothing."
- **注意:** **撮影から保存まで物体を下ろさない。** 0.6.0 から保存の瞬間にも一致が再確認される（#186）。下ろすと `That entry is already set up...` で拒否される。
- **注意:** **1枚目は必ず物体をフレーム外に。** 空の視野に物体が写り込むと差分が物体を切り出せない（#184）。

### SCENE 4 — Slot B: the file you would not（1:00｜★BIND｜WebUI）

- **操作:** Step 1 を **Slot B** に切り替え → **真のファイル**を選択 → **パスワードB** → **Advanced security options** で **Clearing password（破壊用）** を設定 → **物体を外して `1 · Capture empty scene`** → **物体Bをかざして `2 · Capture access object`** → **かざしたまま `Protect file`**。
- **画面期待:** スロットを切り替えるたびに `Access object: Not captured` にリセットされ、**空シーンの撮り直しからやり直しになる**（前の空シーンは使い回されない）。
- **発話（EN）:** "Slot B. Same file on disk. Same demo dot vessel. A different object. A different password. And one more thing here, which I will use later. A second password for this slot. Not one that opens it. Both slots now live inside that one file."
- **注意:** **スロットを切り替えたら必ず物体も差し替える。** 同じ物体を両方の Face に使おうとすると `Object binding failed` で拒否される（cue≠key を壊さないための安全装置。実機で確認済み）。
- **注意:** ここで Clearing password を設定し忘れると **SCENE 9 が実演できない**。設定したことを口に出して言うのは意図的で、SCENE 9 の伏線になる。

### SCENE 5 — Slot A opens（0:20｜WebUI）

- **操作:** **Retrieve** 画面 → **物体A**をかざす → 一致表示を待つ → **パスワードA** → `Open protected file` → 落ちてきたファイルを開いて中身を見せる。
- **画面期待:** 緑のトーストで復元成功。
- **発話（EN）:** "Object A. Password A. And there it is. That is Slot A, out of demo dot vessel."
- **注意:** **ここでは意味づけをしない。** 同じ操作に意味を与えるのは SCENE 8。先に「ただ動く」ところを見せておくから、あとで効く。**時計が押しているならこのシーンを落とす**（SCENE 8 が同一操作なので筋は通る）。
- **注意:** **画面はこのまま。** SCENE 6〜10 はすべてこの Retrieve 画面で行う。切り替えないことが「他は何も変えていない」ことの担保になる。

### SCENE 6 — The object alone is not enough（1:00｜★★Slot A / Slot B の実証｜WebUI・同じ画面）

- **操作:** **同じ Retrieve 画面のまま**、**物体Bに持ち替える** → **一致表示を待つ**（待たずに押すと拒否される）→ まず**パスワードA** → `Open protected file` → **失敗** → 続けて**パスワードB** → `Open protected file` → **成功** → 落ちてきたファイルを開き、SCENE 5 と中身が違うことを見せる。
- **画面期待:** 1回目は `No valid entry found.`。2回目は別のファイルが復元される。**ファイル名は両方とも `retrieved_payload.bin`**（どの Face が開いたかを漏らさないための設計）なので、**名前ではなく中身で違いを見せる**。
- **発話（EN）:** "Same screen. I have only changed the object. This is the object for Slot B. And I will type Slot A's password. No valid entry found. The object is right. The password is not. Nothing opens. Now Slot B's own password. A different file — out of the same file on disk. One vessel. Two objects. Two passwords. Two files."
- **注意:** **物体を持ち替えたら一致表示を待ってから押す。** `/retrieve` は入力パスワードと撮影した cue で全 Face を順に試すので、追加実装は不要。
- **注意:** 1回目の失敗は**意図的に見せる失敗**である。ここを飛ばして成功だけ見せると、観客には「物体が鍵だ」と読まれてしまう。

### SCENE 7 — The password alone is not enough either（0:40｜★★cue≠key の実証｜WebUI・同じ画面）

- **操作:** **同じ画面のまま**、**物体Aに持ち替える**（あるいはカメラの視野から完全に外す — 手で覆うのではなく卓の下に下ろす）→ オーバーレイが変わるのを待つ → **パスワードB** → `Open protected file` → **失敗**。
- **画面期待:** **`No valid entry found.`** のエラートースト。ファイルは出てこない。物体を外した場合はオーバーレイが `No object cue match` / `Present a bound object to continue`、**`/status` の `object_state` は `none`**。
- **発話（EN）:** "Now the other way around. I keep Slot B's password. I change the object back to A. Same result. No valid entry found. Not 'wrong object'. Not 'object missing'. It will not tell you what it is waiting for. That is what 'the cue gates the operation' means."
- **注意:** **ここで間を取る。** SCENE 6 と 7 は対になっていて、**片方だけでは「物体が鍵だ」とも「パスワードが鍵だ」とも取れてしまう。** 両方向を見せて初めて「両方が要る／どちらも鍵ではない」が実証になる。
- **技術的裏付け（質問された場合）:** `collect_auth_sequence()` が `wait_for_reference_match(timeout=10.0)` を呼び、不一致なら `match_none` を返す。この値は復号の入力そのもの（`_read_face_namespace` に渡る）なので、**照合を迂回して復元することはできない。** 0.6.0 では加えて、参照テンプレート自体が**空シーンとの差分領域からのみ**作られる。

### SCENE 8 — Coercion: hand over Slot A（0:30｜WebUI・同じ画面）

- **操作:** **物体A** → **パスワードA** → `Open protected file`。**SCENE 5 とまったく同じ操作。** 手を速く動かさない。語りで見せるシーン。
- **画面期待:** SCENE 5 と同じ。緑のトースト、Slot A のファイル。
- **発話（EN）:** "Now change the situation. Someone has the device. And they have me. 'Give us the password.' So I do. Object A. Password A. They get a file. A real file, that really opens. Nothing on this screen says there is another one. That is the whole design."
- **注意:** **操作が SCENE 5 と同一であること自体が主張である。** 同じ操作が、状況によって「動作確認」にも「強要への応答」にもなる。外から見て区別がつかないことが設計の目的なので、そこを言葉で名指しする。
- **注意:** 時計が押しているなら SCENE 5 を落としてこちらを残す。逆にしない — 意味づけのないシーンだけが残ることになる。

### SCENE 9 — The other password（0:50｜★山場｜WebUI・同じ画面｜**不可逆**）

- **操作:** **同じ Retrieve 画面。消したい Face の物体（物体B）をかざす** → パスワード欄に、そのアクセスパスワードではなく **Clearing password** を入力 → `Open protected file`。
- **画面期待:** **`No valid entry found.`** — パスワードを打ち間違えたときと**完全に同じ表示**。ファイルは出てこない。**これが正しい挙動。**
- **発話（EN）:** "Worse case. They already know there is more. Same screen. Same object. Same field. Same button. The only thing I change is which password I type. And it says — no valid entry found. That is the same sentence you get from a typo. But that entry is not locked. It is gone. The password they can compel is not the only one there is."
- **注意（消えるのは「かざした Face」）:** 対象は画面の選択肢ではなく**カメラの物体**で決まる。**Slot B を消すには物体B を出す必要がある** — 強要下では「真の物体を出すこと自体が情報になる」という設計上の論点があり、質問されたら**隠さずそう答える**。他方の Face の物体をかざした状態で破壊パスワードを入れても、**何も起きない**。
- **注意（資格の分離）:** アクセスパスワードでは破壊できず、破壊パスワードでは開けない。
- **注意（ロックアウトの心配は無い）:** この操作は**失敗としてカウントされない**（`_destroyed_by_password` が成功したとき `record_success`）。→ §9.0.6。

### SCENE 10 — Nothing left to open（0:50｜WebUI・同じ画面）

- **操作:** **物体B** → **パスワードB（正規のもの）** → `Open protected file` → 何も出てこない。続けて **物体A** → **パスワードA** → `Open protected file` → 開く（時計が押していれば口頭のみ）。
  **最後の3行は操作なし。手を止めて、客席を見て言う。**
- **画面期待:** Slot B は `No valid entry found.`。Slot A は従来どおり復元される。
- **発話（EN）:** "Let me prove that. Object B. Slot B's real password. The correct way. Nothing. I cannot get it back either. That is not a bug. And Slot A still opens, exactly as before. — One thing this tool will never tell you: whether your cover story is believable. That is your job. It does not pretend otherwise."
- **注意（最後の3行が Audit ビートの代わり）:** 旧構成にはここで TUI の Audit 画面を開き「判定しないことを誇る」ステップがあった。**画面は出さず、この3行に置き換えた。** 理由は2つ。**(1) 置き場所がない** — SCENE 9〜10 の破壊が感情のピークで、その後に監査画面を出すと温度が下がったところで終わる。前に置けば積み上げた緊張を切る。**(2) 画面が自己矛盾する** — Audit は上段で `Header absent / Magic bytes absent / Metadata minimized` と言いながら、下段で `Tracked Vessels 1 / Tracked Faces 2` と数える。その数字は容器ではなく**手元の台帳**（`VesselService().list_all()`）から来ているので、SCENE 1 で16進ダンプまで見せた直後にこれを出すと、自分で作った印象を自分で崩す。**破壊を見せた直後に、作った本人が先に限界を言う方が効く。**
- **注意（この失敗はカウントされる）:** 破壊済みの Face を正規のパスワードで開こうとすると `_destroyed_by_password` は False を返し、**失敗として記録される**。ただし直前の SCENE 8 の成功でカウンタは 0 に戻っているので、ここで 1 になるだけ（→ §9.0.6）。

### SCENE 11 — ラップ（0:10）

- **発話（EN）:** "One file. Two objects. Two passwords. And a password that ends one, instead of opening it. On real hardware. Come and try it at the table."
- **操作:** スペースをスライドへ戻す（Slide 25）。
- **注意:** 旧構成の締めは "That's Prepare, Bind, Operate, Disclose — on real hardware." だった。**Disclose（Silent Standby）を実演しなくなったので、言わない。** 実演していないものを実演したことにする一文は、質疑で最初に突かれる。

---

### 実演から外したもの / Cut from the live demo

| 旧 Step | 扱い | 理由 |
|---|---|---|
| Step 5 — Audit | **卓上デモと質疑の持ち札に回す** | 上記 SCENE 10 の注記。「空の容器は空に見えてしまうのでは？」は必ず出る質問なので、聞かれたらブラウザのナビから `/operator/audit` をワンクリックで開いて `Free Space Filler` を見せる。**1対1なら台帳の話も落ち着いて説明でき、そこでの説明はむしろ誠実さの証明になる。** 壇上で200人に出す画面ではなく、机で1人に見せる画面。 |
| Step 6 — Silent Standby | **演目から外す** | 「WebUI ごと落ちる」と言っても、**ブラウザ側には痕跡が残る**。実装が主張に追いついていない。TUI 側の Standby 画面も同様に詰めきれていない。実機で動作自体は確認済み（→ §9.0.6）だが、**主張を支えきれないものを壇上に出すと質疑で崩れる**。概念説明は Slide 14 に残す。実装が固まったら卓上デモから戻す。 |

---

## 5. フォールバック方針 / Fallbacks

- **個別シーン:** **止まらず前進**（最大15秒で見切り）。
- **全体（実機不調）:** 章扉（Slide 23）で頭出しした**録画に即切替**。
  "The design points stand either way." と明言し、口頭で「1つの容器・2つの物体・2つのパスワード・
  そして開くのではなく終わらせるパスワード」を辿る。
- **認識不安定:** 起動スクリプトの既定が `demo` モード。それでも不安定なら
  `coercion_safe` の低信頼→ダミー経路を**設計意図として逆手に説明**。
- **WebUI がラップトップから見えない、または不安定:** `PHASMID_WEBUI_EXPOSE_GADGET=1` が
  効いているか、URLが **`10.12.194.1:8000`（IP直指定）** かを確認。`127.0.0.1` と
  `phasmid-pi.local` はラップトップからは**到達しない**。
  **SCENE 3〜6（Bind・復元成功）を口頭要約に切り替え、SCENE 7 は TUI の `Recover File` で
  実施する** — **物体だけを外した拒否は省略してはならない**（→ 下の項）。SCENE 0・1・11 は
  WebUI に依存しないのでそのまま実機で続行。**SCENE 8〜10（強要と破壊）は WebUI 専用なので、
  この場合は口頭説明に落とす。**
- **物体なし拒否の代替経路（WebUI が使えない場合）:** TUI で **`o`（Open）** → `Y` →
  Operation **`Recover File`**（#169 で非活性化していないのはこのため） →
  **Output file** にパス → Face 1 と同じ **Passphrase** → **物体は視野の外** →
  `Run Operation`。約10秒後、赤で **`Open Vessel / no bound object matched`**。
  WebUI 版と違い**失敗を記録しないのでロックしない**。0.4.0 実機で検証済み。
- **`Access temporarily unavailable.` が出た（WebUI ロックアウト）:** 直前の
  リハーサルで失敗を5回使い切っている。**60秒待てば解除される**（ロック消化後に
  カウンタも 0 に戻る — #190 で修正済み）。待てない場合は上の TUI 代替経路に切り替える。
- **時間超過:** 26:00 到達で **SCENE 5 と SCENE 8 を落とす**。それでも足りなければ
  SCENE 2 のトークン説明を1文に縮める。**SCENE 1・6・7・9・10 は何があっても見せる** —
  この5つが揃わないと、観客に残るのは「パスワードでファイルが出た」だけになる。
- **質問されたときの持ち札:** 「空の容器は空に見えてしまうのでは？」には、ブラウザのナビから
  **`/operator/audit`** を開いて `Free Space Filler` を見せる。壇上では出さないが、
  卓上デモと質疑では有効な画面（→ §4「実演から外したもの」）。

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
- **実地では TUI を強要下で開かない。** 卓上デモや質疑で Audit を見せるのは、そこで
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
- [ ] WebUIプロセス停止（`w`、またはinactivity auto-kill 30分待機）。
- [ ] ブラウザタブ（store の1つだけ）を `/unlock` 済みの状態に戻す。
- [ ] カメラ画角・三脚位置を再固定。

---

## 9. 実機で確認済みの挙動 / Verified on device

以下は実機で実際に確認した。設計からの推測ではない。物体キュー関連は **0.6.0**
（2026-07-30、Pi Zero 2 W / picamera2 / 320×240 @ 4fps）、それ以外は 0.4.0。

> **本節の `Step N` は、改訂前の番号のまま残してある。** 検証時点の記録であり、
> 後から番号を振り直すと「そのとき何を試したか」が読めなくなるため。現行の
> シーン番号との対応はおおむね次のとおり — Step 2 → SCENE 3・4、Step 3 → SCENE 5、
> Step 3b → SCENE 6、Step 4 → SCENE 7、Step 4b → SCENE 9、Step 5 → 演目外、
> Step 6 → 演目外。

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

- **否定証明を WebUI に移せる。** WebUI 経路でも拒否が成立する。**成功と失敗が同じ画面で
  連続する**ので、対比の担保が「画面が切り替わらないこと」で取れる（→ SCENE 6・7）。
- **Bind は 1:00 前後に収まる。** 撮影が2回に増えたが、1回で通れば所要は従来と同等。
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

### 9.0.5 WebUI が固まったとき

実機で踏んだ。**Step 4b で破壊 → 正規パスワードで開かないことを確認 → Home を押す**
で、画面がスピナーのまま返らなくなった。**コンソールの再起動は不要**で、
**ブラウザのタブを閉じて開き直せば戻る**（カメラ配信の接続とステータス取得が両方切れる）。

原因は WebUI 側で、**重い処理がイベントループ上で走っていた**こと。Argon2id の
鍵導出・コンテナの上書き・カメラ待ちが全部 `async def` の中にあり、その数秒間は
`/status` も `/video_feed` も Home も返せない。しかも「破壊済みの Face に正規
パスワード」は**アプリ中で最も重い経路**（全 mode の Argon2id が走って失敗し、
そのあと破壊パスワード判定がもう一度走る）。そこへステータス取得が 1.2 秒ごとに
前の結果を待たずに積み上がり、カメラ配信が接続を1本占有しているため、ブラウザの
同時接続枠（6本）が埋まって**次の遷移がソケットを取れなくなる**。

**0.6.1 で修正済み** — 該当9ルートをスレッドプールへ移し、ステータス取得は
同時1本＋4秒でアボートするようにした。**修正版で再現しないことを実機で1回確認しておく。**

**画面構成**

| 画面 | フッタ |
|---|---|
| `SimpleHomeScreen`（起動時） | `o` Open · `n` New · `g` Guided · `e` Expert · `q` Quit · `w` WebUI |
| `HomeScreen`（`e` の後、#169適用後） | `Esc` Back · `o` · `x` · `delete` · `c` · `f` · `g` · `a` · `s` · `t` · `l` · `?` · `q` · `w` |

`d`（Doctor）と `i`（Inspect）は #169 でフッタから非活性化されたため、上表には
含まれない。`a`（Audit）はあえて残した — 壇上の演目からは外れたが、卓上デモと質疑で
使うため（→ §4「実演から外したもの」）。
`HomeScreen.check_action` が `False` を返すことでフッタから消えるが（LUKS 非活性時と
同じ仕組み）、対応する `action_doctor` / `action_inspect_vessel` メソッド自体は
変更しておらず、コマンドパレット経由では引き続き到達できる。

---

### 9.0.6 本番構成の実機確認（0.6.1・2026-08-07）

配備スクリプト（`scripts/pi_zero2w/deploy_to_device.sh`）で `main` を実機に入れた
状態で確認した。

| 確認項目 | 結果 |
|---|---|
| `run_demo_smoke_test.sh` | **11/11 PASS**（`exit=0`） |
| 9.0.5 の回帰 — 破壊 → 正規パスワードで開かない → **Home** | **固まらない。** 修正が効いている |
| 同上 — 復元処理中（Argon2id 実行中）のカメラプレビュー | **動き続ける。** 処理がスレッドプールに逃げている |
| 60秒ロックアウト（#190 の回帰） | **期待どおり。** 5回で入り、60秒で解除され、解除後にカウンタも 0 に戻る |
| Silent Standby の実描画 | **期待どおり。** 機微表示が消え、フッタから `w WebUI` も消える |
| ラップトップからガジェット経由の `/unlock` | **到達する**（上記の破壊シーケンスを Mac のブラウザで実施） |

**Silent Standby は動くが、演目には含めない。** 状態遷移も描画も期待どおりだが、
**ブラウザ側に痕跡が残るため「WebUI ごと落ちる」という主張を画面が支えきれない**。
実装が主張に追いつくまで壇上には出さない（→ §4「実演から外したもの」）。

**ロックアウトは本番構成でも余裕がある。** 本番で失敗として記録されるのは
SCENE 6（1回目のパスワード違い）・SCENE 7（物体違い）・SCENE 10（破壊済みを開く）の
3回だが、`record_success` が状態ごと破棄するため、**間に成功が挟まるたびカウンタが
0 に戻る**。実際のピークは 1。**破壊操作そのものは成功として記録される**
（`_destroyed_by_password` が成功したとき `record_success`）ので、SCENE 9 は
カウンタに影響しない。

**実機で踏んだもの:**

- **`xxd` が入っていない。** SCENE 1 の16進ダンプを `xxd` で書いていたが、Raspberry Pi OS
  Lite には `xxd` パッケージ（旧 `vim-common`）が無く、**壇上なら `command not found` に
  なっていた**。`od -A x -t x1z -N 96` に差し替えた — `od` は coreutils なので必ずある。
  **デバイスに追加インストールして解決しない** — ネットワークに出さない前提そのものを崩す。
  同種の事故を防ぐため、設営時にコマンドの存在を確認する項目を §2 に追加した。

**未確認（会場でしか測れない）:**

- **物体キューの余裕** — 参照テンプレートは SCENE 3・4 で**壇上で作られる**ため、
  照合側と作る側が同じ照明・同じ背景・同じ距離になる。事前に会場の照明を知る必要は
  原理的にない。手元で明るい／暗い／逆光の3条件の**振れ幅**だけ測っておき、会場では
  設営後に SCENE 3→5 を1回通す。
- **SCENE 1 の尺**（1:10 に収まるか）と**スペース切替のリハーサル**。

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
