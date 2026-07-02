# Learning Observability

## 1. 目的

この機能は、ループが単にタスクを完了しているかではなく、複数ターンを通じて次の能力を持つかを観測するためのものです。

1. 経験を再利用可能な形で捕捉する。
2. 過去の知識を後続ターンで実際に検討する。
3. 再利用した知識が有効だったかを独立評価する。
4. 誤った知識を反証、失効、置換できる。
5. 同型問題の再発と未解決事項の滞留を検知する。
6. 評価方法そのものを改善する。

PASS率、作成したlesson数、ツール実行数は学習の証拠ではありません。高いPASS率は評価器の形骸化でも生じ、lesson数は未検証の記録量にすぎないためです。

## 2. 観測アーキテクチャ

```text
Gatekeeper
  learning_contractを確認
        ↓
Sensemaker
  problem_signatureを付与
  learning_retrievalで候補と関連lessonを記録
  prior_learning_consideredを記録
  hypothesis_updatesを記録
        ↓
Generator / ordinary evaluation
        ↓
State Steward
  learning_recordsを提案
  question_updatesを記録
        ↓
Meta-Evaluator
  lessonを承認・反証・保留・置換
  再利用結果をHELPFUL/NEUTRAL/HARMFUL/UNVERIFIEDで評価
  evaluation_changesを記録
        ↓
Deterministic Learning Observer
  複数ターンを集計
  learning-health.jsonを生成
        ↓
Learning Auditor
  指標を構造的に解釈
  制度・policy変更案を提示
```

決定論的Observerは計数と順序検査を担当します。Learning Auditorは、指標が示す構造的意味を解釈します。Auditor自身は記録やpolicyを変更できません。

## 3. Learning contract

GatekeeperがREADYを返すには、Loop Briefに`learning_contract`が必要です。最低限、次を明示します。

- どの種類の経験を再利用可能な知識として残すか。
- lesson IDやproblem signatureの命名範囲。
- 何を証拠としてlessonをVALIDATEDとするか。
- どの条件でlessonを再検討または失効させるか。
- 後続ターンが過去lessonをどのように検討するか。
- 未解決質問をいつエスカレーションするか。

Gatekeeperはこれらを推測して補完してはいけません。

## 4. 安定識別子

### problem_signature

同型問題をターン横断で識別する、非機密の安定IDです。

例:

```text
auth.session-expiry.race
ci.python312.import-regression
db.migration.lock-timeout
```

ファイルパス、ユーザー名、顧客名、トークン、プロンプト本文などは含めません。同一問題クラスには同じsignatureを再利用します。

### lesson_id

再利用可能な知識の意味を識別します。同じIDの意味を変更してはいけません。意味を変更する場合は新しいIDを作り、`supersedes`で旧IDを明示的に置換します。

### question_id

未解決質問のライフサイクルを追跡します。OPEN、ANSWERED、DEFERRED、INVALIDATEDのいずれかで更新します。

## 5. lessonの構造

State Stewardは各lessonについて次を記録します。

```json
{
  "lesson_id": "L-auth-refresh-locking",
  "kind": "FAILURE_PATTERN",
  "statement": "Refresh token rotation and session write must share a serialization boundary.",
  "status": "PROPOSED",
  "evidence_refs": ["test:auth_refresh_race", "diff:current-turn"],
  "confidence": 0.8,
  "applicability": "Session stores with concurrent refresh requests",
  "invalidation_conditions": "Storage engine provides atomic compare-and-swap for the full transaction",
  "supersedes": [],
  "review_after_turns": 10
}
```

`statement`などの内容はリポジトリ内に保存されますが、OTelには送信されません。Observerの集計インデックスにはstatement本文ではなくdigestだけが保存されます。

## 6. lessonのライフサイクル

```text
PROPOSED
  → VALIDATED
  → 後続ターンでAPPLIED / CHALLENGED / NOT_APPLICABLE
  → HELPFUL / NEUTRAL / HARMFUL / UNVERIFIED
  → 必要に応じてCHALLENGED / SUPERSEDED / REJECTED
```

単に作成されたlessonは学習とみなしません。Meta-Evaluatorが証拠を確認し、後続ターンで検討され、結果が評価されて初めて再利用可能性を観測できます。

## 7. 決定論的指標

### observation_coverage

完了ターンのうち、problem signature、過去lesson検討、learning record、question update、learning assessmentが揃っている割合です。低い場合、他の学習指標も信頼できません。

### knowledge_capture_rate

完了ターンのうち、少なくとも一つのlessonがMeta-Evaluatorに受理された割合です。高いほど良いとは限りません。毎回lessonを作る必要はありません。

### learning_retrieval_coverage

完了ターンのうち、Sensemakerが過去learning stateを検索し、候補と関連lessonを明示した割合です。検索不能だった場合は理由を記録します。

この証拠は Read ツールで learning state を参照した journal 記録から判定します。`okfctl` の実行痕跡は memory retrieval の証拠であり、learning retrieval とは区別します。

### learning_reuse_rate

`learning_retrieval.relevant_lesson_ids`が一つ以上あるターンのうち、Sensemakerが関連lessonを明示的に検討した割合です。単に過去lessonが存在するだけの無関係なターンは分母に含めません。

### helpful_reuse_rate

結果評価済みの再利用イベントのうち、Meta-EvaluatorがHELPFULと判断した割合です。因果関係を証明するものではありません。

### recurrence_after_learning_rate

同じproblem signatureが再発したケースのうち、以前の発生時点までにvalidated lessonが存在していた割合です。再発が正当な定期作業である可能性もあるため、Auditorによる解釈が必要です。

### question_resolution_rate

