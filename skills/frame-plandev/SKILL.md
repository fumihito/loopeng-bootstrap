---
name: frame-plandev
description: "Human planning frame for phased delivery, scope control, verification, and handoff."
user-invocable: true
---

## Purpose

Planning frame for multi-step delivery work.
It helps a human turn a request into phases, identify scope and constraints, define verification, and decide what handoff is needed.

This is the human-facing replacement for the old plandev orchestration shape.
Use it to keep delivery work explicit about scope, phase boundaries, verification, blockers, and handoff.
Use `goal` as the single source of truth for current checkpoint, completed phases, open decisions, and next safe action.
If the work is already in flight, recover state from `goal` before re-planning.

## Adjacent frames

- Use `frame-plantask` when the main work is making dependencies and ordering explicit.
- Use `frame-smeac` when the plan already exists and needs compression into a handoffable brief.
- Use `frame-first-principles` when the plan still rests on shaky assumptions that need decomposition first.

## When to use

- You need to plan a change across multiple steps
- The work has design, implementation, verification, and handoff phases
- You need to decide what to do first, what to defer, and what to test
- A decision is missing and should be called out before work starts
- You need a plan that can survive interruption and be resumed later
- The current state is partial and you need to recover a coherent next step from `goal`

## Procedure

1. Define the outcome in one sentence.
2. List scope, non-goals, constraints, and risks.
3. Read `goal` for the current checkpoint and unresolved work.
4. Classify the work size and risk level.
5. Break the work into 3 to 5 phases.
6. For each phase, note inputs, outputs, verification, and the next phase boundary.
7. Identify blocked decisions and required human input.
8. Decide what counts as done and what evidence will prove it.
9. Summarize the handoff for the next person or next turn.

## Planning rules

- Do not treat planning as implementation
- Do not skip verification
- Do not hide unresolved decisions
- If the work spans design and delivery, keep the design assumptions visible
- If a phase cannot start, say why and what input would unblock it
- If the handoff is incomplete, say so explicitly
- If the plan is already underway, identify the last completed phase and the next unfinished one from `goal`
- Keep the distinction between fresh planning and resumption explicit, but let `goal` carry the resumption state

## Output structure

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

## Completion criteria

- The outcome is defined
- The scope is bounded
- Every phase has a verification step
- Blockers are named
- The handoff is explicit
- The current checkpoint is known when resuming work
- `goal` captures the resumption state

## Open decisions

- What still needs a human decision
- What is deliberately deferred
- What would change the plan
- What phase boundary the next turn should start from
- What part of the state belongs in `goal`

## Interaction with companion frames

- Use `frame-smeac` when the plan needs to be compressed into a handoffable brief
- Use `frame-first-principles` when the plan still rests on shaky assumptions
- Use `goal` rather than a separate resume frame for interrupted work
