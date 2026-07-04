<!-- completion-protocol:begin -->
## Completion protocol (mandatory)

監査対象パス(`.agent-loop/` `tests/` `install.py` `utils/` `docs/loop-structure*`)に触れる作業では:

1. 完了宣言の前に `python3 utils/audit_guard.py record` を実行する。
2. record が失敗したら、修正するまで完了を宣言しない。失敗を記録する行を手書きしない。
3. 生成された audit 行(`docs/audit-log.md`)を必ずコミットに含める。
4. 完了宣言に record の出力(または audit 行)を含める。

詳細: `docs/RELEASE_AUDIT.md`
<!-- completion-protocol:end -->