追跡されたquestion IDのうち、ANSWEREDになった割合です。DEFERREDの滞留もlearning debtに含まれます。

### evaluation_adaptation_rate

評価方法の変更がMeta-EvaluatorにACCEPTEDされたターンの割合です。ゼロが必ず悪いわけではありませんが、失敗が続くのにゼロなら評価系が学習していない可能性があります。

### learning_chain_completion_rate / average_turns_to_first_reuse

validated lessonのうち、後続ターンで一度以上明示的に検討された割合と、検証から最初の再利用までの平均ターン数です。再利用の質は別途HELPFUL / HARMFULで評価します。

### trend

現在windowと直前の同じ長さのwindowを比較し、観測カバレッジ、再利用率、再発率、質問解決率、評価適応率、learning debtの差分を出します。最低2 window分のデータがない場合は比較不能です。

### learning_debt_score

次をpolicyの重みで集計します。

- 観測記録の欠落
- 長期未解決質問
- 未検証のまま残るlesson
- 再利用も再検証もされないstale lesson
- 同じlesson IDの意味衝突
- HARMFULと評価された再利用
- 学習後の同型問題再発
- 未登録lessonへの参照
- learning retrievalの未実施
- 関連lessonの未検討
- lesson recordなしでの承認
- APPLIED / CHALLENGED後の結果未評価
- 証拠、適用条件、失効条件が不足したlesson

## 8. ヘルス判定

```text
UNKNOWN
  完了ターンが少なく、判断根拠が不足

HEALTHY
  観測カバレッジが十分で、重大な学習負債が検出されない

DEGRADED
  再利用不足、未解決質問、stale lesson、観測欠落などが蓄積

UNHEALTHY
  harmful reuse、lesson IDの意味衝突、高い再発率、重大なlearning debt
```

しきい値は`.agent-loop/learning-policy.json`で管理します。しきい値を良く見せるために自動変更してはいけません。

## 9. 実行方法

決定論的レポートを再構築します。

```bash
python3 .agent-loop/bin/learning_health.py rebuild
```

JSONレポート:

```bash
python3 .agent-loop/bin/learning_health.py report --format json
```

人間向けMarkdown:

```bash
python3 .agent-loop/bin/learning_health.py report --format markdown
```

CIでUNHEALTHYを失敗扱いにします。

```bash
python3 .agent-loop/bin/learning_health.py check --fail-on unhealthy
```

DEGRADEDも失敗扱いにする場合:

```bash
python3 .agent-loop/bin/learning_health.py check --fail-on degraded
```

Learning Auditorを起動する場合、ユーザー入力の先頭を次のようにします。

```text
learning-audit: 過去50ターンについて、学習の再利用、再発、知識負債、評価方法の適応を監査してください。
```

SOPルーターが`sop-learning-audit`をロードし、決定論的レポートの再構築と`learning-auditor`の起動を要求します。

## 10. 既存履歴からの導入

v11以前の完了ターンはlearning fieldを持たないため、観測カバレッジを下げます。アップグレード時点を新しい観測baselineとする場合は、`.agent-loop/learning-policy.json`の`history_start_at`へISO 8601時刻を設定します。

```json
{
  "history_start_at": "2026-07-01T00:00:00+09:00"
}
```

過去ターンを無理に補完して観測品質を良く見せてはいけません。必要なら人間が根拠を確認したうえで別の移行記録を作成します。

## 11. 保存場所

```text
.agent-loop/runtime/turns/<turn-id>/learning-observation.json
.agent-loop/state/learning/turns/<turn-id>.json
.agent-loop/state/learning/learning-health.json
.agent-loop/state/learning/learning-index.json
```

runtimeとstateの保存期間は、リポジトリのデータ保持ポリシーに合わせて管理してください。

## 12. OTel

次の安全な集計イベントを追加します。

- `agent.loop.learning.turn_observed`
- `agent.loop.learning.health_updated`
- `agent.loop.learning.observation_failed`
- `agent.loop.learning.audit_reported`

OTelには件数、比率、ヘルス分類だけを送ります。lesson ID、question ID、problem signature、lesson本文、根拠、プロンプト、パス、引数は送りません。

## 13. 解釈上の制約

- lessonを利用したターンが成功しても、そのlessonが成功原因とは限りません。
- relevant lessonの判定自体はSensemakerの意味判断であり、決定論的Observerが正しさを保証するものではありません。
- 同じproblem signatureの再発は、正当な反復作業の場合があります。
- correctionが少ないことは、知識が正確な証拠ではなく、反証が行われていない可能性があります。
- lesson数を目標化すると、記録量だけが増えるGoodhart化が起きます。
- 意味的類似度やembeddingによる自動クラスタリングは、非決定性と機密性の理由で標準機能には含めていません。

## 14. 推奨監査周期

- 開発初期: 10〜20完了ターンごと
- 安定運用: 週次または50完了ターンごと
- Watchdog急増、再発、HARMFUL reuse発生時: 即時
- policyや評価基準変更後: 変更前後の同じ長さのwindowを比較


## OKF LLMWiki memory observations

学習観測は、lessonの状態遷移だけでなく、耐久メモリーの検索と昇格も追跡します。各ターンは`memory_retrieval`、`memory_proposals`、`memory_assessment`、`memory_commit`の要約を持ちます。Observerは本文やconcept IDをOTelへ送らず、検索実施率、提案数、受理数、commit数、proposal-to-commit完了率、commit失敗数だけを集計します。

受理されたproposalがcommitされない場合は、知識が評価から保存へ移る経路が壊れているためUNHEALTHY要因です。一方、concept数の増加は学習の証拠ではありません。検索されず、役立たず、訂正されないWikiは知識負債です。
