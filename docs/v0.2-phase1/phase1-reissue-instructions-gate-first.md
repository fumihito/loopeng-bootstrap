# Phase 1 再発行指示（ゲート先行版）

対象: `fumihito/loopeng-bootstrap`

## 前提

- `utils/phase1_gate.py` はコミット済みであること。
- ここにある文書群が、以後の Phase 1 作業の唯一の参照になること。
- チャットの転記と文書が食い違う場合は、リポジトリ内の文書を正とすること。

## 提案 2

- `tests/test_routing_profile_self_sufficiency.py` の
  `test_routing_profile_does_not_redistribute_legacy_artifacts` を是正する。
- 現在の空検証を破棄し、`utils/phase1_gate.py` の `LEGACY_ARTIFACTS` と同一の対象を検査する。
- `LEGACY_ARTIFACTS` は gate から import する。
- `@unittest.expectedFailure` は SA-WP4 完了時に外す。

## 提案 3

### 手順 0

- `docs/v0.2-phase1/` を作成し、関連文書を配置する。

### 手順 1-5

| WP | 内容の正 | 完了宣言の唯一の形式 |
|---|---|---|
| SA-WP1 | 乖離監査 G-WP1 の 1〜7 | `phase1_gate.py --gate 1` の PASS 出力転記 |
| SA-WP2 | 追補 S3 の修正 1〜3 | `--gate 2` PASS 転記 |
| SA-WP3 | 追補 G-WP7 の 1〜4 | `--gate 3` PASS 転記 |
| SA-WP4 | 乖離監査 G-WP2 の 1〜4 + 追補 S1 | `--gate 4` PASS 転記 + 提案 2 の expectedFailure 除去 |
| SA-WP5 | 乖離監査 G-WP3 の 1〜5 | `--gate 5` PASS 転記 |

## 共通規律

- 各 WP は 1 コミット以上で構成してよい。
- WP 完了コミットには、該当ゲートの PASS 出力を含める。
- SA-WP2 完了後の WP は journal 化する。
- SA-WP3 完了後の WP は intent 宣言を義務化する。
- `utils/phase1_gate.py` は変更禁止。

## 手順 6

- `python3 utils/phase1_gate.py` の `PHASE 1 GATE: GREEN` 全文転記と、検収空ランの Run Report を添付する。
- ここで作業を停止し、SA-WP6 以降には進まない。

