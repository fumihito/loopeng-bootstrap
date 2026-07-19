# Tool trace

Tool trace is the pure-observation stream for Claude Code and Codex. It is
separate from the governance journal: trace records do not extend
`loopeng.journal.EVENT_KINDS`, change hard-block decisions, or replace the Run
Report.

## Commands

```bash
python3 -m loopeng trace render --run <run-id>
python3 -m loopeng trace render --all
python3 -m loopeng trace show --run <run-id>
```

The renderer reads `.agent-loop/state/trace/<run-id>.jsonl` and the matching
journal run-start/run-end records. It writes the generated index and per-run
views below `.agent-loop/state/reports/trace/`. The outputs contain no current
time or random value, so identical inputs produce identical bytes.

## JSONL schema

Each record has `schema: 1`, an ISO-8601 UTC `ts`, `run_id`, `platform`,
`tool_name`, `call_ref`, `pairing`, and `paths`. PRE_TOOL records use `phase:
pre`, `input_excerpt`, and a SHA-256 `input_digest`; POST_TOOL records use
`phase: post`, `response_excerpt`, `response_digest`, `tool_success`, and
`duration_ms`. A denied hard block adds `phase: deny` and the exact
`deny_reason`. Excerpts are at most 2000 characters.

Inputs and responses pass through the journal sanitizer before excerpting and
digesting. The digest therefore identifies the sanitized full value, not an
unsanitized secret. Missing correlation IDs use a best-effort same-tool
pairing; concurrent ambiguity and unmatched posts remain explicit with a null
duration.

## Views and boundaries

`index.md` lists runs newest first. A run view contains Summary, Timeline,
Denied, Call details, and Provenance sections. Call detail excerpts are copied
from the stored sanitized records without renderer-side rewriting.

Trace write and render failures are fail-open and are recorded as hook
failures when possible. Codex hooks use a `*` matcher so read tools are
observed; Claude Code already uses a `*` matcher. Trace does not introduce
new deny rules, and generated state is not committed.

This document summarizes D1–D6: separate stream, pre/post best-effort
pairing, sanitize/truncate/digest, explicit deterministic rendering, Codex
matcher coverage, and fail-open boundaries.
