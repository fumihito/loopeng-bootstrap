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

`python3 -m loopeng review dag` is the deterministic visual review companion. It reads the same JSON sidecars, writes the `loop-dag.mmd` / `loop-dag.svg` Mermaid/SVG artifacts under `.agent-loop/state/reports` (the `--out` path must remain there), and is an explicit read-only-review exception because those artifacts are audit outputs alongside the Run Report.

Use `python3 -m loopeng review dag --stage <stage>` to inspect finding details from schema 2 sidecars; schema 1 sidecars remain readable and are marked as detail unavailable. The detail view is text/JSON only and does not alter the overview diagrams.

The canonical generator is `python3 -m loopeng audit run --run <id>`, which consumes the journal plus the git worktree and writes a markdown report.

## Journal event contract

- `run-start`: `{"kind":"run-start","agent":"<agent>","goal":"<goal>"}`
- `run-end`: `{"kind":"run-end"}`
- `okf-apply`: `{"kind":"okf-apply","report":"<path>","ok":true|false,"touched":[...]}`
- `intent`: `{"kind":"intent","paths":["<relative path or directory>"],"reason":"<reason>"}`

Hooks are the standard automatic capture layer for Claude Code and Codex. `loopeng okf apply --run <id>` and `loopeng journal add` remain CLI paths for explicit/headless use. `audit run` writes the next-turn handoff with `source_turn_id`, `goal`, `summary`, `alerts_summary`, and `generated_at`.

フックから注入するエージェント可視メッセージには `[loopeng-bootstrap v{VERSION} | loopeng/v0.2 | {EVENT}]` 形式のバナーを付ける。
