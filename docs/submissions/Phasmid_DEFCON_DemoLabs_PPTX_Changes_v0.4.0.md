# Phasmid_DEFCON_DemoLabs.pptx — 0.4.0 反映のための変更点まとめ

**目的:** v0.4.0 に至るデモ変更（WebUI 中心の Bind/Operate、Issue #169 の TUI 非活性化）を
`Phasmid_DEFCON_DemoLabs.pptx`（全26枚）に反映するための作業リスト。
実際のスライド編集は手動で行う前提のため、**現状のテキストと変更後のテキストを対で示す**。
対象は **Slide 23・24** のみ（他スライドは python-pptx でも本文を確認したが変更不要）。

参照した確定情報の出どころ:
- `docs/submissions/Phasmid_Demo_Runbook.md`（実機で全手順確認済み・最新の Step 0〜7 構成）
- `docs/submissions/Phasmid_Talk_Script_30min.md`（v5 改訂済みの台本・Slide 24 該当セクション）
- 公開アーティファクト「Phasmid — DEF CON Demo Labs Run-of-Show」（同じ Step 0〜7 に更新済み）

---

## Slide 23 — LIVE DEMO（章扉）

### サブタイトル行（本文シェイプ）

**現状:**
```
Create → Faces → Guided → Audit → WebUI → Silent Standby
```

**変更後:**
```
Create → Bind (WebUI) → Operate (WebUI) → Refuse → Audit → Silent Standby
```

理由: 現行の文言は「Faces」「Guided」など今のデモ動線と対応しない語を含む。
Bind と Operate が WebUI で行われることを章扉の時点で示しておくと、Slide 24 で
プロジェクタが切り替わることに観客が驚かない。

### ノート（スピーカーノート）

**現状のまま変更不要。** 「プロジェクタ入力をTUIへ切替」は Step 0/1 開始時の操作として
引き続き正しい（切替はこの後の Step 1→2 と Step 3→4 の2箇所のみ）。

---

## Slide 24 — LIVE DEMO（本編）

### サブタイトル（本文シェイプ）

**現状:**
```
Real TUI — Local Disclosure Control
```

**変更後:**
```
Real TUI + local WebUI — Local Disclosure Control
```

理由: 本編は TUI 単独ではなく TUI と WebUI の両方を実際に操作する。単独表記のままだと
壇上でブラウザに切り替えた瞬間、スライドの主張と矛盾して見える。

### Walkthrough 箇条書き（本文シェイプ）

**現状:**
```
Create a Vessel — deniable container
Store a file with the object cue
Recover with the object — it comes back
Recover WITHOUT it — refused after 10 s
Audit — free space, and what it won't judge
Local WebUI over USB → Silent Standby
```

**変更後:**
```
Create a Vessel — deniable container (TUI)
Bind two Faces via the local WebUI — object cue per Face (WebUI)
Recover with the object — it comes back; a second, narrower session (WebUI)
Recover WITHOUT it — refused after 10 s, back on the TUI
Audit — free space, and what it won't judge (TUI)
Silent Standby — the WebUI drops with it (TUI)
```

理由: 6行のうち3行（Bind・1回目のRecover・WebUI言及）が「見せるだけ」から
「実際に壇上で操作する」に変わった。特に "Store a file" という表現は Add File を指すが、
Add File は Issue #169 で TUI から非活性化済みで、実際には WebUI の Store 画面で行う —
現状の文言のまま話すと事実と食い違う。

### bottom bar 行（本文シェイプ）

**現状:**
```
bottom bar  Open · New · Guided · Expert · Quit · WebUI   (Expert adds Audit · Doctor)
```

**変更後:**
```
bottom bar  Open · New · Guided · Expert · Quit · WebUI   (Expert adds Audit — Doctor/Inspect moved off the footer, #169)
```

理由: Issue #169 の実装で、Expert フッタから **Doctor** と **Inspect** の2キーを非活性化した
（フッタからは消えるが、コマンドパレット経由では引き続き到達できる — 削除ではなく非活性化）。
**Audit はあえて残した**（本デモの Step 5 でキー1つで直接使うため）。現状の文言のまま
"Expert adds Audit · Doctor" と言うと、壇上のフッタに Doctor が映らないため観客と食い違う。

