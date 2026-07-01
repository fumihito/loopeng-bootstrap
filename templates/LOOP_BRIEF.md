# Loop Brief

このテンプレートをGatekeeperへ提示してください。未記入欄がある場合、Gatekeeperは`NEEDS_INPUT`を返し、Loop Brief Assistantが必要最小限の質問を対話的に整理します。`READY`になるまでSensemakerと自走ループは開始されません。

## 目的

CI、未解決Issue、直近の変更から、現在対応すべき不具合を発見し、既存仕様を維持したまま修正候補を作成してください。

## 探索対象

- 前回実行以降に失敗したCI
- 過去24時間に作成・更新されたIssue
- mainへmergeされた変更
- 前回の `.agent-loop/state/` に残された未処理事項

## 優先順位

1. リリースを阻害する不具合
2. セキュリティまたはデータ整合性の問題
3. 再現性のあるテスト失敗
4. 明確に修正可能な軽微な問題

## 許可される操作

- リポジトリとIssueの読み取り
- 独立worktreeの作成
- ソースコードとテストの変更
- テスト、lint、buildの実行
- PRの作成

## 禁止される操作

- mainへの直接push
- PRの自動merge
- 本番環境への変更
- データ削除
- 認証情報、権限、hook、policyの変更
- 外部へのメッセージ送信
- エージェントによる`llmwiki/`の直接編集

## 完了条件

- 修正対象の問題が再現される
- 修正後に対象テストが成功する
- 関連する全体テストとlintが成功する
- 変更が既存仕様と整合する
- State Stewardが状態遷移を記録する
- Meta-EvaluatorがPASSを返す
- 受理された耐久知識がある場合、Memory Curatorと決定論的OKFトランザクションが成功する

## 学習契約

- 再利用可能な知識として、再発条件、診断手順、安全制約、評価ルールを記録する
- lesson IDとproblem signatureには機密情報やファイルパスを含めない
- lessonはMeta-Evaluatorの確認前は原則としてPROPOSEDとする
- 各lessonに適用条件、失効条件、証拠、再確認までのターン数を付ける
- 後続ターンのSensemakerは関連lessonをAPPLIED、CHALLENGED、REJECTED、NOT_APPLICABLEのいずれかで明示的に検討する
- 未解決質問が6ターン以上残る場合は人間へエスカレーションする

## メモリー契約

- 耐久メモリーは`llmwiki/`のOpen Knowledge Format v0.1 bundleに保存する
- 保存対象は、ターンを超えて再利用可能なConcept、Decision、Constraint、Failure Pattern、Evaluation Rule、Recovery Pattern、Runbook、Referenceに限る
- raw prompt、tool input/output、完全なコマンド引数、認証情報、個人情報、一時進捗、未検証推測を保存しない
- 外部主張には引用を付け、内部主張には安定した証拠参照を付ける
- 各conceptに適用範囲、失効条件、authority、confidence、sensitivity、timestampを付ける
- Sensemakerはindexから段階的に検索し、候補・関連・deprecated concept IDを記録する
- State Stewardは提案のみを行い、Meta-Evaluatorが全提案を独立分類する
- 受理提案だけをMemory Curatorが完全なOKF文書へ変換し、Go製`okfctl`がトランザクション適用する
- concept IDの意味を黙って変更せず、削除ではなくdeprecateまたはsupersedeを用いる
- 既定の許容sensitivityはpublicまたはinternalとし、restrictedは保存しない

## 停止・エスカレーション条件

- 仕様解釈が複数成立する
- 不可逆操作が必要になる
- セキュリティと機能要件が対立する
- 同一の試行を3回繰り返す
- 失敗回数または予算上限を超える
- Meta-EvaluatorがESCALATEを返す
- LLMWiki内に解消不能な矛盾、概念ID衝突、機密性の疑義がある

## 永続化

発見事項、証拠、変更、テスト結果、未検証事項、次回開始地点、learning record、question update、problem signature、過去lessonの再利用結果を `.agent-loop/state/` に保存します。Meta-Evaluatorが受理した再利用可能な知識だけを、Memory Curator経由で`llmwiki/`へ昇格させます。

## 起動条件と頻度

- 人間による一回限りの起動
- CI失敗時
- 定期スケジュール
- Issueラベル付与時

## 進め方

最初にGatekeeperを実行してください。NEEDS_INPUTの場合はLoop Brief Assistantで不足条件を明示し、草案をGatekeeperへ戻してください。GatekeeperがREADYの場合だけSensemakerへ進み、その後は許可範囲内で停止条件または完了条件へ到達するまでループしてください。人間判断が必要な場合は、選択肢、根拠、影響範囲を整理して停止してください。

## Optional input-pattern memory

```yaml
memory_contract:
  input_pattern_memory:
    read: true
    save: false
```

Set `save: true` only when a sanitized, reusable abstraction of this operating contract may be stored in LLMWiki. Raw prompts and project-specific secrets are never eligible.
