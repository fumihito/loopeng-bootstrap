# Run Report

Run Report is the completion artifact for v0.2. A run is not considered auditable until the report exists.

## Required sections

1. `What ran`
   - run-id
   - agent type
   - duration
   - handoff source
2. `Mutations`
   - changed files
   - protected-path markers
3. `Memory`
   - applied OKF report
   - rejected OKF report and reason
4. `Learning`
   - new learning entries
   - backlog count
5. `Alerts`
   - alert ID
   - severity
   - evidence reference
6. `Blocked`
   - hard-blocks only
7. `Next`
   - handoff content for the next turn

## Contract

Run Report is descriptive, not justificatory. It reports what happened and what was detected; it does not relabel an alert-free run as proof of correctness.

The canonical generator is `python3 -m loopeng audit run --run <id>`, which consumes the journal plus the git worktree and writes a markdown report.

将来、v0.2 側で任意接続の PreToolUse アダプタ等を実装する場合、エージェント可視メッセージには `[loopeng-bootstrap v{VERSION} | loopeng/v0.2 | {EVENT}]` 形式のバナーを付ける。バナー生成は `loopeng/_paths.py` 近傍に単一関数として置き、loop_hook の形式と一致させる。
