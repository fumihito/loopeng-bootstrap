---
name: frame-research-tactics
description: "Turn claims into hypotheses and verification steps. Use when evidence exists but needs falsification or confirmation planning. The point is to decide what observation would change the answer."
user-invocable: true
---

## Purpose

Use this frame when sources or claims need hypotheses, verification, and falsification steps. It turns research findings into a checkable plan.

## When to use

- You already have claims or sources
- You need a verification or falsification plan
- The next step is paper-based, not a live probe

## Workflow

1. Restate the claims as hypotheses.
2. List the evidence that would support or refute each one.
3. Rank the checks by information gain and cost.
4. Identify the result that would change the answer.
5. Note whether a live probe is actually required.

## Design notes

- Keep hypotheses explicit and falsifiable
- Make verification conditions concrete
- Preserve the path to a bounded probe when paper checks are not enough
- Keep each hypothesis paired with the observation that would change the answer

## Output

- Hypotheses
- Verification plan
- Falsification plan
- Priority order
- Residual uncertainty

## Exit

Stop when the hypotheses are paired with the checks that would settle them. If the uncertainty requires a live probe, hand off to experiments.
If this session produced a deliverable goal or verification conditions, you can hand it to the autonomous loop (when installed) by stating the request in a plain, prefix-less message.

## Adjacent frames

- Use `frame-research` when the task is still source-backed comparison rather than a verification plan.
- Use `frame-experiments` when the uncertainty has to be resolved by a bounded probe in the world.
- Use `frame-research-arch` when the task is narrowing architecture choices instead of building a test plan.