### スピーカーノート

**現状:**
```
[19:20 / ~7:00] LIVE DEMO  ★中心
EN (最小限・手を動かしながら): "This is the real TUI — Local Disclosure Control. I create
a vessel. I store a file while holding the object in front of the camera. I recover it
with the object — it comes back. Now watch: same file, same password, same everything,
only the object is gone. Ten seconds, and it refuses. That is what 'the cue gates the
operation' means. Then Audit — note what it does not claim. Then the local web
interface, and Silent Standby."
JA: 詳細手順は別紙 Phasmid_Demo_Runbook（8ステップ）を参照。Step 3b（物体なしで失敗）が
本番の山。ここで必ず間を取る。成功例だけでは cue≠key を何も証明していない。マウスは
使わない（Tab/Enter）。端末幅123桁以上。Fill Free Space は実測4分なので壇上では実行しない。
失敗時は録画へ切替。約7分で切り上げ、Q&Aに15分残す。
```

**変更後:**
```
[19:20 / ~7:30] LIVE DEMO  ★中心
EN (最小限・手を動かしながら): "This is the real system — the TUI handles prepare, refuse,
and disclose; the local WebUI, reached over USB, handles bind and operate. I'll create a
vessel here. Then I switch to the browser, log in with a store-scoped token, and register
two Faces — each one bound to an everyday object in front of the camera. I'll open one
back with the correct object — it comes back, and I'll show you a second, narrower
session that can never reach Face setup at all. Then I switch back here and do the
important part: same file, same password, same everything — only the object is gone.
Ten seconds, and it refuses. That is what 'the cue gates the operation' means. Then
Audit — and notice what it doesn't claim. Then Silent Standby."
JA: 詳細手順は別紙 Phasmid_Demo_Runbook（8ステップ、合計 ~7:30）を参照。Step 2〜3
（Bind・Operate）は WebUI、Step 4（物体なしで失敗）は TUI に戻す — 本番の山はここ。
物体なしの対比が無ければ cue≠key は何も証明していない。プロジェクタ切替は Step 1→2 と
Step 3→4 の1往復のみ。マウスは使わない（Tab/Enter）。端末幅124桁以上（#169 の
Doctor/Inspect 非活性化でフッタが縮み、閾値が123→124桁に変わった点に注意）。
Fill Free Space は実測4分なので壇上では実行しない。失敗時は録画へ切替。
約7分半で切り上げ、Q&Aに15分残す。
```

理由: 台本 v5（`Phasmid_Talk_Script_30min.md`）の Slide 24 セクションと歩調を合わせる。
主な変更点は次の3つ:
1. "I store a file" → WebUI での Bind（Face 2つの登録）に置き換え。Add File は #169 で
   非活性化済みのため、この表現をそのまま使うと壇上の操作と一致しない。
2. Step 番号を「Step 3b」から**「Step 4」**へ統一（ランブック・台本と同じ番号体系）。
3. 端末幅の閾値を **123桁→124桁**に修正（Doctor/Inspect 非活性化でフッタの項目数が
   1つ減ったことによる — ランブック §9 参照）。

---

## 変更不要なスライド（確認済み）

Slide 1〜22、25、26 の本文・ノートを python-pptx で確認したが、TUI/WebUI の役割分担や
Issue #169 に関わる記述は含まれていない（Slide 16 の "Operate through CLI, TUI, or local
WebUI" のような一般論の記述は今回の変更と矛盾しないため据え置き）。

---

## 反映後の確認

編集後、以下で本ファイルとの整合を再確認できる:
- `docs/submissions/Phasmid_Demo_Runbook.md` §1（タイミング表）・Step 2〜4
- `docs/submissions/Phasmid_Talk_Script_30min.md` Slide 24 セクション（本ドキュメントの
  「変更後」はこのファイルの記述とほぼ同一の文言）
- 公開アーティファクト「Phasmid — DEF CON Demo Labs Run-of-Show」
