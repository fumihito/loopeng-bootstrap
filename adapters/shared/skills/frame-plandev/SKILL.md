---
name: frame-plandev
description: "Build phased delivery plans with decisions, verification, and handoff points. Use when the work needs a sequence, not just a task list. The point is to turn scope into a delivery path with checkpoints."
user-invocable: true
---

## Purpose

Planning frame for multi-step delivery work. It helps a human turn a request into phases, identify scope and constraints, define verification, and decide what handoff is needed.

This is the human-facing replacement for the old plandev orchestration shape. Use it to keep delivery work explicit about scope, phase boundaries, verification, blockers, and handoff.

## When to use

- You need to plan a change across multiple steps
- The work has design, implementation, verification, and handoff phases
- You need to decide what to do first, what to defer, and what to test
- A decision is missing and should be called out before work starts
- You need a plan that can survive interruption and be resumed later

## Workflow

1. Define the outcome in one sentence.
2. List scope, non-goals, constraints, and risks.
3. Break the work into 3 to 5 phases.
4. For each phase, note inputs, outputs, verification, and the next phase boundary.
5. Identify blocked decisions and required human input.
6. Decide what counts as done and what evidence will prove it.
7. Summarize the handoff for the next person or next turn.

## Planning rules

- Do not treat planning as implementation
- Do not skip verification
- Do not hide unresolved decisions
- If the work spans design and delivery, keep the design assumptions visible
- If a phase cannot start, say why and what input would unblock it
- If the handoff is incomplete, say so explicitly

## Output

- Goal
- Scope and non-goals
- Work size
- Constraints and risks
- Phases
- Verification
- Blockers
- Handoff
- Completion criteria
- Open decisions
- Current checkpoint
- Goal state

## Exit

Finish when the outcome is defined, every phase has verification, blockers are named, and the handoff is explicit. If the plan is already underway, identify the current checkpoint from the active brief or turn before continuing.

## Adjacent frames

- Use `frame-plantask` when the main work is making dependencies and ordering explicit.
- Use `frame-smeac` when the plan already exists and needs compression into a handoffable brief.
- Use `frame-first-principles` when the plan still rests on shaky assumptions that need decomposition first.
