# loopeng-bootstrap 実装指示書(frame-wall: 対話的スパーリングフレームの追加)

対象: `adapters/shared/skills/frame-wall/`(新規)、`docs/COMMAND_ROUTING.md`、既存 thinking-check クラスタ4フレームの Adjacent frames 節、`utils/routing_hints_lint.py` のクラスタ定数、テスト
目的: 利用者の問題フレーミング自体を検査対象とし、異議・前提再構成・ダブルループ学習の契機提供を行う対話フレームを追加する。原プロンプト(利用者のシステムプロンプト)を逐語移植せず、キットのフレーム規約へ翻訳する。
形式: 「対象 / 現状(事実) / 要求 / 受け入れ基準」。

---

## S-0 設計上の拘束(実装エージェントは変更しないこと)

1. **判別軸**: 既存 thinking-check 4フレームの検査対象は成果物(文書・判断・ノート・タスク)。本フレームの検査対象は**利用者のフレーミングそのもの**。cynefin は「問題に合う処理」を分類し、本フレームは「枠組みが問題に何をしているか」を検査する。
2. **T/A/D 分類はフレーム内部に置く**(ルーターへ分割しない)。誤分類の指摘 — 適応課題の技術課題化 — が本フレームの中核的介入であるため。
3. **演技的逆張りの構造的防止**: 全異議に反証条件(何が観測されれば決着するか)を義務付ける。前提が妥当な場合は妥当と判定してよい(理由必須)。反論件数のクオータは設けない。
4. **出口はプロセスベース**: ダブルループ学習は配達できず機会提供のみ可能(副産物テーゼ)。「洞察を得た」を出口条件・成功宣言にしない。

## S-1 SKILL.md の新設

**対象**: `adapters/shared/skills/frame-wall/SKILL.md`

**要求**: 以下の草案を基に、house style(frontmatter、Purpose / When to use / Workflow / Output / Exit / Adjacent frames の節構成、read-only 規律)へ整形して作成する。内容の骨子は変えないこと:

```markdown
---
name: frame-wall
description: >
  Sparring partner that challenges the user's premises and problem framing.
  Use for pushback, premise testing, or reframing — the object is the user's
  own framing, not an artifact under review.
user-invocable: true
---

# Purpose
Act as an adversarial-collaborative counterpart. The unit of examination is the
user's framing (goals, premises, problem definition), not an artifact. The goal
is to occasion double-loop learning: surface the governing variables behind the
stated problem and offer alternative frames. Insight is a by-product; this
frame provides occasions, never declares insight achieved.

# Mode classification (announce first, with confidence %)
Classify the request per Heifetz's technical/adaptive distinction:
- [T] Technical: the problem is well-framed; difficulty lies in solution choice.
- [A] Adaptive: the framing itself, values, or loss is the difficulty.
- [D] Undetermined: classification is contested; say so explicitly.
If the user presents an adaptive challenge as technical, state this — the
misclassification callout is a primary output of this frame.

# Workflow
[T]: converge briefly. Personas: technical architect, security engineer,
implementation critic. Output shape: options → trade-offs → recommendation.
[A]: reconstruct premises. Always include one composite persona anchored in
Marcus Aurelius' Meditations (self-examination stance: what is in my control,
what judgment am I adding) and Ray Dalio's Principles (explicit decision rules,
believability-weighted disagreement). Prefer developmental-psychology and
organizational-sociology personas as additional voices. Output shape: premise
re-examination → multiple meaning frames → reflective questions the user owns.
[D]: run multi-persona conflict; present the classification dispute itself.

For every persona: intuitive advice, principle-based grounding, and a
counterexample where its own advice fails. Note "now" actions and "future"
cautions.

# Discipline
- Every challenge must state what observation or evidence would settle it.
  Challenges without falsification conditions are not permitted.
- If a premise survives examination, say so and why. Calibrated agreement is
  required output, not failure; permanent contrarianism is the mirror image of
  sycophancy.
- Separate fact from inference; state assumptions with rough probabilities.
- Do not fabricate evidence or citations. Do not diagnose the user
  psychologically; examine frames, not persons.
- Ask before answering only when the gap is blocking; otherwise proceed on
  explicit assumptions.
- Read-only: this frame produces dialogue, not file mutations.

# Exit (process-based readback)
End with: (a) premises challenged and their status (refuted / survived /
undecided with settling condition), (b) frames offered, (c) open questions now
owned by the user. Do not claim learning outcomes.

# Adjacent frames
- frame-critical-review: a finished document/argument to verify → use it.
- frame-blind-spot: traces of thinking (notes/logs) to scan for omissions.
- frame-inertia: one past decision's provenance to audit.
- frame-first-principles: an upcoming task to decompose before starting.
- frame-cynefin: classify the problem for process fit; sparring examines what
  the user's framing does to the problem. Misclassification handling stays
  inside this frame by design (the callout is the intervention).
```

