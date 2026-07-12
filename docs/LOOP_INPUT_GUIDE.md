# Loop input guide

The human input to a v0.2 autonomous run is a goal plus the evidence and
boundaries needed to decide when that goal is complete. The run starts with a
`run-start` goal event, may declare an `intent` before protected-path work, and
ends with a journaled handoff and Run Report. See [README.md](../README.md) for
the run cycle and [RUN_REPORT.md](RUN_REPORT.md) for the event contract.

## Minimal input

- outcome: the state that must be true at completion;
- scope and non-goals: what may and may not change;
- trusted evidence: tests, checks, runtime observations, or documents;
- stop and escalation conditions: when to stop or return to a human.

## Recommended input

Also state protected boundaries, approval requirements, resource limits,
persistence rules, learning and memory rules, and the next-turn trigger. Keep
these as a short operational contract in `AGENTS.md`, `CLAUDE.md`, or the
repository's `.agent-loop` state rather than as a prescribed sequence of tool
commands.

## Entry modes

Use `review:` for reviewing recorded results and concerns, `review: dag` for a
deterministic loop diagram, and `list:` to inspect the available entry modes.
Other mode words and the canonical Run discipline are maintained in
`AGENTS.md` and `CLAUDE.md`.
