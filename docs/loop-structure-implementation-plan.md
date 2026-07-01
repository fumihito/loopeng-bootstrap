# Loop Structure Implementation Plan

## Goal

Close the remaining structural gaps between `docs/loop-structure.mmd` and the runtime implementation.

## Priority 1: Integrator

### What to build

- A concrete `integrator` subagent role contract.
- Hook validation for `integrator` reports.
- A policy gate that requires an Integrator report before product mutation when the autonomous loop is active.

### Why it matters

The current loop has Gatekeeper, Sensemaker, Governor, State Steward, and Meta-Evaluator, but no dedicated merge point for parallel or competing candidate outputs. The Integrator becomes that merge point.

### Acceptance criteria

- `integrator` is accepted as a trusted subagent report.
- Invalid reports are rejected by the hook.
- Mutation is denied until an Integrator report exists when the policy requires it.

## Priority 2: Next-turn handoff

### What to build

- A deterministic next-turn handoff artifact written at turn completion.
- A small scheduler helper that reads the completed turn state and emits the next-turn trigger metadata.
- A persistent scheduler daemon, backed by systemd, that polls the handoff and starts the next trigger when configured.

### Why it matters

The repository currently persists turn state, but it does not expose a concrete scheduler-facing artifact for the next execution.

### Acceptance criteria

- Completed turns emit a `next-turn.json` handoff file.
- The handoff records enough metadata for an external scheduler to start the next turn.
- The helper can read the turn directory and print the next-turn plan.
- The daemon can process ready handoffs once and can be kept alive as a systemd service.

## Priority 3: Documentation alignment

### What to update

- `docs/loop-structure.mmd`
- `docs/loop-structure.svg`
- `docs/loop-structure-gap-report.md`
- `README.md`
- `README.ja.md`

### Acceptance criteria

- The diagram reflects the implemented Integrator and next-turn handoff.
- The gap report no longer claims those pieces are missing.
- The README points to the scheduler daemon and systemd service.

## Priority 4: Verification

### What to test

- Integrator report validation.
- Mutation blocking before Integrator when the policy requires it.
- Next-turn handoff file creation on completion.
- Scheduler helper output.
- Scheduler daemon one-shot processing and trigger command execution.

### Acceptance criteria

- Existing smoke tests continue to pass.
- New tests cover the new role and handoff paths.
- The daemon test covers the systemd-ready scheduler loop.
