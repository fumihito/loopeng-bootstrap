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
6. `Outcome`
   - observed command/text acceptance result or human label
7. `Behavior`
   - skills used, including source and count
   - blocked operations from `blocked` events
8. `Blocked`
   - hard-blocks only
9. `Next`
   - handoff content for the next turn

## Contract

Run Report is descriptive, not justificatory. It reports what happened and what was detected; it does not relabel an alert-free run as proof of correctness.

`python3 -m loopeng review dag` is the deterministic visual review companion. It reads the same JSON sidecars, writes the `loop-dag.mmd` / `loop-dag.svg` Mermaid/SVG artifacts under `.agent-loop/state/reports` (the `--out` path must remain there), and is an explicit read-only-review exception because those artifacts are audit outputs alongside the Run Report.

Use `python3 -m loopeng review dag --stage <stage>` to inspect finding details from schema 2 sidecars; schema 1 sidecars remain readable and are marked as detail unavailable. The detail view is text/JSON only and does not alter the overview diagrams.

The canonical generator is `python3 -m loopeng audit run --run <id>`, which consumes the journal plus the git worktree and writes a markdown report.

The optional sidecar `behavior` key contains `skills` and `blocked` count maps. The schema version remains unchanged because adding this optional key is backward compatible; raise it only for incompatible changes.

Every tenth completed run is sampled with an informational `external_review_due` marker; `audit export` creates the sanitized packet. The packet mechanism does not decide who reviews it or how a review establishes the loop.

For this deployment, the external review actor is a separate agent. Review execution and result return remain outside the loop mechanism; the exported packet is the handoff boundary.

`Outcome` records the latest human `run outcome` label when present, otherwise the observed `run verify` result. Command acceptance checks run in order with a 300-second timeout: all commands passing and no text checks is `pass`; any command failure is `fail`; passing commands with unresolved text checks is `unverified`. Text acceptance is never resolved by agent self-report. The sidecar includes the optional `outcome` key. Handoff is last-write-wins.

The `memory_commit_divergence` inspection compares the 7-day `llmwiki/log.jsonl` operation count with non-LLMWiki commit activity and reports the configured one-sided divergence signals.

## Journal event contract

The following list is one-to-one with `loopeng.journal.EVENT_KINDS`; changing
that tuple requires updating this section in the same run.

- `run-start`: `{"kind":"run-start","agent":"<agent>","goal":"<goal>"}`
- `run-end`: `{"kind":"run-end"}`
- `okf-apply`: `{"kind":"okf-apply","report":"<path>","ok":true|false,"touched":[...]}`
- `intent`: `{"kind":"intent","paths":["<relative path or directory>"],"reason":"<reason>"}`
- `mutation`: `{"kind":"mutation","path":"<relative path>"}`
- `decision`: `{"kind":"decision","item":"<id>","choice":"go|alt|hold"}`
- `go-result`: `{"kind":"go-result","item":"<id>","result":"<result>"}`
- `review`: review sections recorded after a review output is consumed.
- `command`: a tool command captured by a hook.
- `review_failure`: a hook could not obtain review context.
- `hook_failure`: a hook audit or processing failure.
- `retrieval`: `{"kind":"retrieval","query":"<summary>","read_ids":[...]}`
- `memory-draft`: `{"kind":"memory-draft","draft":"<path>","proposals":[...],"status":"pending-approval|rejected"}`
- `okf-apply`: includes `tier: provisional` for autonomous applies.
- `learning-candidate`: a sanitized failure-to-recovery learning capture.
- `skill-used`: `{"kind":"skill-used","skill":"<name>","source":"tool|path"}`.
- `blocked`: `{"kind":"blocked","check_id":"<HARD_BLOCK>","summary":"<sanitized, max 200 chars>","tool_name":"<name>"}`.
- `outcome`: `{"kind":"outcome","status":"pass|fail|unverified","source":"verify|human","results":[...]}`.
- `recurrence`: `{"kind":"recurrence","concept_id":"...","matched":"..."}`.

Hooks are the standard automatic capture layer for Claude Code and Codex. `loopeng okf apply --run <id>` and `loopeng journal add` remain CLI paths for explicit/headless use. `audit run` writes the next-turn handoff with `source_turn_id`, `goal`, `summary`, `alerts_summary`, and `generated_at`.

フックから注入するエージェント可視メッセージには `[loopeng-bootstrap v{VERSION} | loopeng/v0.2 | {EVENT}]` 形式のバナーを付ける。
