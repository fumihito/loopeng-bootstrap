---
name: frame-experiments
description: "Design small experiments for uncertainty using causal tests, DOE loops, and safe-to-fail probes."
user-invocable: true
---

## Purpose

Use this frame when the question cannot be settled confidently by reasoning alone.
It helps choose the right experiment model, limit blast radius, and define what observation changes the next step.

## Core loop

`intervention -> observation -> interpretation -> next intervention`

## Experiment models

- `causal-test`: isolate one change and compare outcomes
- `design-optimization`: tune a few interacting factors
- `exploratory-probe`: learn what matters when the space is unclear

## Domain split

- Complicated: a specialist can probably narrow the answer with good comparison
- Complex: you need probing and learning from the result

## Risk bounding

For every experiment, specify:

- blast radius
- reversibility
- timebox
- cost

## Decision rules

State what will:

- amplify a promising path
- dampen a weak path
- stop the next round

## Workflow

1. State the learning target.
2. Decide whether the problem is Complicated or Complex.
3. Choose the experiment model.
4. Bound risk, reversibility, timebox, and cost.
5. Define observation and decision rules.
6. Decide what will amplify, dampen, or stop the next round.

## Output structure

- Learning target
- Domain
- Experiment model
- Intervention
- Observation
- Decision rule
- Constraints
- Next step

