---
name: frame-research-arch
description: "Narrow architecture options and their selection conditions. Use when the problem is design choice, not source comparison or probing. The point is to compare tradeoffs before choosing a direction."
user-invocable: true
---

## Purpose

Use this frame when the task is narrowing design options and their conditions. It compares architecture choices, tradeoffs, and fit for the situation.

It stays on the design-choice side of the line. If the question is whether to commit, phase, or compress an existing plan, use a planning or decision frame instead.

## When to use

- You need to choose between design options
- The main question is selection conditions, not evidence gathering
- A probe is not the right next move

## When NOT to use

- The task is to compare published sources or other evidence -> `frame-research`
- The next step is a bounded live probe -> `frame-experiments`
- The real question is whether to commit or revisit a commitment -> `frame-decision-making`
- The work is already a chosen delivery path that needs phasing -> `frame-plandev`

## Workflow

1. List the candidate options.
2. Compare their tradeoffs.
3. State the conditions where each option wins.
4. Identify the decision that still needs evidence.
5. Note the safest next step.

## Design notes

- Keep the focus on option narrowing, not implementation
- Make the conditions for choice explicit
- Keep the tradeoff surface visible
- Keep the option set small enough to compare without flattening the decision

## Output

- Option set
- Tradeoffs
- Selection conditions
- Recommendation
- Residual uncertainty

## Exit

End when the choice space is narrowed enough to compare or commit. If a bounded probe is still required, hand off instead of forcing a choice.

## Adjacent frames

- Use `frame-research` when the design choice still needs source-backed comparison.
- Use `frame-decision-making` when the design choice has become a commitment question.
- Use `frame-research-tactics` when the architecture choice needs hypothesis and verification planning.
- Use `frame-experiments` when the choice can only be separated by a bounded live probe.
