<!-- completion-protocol:begin -->
## Completion protocol (mandatory)

監査対象パス(`.agent-loop/` `tests/` `install.py` `utils/` `docs/loop-structure*`)に触れる作業では:

1. 完了宣言の前に `python3 utils/audit_guard.py record` を実行する。
2. record が失敗したら、修正するまで完了を宣言しない。失敗を記録する行を手書きしない。
3. `record` が audit 行を安全に HEAD へ amend 吸収、または separate モードで自動コミットする。
4. 完了宣言に record の出力(または audit 行)を含める。
5. frame スキルは `adapters/shared/skills` のみを編集し、コミット前に `install.py --self --update` を実行する。

詳細: `docs/RELEASE_AUDIT.md`
<!-- completion-protocol:end -->

## Run discipline

Hooks are the standard journal/audit capture layer for Claude Code and Codex.
Use `python3 -m loopeng journal add` only for headless or script-driven runs;
hooks-disabled operation is a supported degraded mode and may raise
`journal_coverage`.
If a user prompt begins with `review:`, run `python3 -m loopeng review --triage` and present its output as-is (no summary, elaboration, or additional analysis). End the response after presenting the trailing question and wait for the user. Use `--next` for `review: next`, omit `--triage` for `review: full`, and use `--go <item-id>` for `review: go <item-id>`. Execute standard remediation only for catalog entries marked `agent_executable`; otherwise report that user judgment or proposal is required and stop.
