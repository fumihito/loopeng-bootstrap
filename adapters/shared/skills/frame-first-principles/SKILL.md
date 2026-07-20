---
name: frame-first-principles
description: "Decompose an underspecified task into facts, constraints, assumptions, and subproblems. Use when the question is still too fuzzy to judge another way. The point is to build a stable problem signature before acting."
user-invocable: true
---

## Purpose

Use this frame when the question needs decomposition before any other frame can work well. It builds a stable problem signature from goal, facts, constraints, assumptions, and subproblems.

## When to use

- The work is still underspecified or unstable
- You need to separate facts from assumptions
- The next step depends on a clearer problem statement

## Workflow

1. Restate the goal.
2. List the facts.
3. List the constraints.
4. List the assumptions.
5. Break the task into subproblems.
6. Identify what would change the framing.

## Decomposition contract

- Separate goal, facts, constraints, assumptions, tools, subproblems, and verification
- Do not jump to implementation before the problem is stable
- Keep unresolved unknowns visible

## Replanning triggers

- A hidden assumption fails
- The goal changes
- The problem proves to be better handled by another frame

## Output

- Goal
- Facts
- Constraints
- Assumptions
- Subproblems
- Verification
- Next step

## Exit

Stop when the decomposition is clear enough to hand off, compare, or plan. If the question is still not stable, say what additional information would stabilize it.
If this session produced a deliverable goal or verification conditions, you can hand it to the autonomous loop (when installed) by stating the request in a plain, prefix-less message.

## Adjacent frames

- Use `frame-cynefin` first if the question itself may not be stable.
- Use `frame-wall` when the user's framing itself needs challenge or reframing before decomposition.
- Use `frame-blind-spot` when the main problem is hidden assumptions or avoided alternatives.
- Use `frame-critical-review` when the work has become a claim that can be tested against evidence.
- Use `frame-axis` as the next step once a concrete case exists for a candidate distinction.

## Operational contract

This is the standalone contract for this skill. The adjacent-frame references
above are optional handoffs, not prerequisites or additional instructions.

Decompose in this order: restate the goal, strip inherited assumptions,
identify primitives, then derive constraints, tools, minimal subproblems, and
verification. Keep facts, assumptions, decisions, and unknowns in separate
lists. Do not implement while the problem signature is unstable.

Replan when the goal changes, a key assumption fails, or another frame becomes
more appropriate. The handoff must contain the goal, facts, constraints,
assumptions, primitives, subproblems, verification, and next step.
