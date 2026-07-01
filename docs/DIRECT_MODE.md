# Direct mode

`direct:` is a reserved leading header for a bounded, non-autonomous interaction that bypasses Gatekeeper.

```text
direct: explain why this test is flaky
```

## Purpose

Direct mode exists for questions, inspection, explanation, and other one-shot work where constructing an autonomous Loop Brief would be disproportionate. It is not a shortcut into the autonomous loop and does not imply delegated authority.

## Routing

`direct:` is recognized before generic SOP header routing. It does not map to `sop-direct` and does not load a skill. The remaining text is handled by the parent coding agent under a dedicated `DIRECT` routing mode.

## Default permissions

Direct mode is read-only by default. It may read repository data and run non-mutating inspection commands, but it may not:

- invoke Gatekeeper, Sensemaker, State Steward, Meta-Evaluator, Memory Curator, or other loop-control roles;
- mutate product files or external systems;
- modify LLMWiki;
- bypass protected-path, destructive-command, high-risk-command, Watchdog, permission, or telemetry controls.

`.agent-loop/direct-policy.json` contains an explicit `allow_mutations` switch. Changing it should be treated as a security decision. Even when enabled, protected paths, high-risk operations, direct LLMWiki writes, and Watchdog controls remain enforced. Direct mutation does not receive the autonomous loop's State Steward, Meta-Evaluator, or memory-promotion guarantees.

## Completion

A read-only direct turn completes as `DIRECT_COMPLETE`. No learning observation or durable-memory promotion is generated, because the turn did not pass through the controlled learning loop.

## Telemetry

The hook emits `agent.loop.direct.started` and `agent.loop.direct.completed`. Prompt text, tool arguments, command arguments, and answer content are not logged.