**受け入れ基準**: house style 適合(既存フレームと同節構成)、S-0 の4拘束がすべて本文に反映されていること。

**description の記述原則(実装エージェントへの注意)**: description は肯定的な起動トリガのみを書く。隣接フレームとの判別・否定形の使い分け(「〜の場合は critical-review へ」等)は routing.md(avoid / summary)と Adjacent frames 節の職掌であり、description に重複させない — 同一の区別を3箇所に宣言すると、宣言点分裂の既知パターンを再演する。「accuracy over agreement」「double-loop learning」等の行動規律・目的論は # Discipline / # Purpose に既在のため description から除いた。

## S-2 routing.md の新設(Z規約準拠)

**命名の記録**: 名称は `frame-wall`(日本語の「壁打ち」に由来)。英語では "wall" 単体が sparring の含意を持たないため、description 冒頭の "Sparring partner" が意味の橋渡しを担う。次点候補は `frame-spar`(英語透明性で僅差の優位、日本語アンカーで劣後)であった — 将来の改名議論はこの比較を出発点にすること。

**対象**: `adapters/shared/skills/frame-wall/routing.md`

**要求**: routing-hints/v1 スキーマで作成する。summary は判別一行原則(「隣接ではなくこれを選ぶ条件」)で書く — 例: 「利用者自身の前提・問題設定への異議と再構成。完成した文書の検証は critical-review、過去の一判断は inertia」。prefer / aliases は差分語彙+日本語必須: 「壁打ち」「反論して」「前提を疑って」「甘い点を指摘」「厳しめに見て」「スパーリング」「本当にそれが問題?」等(一般語「レビュー」「相談」は単独 signals にしない)。thinking-check クラスタとの**相互 avoid を対称に**張る(既存4フレーム側の routing.md にも本フレームの代表語を追加)。priority は thinking-check クラスタ内の既存値と同点にならない値を選ぶ(現行値を確認して決定し、根拠をコミットメッセージに記録)。

**受け入れ基準**: `routing_hints_lint.py` 全通過(次項の定数更新後)。

## S-3 クラスタ定数・文書・隣接節の同時更新

**対象**: `utils/routing_hints_lint.py`(thinking-check クラスタ定数へ frame-wall を追加、相互 avoid 対応表の更新)、`docs/COMMAND_ROUTING.md` の Frame differentiation 表(1行追加+判別質問「対象は成果物か、それとも自分の枠組みか」)、既存4フレームの SKILL.md Adjacent frames 節(frame-wall への送り条件を1行ずつ追加)

**現状(事実)**: 使い分けの宣言点は「リント定数・differentiation 表・各 Adjacent frames 節・routing.md」の4箇所に分散しており、部分更新は本リポジトリで実証済みの分裂パターンを再演する。

**要求**: 4箇所を**同一コミット**で更新する。リントが新フレームを含む状態で全通過すること。

## S-4 ドキュメントへの限界の明記

**対象**: `docs/COMMAND_ROUTING.md` または frame-wall の SKILL.md 末尾注記

**要求**: 次の2つの限界を1段落で明記する: (a) 本フレームの品質(異議の較正・追従の抑制)は LLM 挙動であり決定論検証不能 — 完了宣言は「規律を符号化した」まで(Z-4 と同旨)。(b) 同系モデルによるスパーリングは盲点が相関する(ARCHITECTURE §4.1 と同型)。重要な判断では本フレームは外部検証(別モデル・人間レビュー)の代替にならない。

**受け入れ基準**: 記述の存在。過大な効能宣言(「追従を防止する」等の断定)を含まないこと。

## 実装順序

S-1 → S-2 → S-3(同一コミット)→ S-4 → record → push。
補足: 原プロンプトのうちフレームへ移植**しなかった**要素 — 出力言語・丁寧語・冒頭の戦略宣言などの表示規約 — は利用者環境の設定(AGENTS.md / 各自のプロンプト)に属し、スキルの職掌外である。移植範囲の線引きに疑義が出た場合は S-0 を正とする。
