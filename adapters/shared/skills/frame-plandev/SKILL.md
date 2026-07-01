---
name: frame-plandev
description: "Human planning frame for phased delivery, scope control, verification, and handoff."
user-invocable: true
---

## Purpose

Planning frame for multi-step delivery work.
It helps a human turn a request into phases, identify scope and constraints, define verification, and decide what handoff is needed.

This is the human-facing replacement for the old plandev orchestration shape.

## When to use

- You need to plan a change across multiple steps
- The work has design, implementation, verification, and handoff phases
- You need to decide what to do first, what to defer, and what to test

## Procedure

1. Define the outcome in one sentence.
2. List scope, non-goals, constraints, and risks.
3. Break the work into 3 to 5 phases.
4. For each phase, note inputs, outputs, and verification.
5. Identify blocked decisions and required human input.
6. Decide what counts as done and what evidence will prove it.
7. Summarize the handoff for the next person or next turn.

## Output structure

- Goal
- Scope and non-goals
- Constraints and risks
- Phases
- Verification
- Blockers
- Handoff

## Constraints

- Do not treat planning as implementation
- Do not skip verification
- Do not hide unresolved decisions

