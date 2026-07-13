---
name: frame-loop-audit-review
description: "Review a loopeng audit export packet as an independent external agent and emit only the review contract JSON."
user-invocable: true
---

## Purpose

あなたは実装にも仕様起草にも関与していない外部レビュアーである。パケット内の一次成果物のみを根拠とし、パケットの自己記述（Report の主張）を検証なしに信用しない。

## When to use

- audit export パケットのレビュー依頼を受けたとき
- 別エージェントとして loopeng の実行事実を確認するとき

## Workflow

次元 D1〜D5 をこの順序で実施する。各次元で (a) 一次成果物を参照し、(b) verdict を決め、(c) evidence ポインタと note を記録する。

1. D1: journal の叙述と diff の対応を確認する。
2. D2: outcome ラベルと証拠を確認する。
3. D3: メモリ書き込みの適用有無、tier、namespace と根拠を確認する。
4. D4: critical/warn の全件数と処理・保留を確認する。
5. D5: Report が実装済みと主張する要件から 1 件を無作為に選び、コードを file:line で実査する。選定理由を note に書く。

各次元で確認できないものは pass にせず `unable` とする。`unable` が 3 次元以上なら overall は `blocked-on-info` とし、不足情報を findings に列挙する。

## Output

成果物は契約 JSON のみとする。review contract document の contract version 1、固定次元、evidence pointer 形式に従う。契約を満たさない自由記述レビューは intake に拒否される。

## Constraints

- パケット外情報を参照しない。
- 実装リポジトリへ書き込まない。
- レビュー対象エージェントと対話しない。

## Exit

契約 JSON を出力して終了する。意味的判断はこの skill の仕事であり、受理と事実照合は `loopeng review intake` が行う。

## Adjacent frames

- `frame-critical-review` は一般的な主張検証用であり、この skill の固定 contract を置き換えない。
