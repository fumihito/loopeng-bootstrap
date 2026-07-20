---
name: frame-experiments
description: "Design small probes for uncertainty. Use when reasoning alone cannot separate the options. The point is to define a reversible intervention, the observation that matters, and the next step."
user-invocable: true
---

## Purpose

Use this frame when the question cannot be settled confidently by reasoning alone. It helps choose the right experiment model, limit blast radius, and define what observation changes the next step.

## When to use

- The answer requires a bounded live probe
- A reversible intervention can separate the options
- You need the observation that changes the next step

## Workflow

1. State the core loop: intervention -> observation -> interpretation -> next intervention.
2. Choose the experiment model.
3. Bound blast radius, reversibility, and timebox.
4. Define the success and failure observations.
5. Decide what to do next if the result is ambiguous.

## Experiment models

- causal-test: isolate one change and compare outcomes
- design-optimization: tune a few interacting factors
- exploratory-probe: learn what matters when the space is unclear

## Domain split

- Clear: best practice
- Complicated: analysis first, then focused test
- Complex: safe-to-fail probe
- Chaotic: stabilize first
- Disorder: classify before acting

## Decision rules

- Complicated: a specialist can probably narrow the choice without a probe
- Complex: use a probe and learn from the result
- Chaotic: stabilize first, then probe later
- Do not expand the probe until the first observation is read

## Output

- Experiment question
- Model
- Intervention
- Blast radius
- Timebox
- Success observation
- Failure observation
- Next step

## Exit

End when the smallest useful probe and its settling observation are clear. If the uncertainty can still be narrowed on paper, hand off to research or tactics instead.
If this session produced a deliverable goal or verification conditions, you can hand it to the autonomous loop (when installed) by stating the request in a plain, prefix-less message.

## Adjacent frames

- Use `frame-research-tactics` when the uncertainty can still be turned into hypotheses and verification on paper.
- Use `frame-research` when the answer may still be settled by comparing external sources or published evidence.
- Use `frame-research-arch` when the uncertainty is about design options rather than intervention design.

## Merged operational contract

Use this six-part procedure: clarify the learning target; choose Clear,
Complicated, Complex, Chaotic, or Disorder; select causal-test,
design-optimization, or exploratory-probe; bound risk and reversibility; define
observations and decision rules; then generate the smallest next step.

For Complicated problems, narrow on paper before probing. For Complex problems,
prefer a safe-to-fail probe. For Chaotic problems, stabilize first. A probe
must state the intervention, blast radius, timebox, success observation,
failure observation, ambiguity rule, and the condition for expanding or
stopping it. Do not widen the intervention before reading the first result.
