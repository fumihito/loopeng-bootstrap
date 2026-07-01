# 自走ループに必要な人間入力

## Entry modes

Choose the interaction mode explicitly when the distinction matters:

- `direct:` for a bounded one-shot question or inspection without Gatekeeper. It is read-only by default and does not create a learning or memory record.
- `<header>:` for a mandatory SOP such as `diag:` or `learning-audit:`.
- no header for an autonomous-loop request. This enters Gatekeeper and, when incomplete, the Loop Brief Assistant dialogue.

Loop Brief Assistant is not a substitute for human authority. It structures explicit answers and returns a draft to Gatekeeper; it does not fill missing conditions by inference.

## 入口はGatekeeper

ユーザーはGeneratorやSensemakerへ直接指示せず、まずGatekeeperへ目的またはLoop Briefを提示します。Gatekeeperは10条件の充足を確認し、`READY`、`NEEDS_INPUT`、`REJECT`のいずれかを返します。`READY`のときだけ、正規化されたLoop BriefがSensemakerへ渡されます。Gatekeeperが`NEEDS_INPUT`を返すとLoop Brief Assistantが不足条件を対話的に整理します。前回の草案と質問はセッション単位で保持され、完成草案はGatekeeperへ戻されます。

この仕組みは、一回の実行を統治する hook と10個のロールを提供します。自動的に次回実行を起動するスケジューラそのものではありません。

```text
hook＋9ロール = 一回の実行を安全に統治する仕組み
scheduler＋永続状態 = 次の実行を自動的に起動する仕組み
```

人間が与えるべきものは逐次作業指示ではなく、ループが自律判断するための「運用契約」です。

## 1. 固定的な運用契約

次の内容を `.agent-loop/state/project.md`、`.agent-loop/policy.json`、`AGENTS.md`、`CLAUDE.md` などへ保存します。

- Purpose: 最終的に実現する状態
- Non-goals: 実行しないこと
- Protected boundaries: 変更禁止領域
- Human-only decisions: 人間だけが判断する事項
- Trusted evidence: 正しさを判断する一次情報
- Risk tolerance: 許容可能な損失・変更範囲
- Approval policy: 人間承認が必要な操作
- Resource limits: 時間、トークン、再試行、並列数

## 2. 各ループ開始時に必要な10項目

### Outcome

作業手順ではなく、終了時に成立している状態を定義します。

### Discovery scope

CI失敗、Issue、直近の変更、監視アラート、前回状態など、仕事を発見する情報源を定義します。

### Authority envelope

読み取り、編集、テスト、PR作成などの許可範囲と、mainへのpush、本番変更、外部送信などの禁止範囲を定義します。

### Evaluation contract

テスト結果、lint、実動作、仕様との対応、セキュリティ境界など、正しさの証拠を定義します。

### Persistence contract

発見事項、証拠、変更、テスト結果、未検証事項、次回開始地点など、次回へ残す情報を定義します。

### Learning contract

何を再利用可能な知識として残すか、どの証拠で検証するか、どの条件で失効・置換するか、後続ターンが過去知識をどう検討するかを定義します。lesson数やPASS率を学習の代理指標にしないことも明示します。

### Memory contract

OKF LLMWikiへ昇格してよい知識、除外対象、機密区分、根拠と引用、レビュー・失効規則、昇格主体を定義します。実行ログや未評価の推測をそのまま長期記憶へ入れないことを明示します。

### Stop condition

完了条件と、反復、失敗回数、予算、価値判断、不逆操作などによる停止条件を定義します。

### Escalation contract

仕様の多義性、価値対立、公開API変更、本番操作など、人間へ戻す条件を定義します。

### Trigger / cadence

同一セッション内の継続条件と、cron、CI、automationなどのセッション間トリガーを定義します。

## 3. 入力レベル

### 最小入力

- 目的
- 探索対象
- 許可範囲
- 完了条件
- 停止条件

低リスクで可逆な作業向けです。

### 標準入力

上記10項目すべてを定義します。通常の実務ではこの形式を推奨します。

### 高保証入力

標準入力に加えて、次を定義します。

- 安全制約
- ロールバック地点
- 承認者
- 最大変更量
- 最大並列数
- リスク分類
- 評価器の独立条件
- ホールドアウト評価

本番、セキュリティ、インフラ、データ移行向けです。

## 4. ロール別に必要な人間入力

| ロール | 必要な入力 |
|---|---|
| Sensemaker | 目的、探索範囲、非目的 |
| Governor | 許可、禁止、承認境界 |
| State Steward | 保存対象、信頼できる証拠 |
| Watchdog / Recovery | 上限、停止条件、安全な復旧点 |
| Meta-Evaluator | 本来の目的、評価基準、lessonの検証条件、許容不能な見逃し |

## 5. 人間が与えない方がよい入力

次のような逐次指示は、人間がPlannerとGeneratorを代行するため、自走性を失わせます。

```text
このファイルを開く
この関数を変更する
このコマンドを実行する
次にこのテストを動かす
```

代わりに、次を定義します。

```text
何を達成するか
どこから仕事を見つけるか
何を証拠とするか
何をしてよいか
いつ止まるか
誰へ戻すか
```

## 6. 自走に必要な三要素

1. `project.md` と `policy.json` による固定的な運用境界
2. 10項目を含む Loop Brief
3. cron、CI、Codex/Claude automationなどの再起動トリガー

この三つが揃って初めて、hookにより統治された継続的な自走ループになります。


## 9. Memory contract

自走ループが何を長期記憶へ昇格させるかを明示します。最低限、保存対象、保存禁止情報、信頼できるauthorityとcitation、適用範囲・失効条件、review周期、promoterを定義してください。既定の保存先は`llmwiki/`のOKF v0.1 bundleで、State Stewardは提案のみ、Meta-Evaluatorが独立評価し、Memory CuratorとGo製`okfctl`だけが反映します。

「すべて記憶する」は有効な契約ではありません。生ログや会話履歴を耐久知識へ混入させると、検索ノイズ、機密性、古い前提の固定化、責任不明確化を招きます。

## Input-pattern memory contract

To permit Loop Brief pattern retrieval or capture, make it explicit inside `memory_contract`:

```json
{
  "input_pattern_memory": {
    "read": true,
    "save": true
  }
}
```

`read` permits Assistant to retrieve reviewed pattern candidates. `save` permits Assistant to propose an abstract pattern after the brief is complete. Neither flag grants permission to copy previous authority. Every reused field must still be confirmed and Gatekeeper must validate the current brief.
