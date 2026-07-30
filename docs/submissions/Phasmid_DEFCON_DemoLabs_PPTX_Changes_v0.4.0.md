# Phasmid_DEFCON_DemoLabs.pptx — 適用済み変更の記録

**状態: 適用済み。** 本ファイルは当初「手作業でデッキを編集するための指示書」だったが、
変更は `python-pptx` で `Phasmid_DEFCON_DemoLabs.pptx` に直接適用したため、
**何をどう変えたかの記録**に書き換えた。手順書として読む必要はない。

対象は **Slide 23・24 とそのスピーカーノートのみ**（他22枚は本文・ノートとも未変更。
ZIP パート差分で `slide23.xml` / `slide24.xml` / `notesSlide23.xml` / `notesSlide24.xml`
の4つだけが変わったことを確認済み）。

反映元:
- `docs/submissions/Phasmid_Demo_Runbook.md`（9手・合計 ~7:20）
- `docs/submissions/Phasmid_Talk_Script_30min.md`（Slide 24 セクション）
- 公開アーティファクト「Phasmid — DEF CON Demo Labs Run-of-Show」

---

## 変更の理由

旧デッキは **8手・TUI 中心**の構成を前提にしており、現行の**9手・TUI+WebUI**構成と
食い違っていた。特に問題だったのは次の3点。

1. **`Store a file with the object cue`** — これは TUI の `Add File` を指すが、
   Issue #169 で非活性化済み。実際の保存は WebUI の Store 画面で行う。
2. **成功例しか予告していなかった。** 現行デモの中心は
   **「同じ容器・2つのパスワード・2つの別ファイル」**（Janus の実証）で、
   旧デッキはこの対比を一言も示していなかった。
3. **`(Expert adds Audit · Doctor)`** — Doctor は #169 でフッタから消えたため、
   壇上のフッタに映らず観客と食い違う。

---

## Slide 23（章扉）

| 箇所 | 変更前 | 変更後 |
|---|---|---|
| フロー行 | `Create → Faces → Guided → Audit → WebUI → Silent Standby` | `Create → Bind → Two passwords → Refused → Audit → Silent Standby` |

`Faces` / `Guided` は現行動線に対応しない語だった。新しい並びは2つの証明
（`Two passwords` = Janus、`Refused` = cue≠key）を章扉の時点で予告する。
最終セグメントの強調色（オレンジ）は元のまま維持。

タイトル `LIVE DEMO`、サブタイトル `Local Disclosure Control — on real hardware`、
録画フォールバックの注記は変更なし（いずれも現行構成でも正しい）。

**ノート:** プロジェクタ切替が Step 1→2 と Step 4→5 の1往復だけである旨を追記。

---

## Slide 24（本編）

| 箇所 | 変更前 | 変更後 |
|---|---|---|
| 見出し | `What you'll see at the table` | `One container, two passwords, two files` |
| 副題 | `Real TUI — Local Disclosure Control` | `Real TUI + local WebUI — Local Disclosure Control` |
| bottom bar | `… (Expert adds Audit · Doctor)` | `… (Expert adds Audit)` |

見出しを「卓上デモの案内」から**本デモの主張そのもの**に差し替えた。この1行が
Slide 7 の Slot A / Slot B と直結する。

**Walkthrough（6行）**

変更前:
```
Create a Vessel — deniable container
Store a file with the object cue
Recover with the object — it comes back
Recover WITHOUT it — refused after 10 s
Audit — free space, and what it won't judge
Local WebUI over USB → Silent Standby
```

変更後:
```
Create a container — no header, no magic
Store two files, two passwords, two objects
First password → the first file
Second password → a different file
Object taken away → refused after 10 s
Audit, then Silent Standby
```

3行目と4行目が **Janus の対比**、5行目が **cue≠key の対比**。
9手すべてを列挙せず、証明の骨格だけを残している（詳細は口頭とランブック）。

**ノート:** 全面改稿。EN の読み上げ文を現行の9手構成に差し替え、
①2つの対比の意味と省略不可であること、②Step 2〜4 が WebUI・Step 5 以降が TUI、
③端末幅 124 桁（#169 で 145 から低下）、④`Add File` 非活性化、
⑤**復元が2回とも `retrieved_payload.bin` で落ちるため違いは中身を開いて見せる**
（事前にダウンロードフォルダを空にする）、⑥破壊は壇上で実演しない、
⑦時間超過時に削る手順、を追記。

---

## 検証

- `scripts/office/validate.py out.pptx --original src.pptx` → All validations PASSED
- ZIP パート差分 → 変更は上記4パートのみ、追加・削除パートなし、26枚維持
- **文字あふれを実測で確認。** LibreOffice がこの環境で元デッキすら読み込めず
  レンダリング QA ができないため、代わりに文字幅を計算した。変更した図形の多くは
  **Courier New（等幅・advance = 0.6 em）なので幅は厳密に計算可能**。
  Calibri の1箇所は Liberation Sans で測定した（Calibri より広いため安全側）。

| 図形 | フォント | 使用幅 / 箱幅 | 判定 |
|---|---|---|---|
| s23 フロー行 | Courier New 18pt | 9.60 / 11.50 in | 収まる |
| s24 見出し | Courier New 34pt | 11.05 / 12.10 in | 収まる（最も窮屈・91%） |
| s24 副題 | Courier New 12pt | 4.90 / 6.40 in | 収まる |
| s24 bottom bar | Courier New 12.5pt | 2行に折返し（変更前も2行） | 収まる |
| s24 Walkthrough | Calibri 17pt | 最長 4.49 / 5.40 in | 各行1行に収まる |

Walkthrough は**変更前より最長行が短くなっている**（4.53 → 4.49 in）。
