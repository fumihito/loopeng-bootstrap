---
name: frame-plantask
description: "Turn a workflow into an explicit dependency graph. Use when order, blockers, and validation steps are the main design problem. The point is to make execution dependencies visible before committing to a plan."
user-invocable: true
---

## Purpose

Use this frame when the task is mainly to make dependencies, order, and validation steps explicit. It turns a rough task list into a dependency-aware workflow graph.

## When to use

- The main question is what depends on what
- You need to expose blockers and ordering
- Validation steps must be placed before execution

## Workflow

1. List the nodes.
2. Draw the edges.
3. Identify blockers and validation gates.
4. Collapse duplicate or unnecessary steps.
5. Check whether the graph supports delivery.

## Constraints

- Do not confuse dependency design with phase planning
- Do not lose validation steps while simplifying the graph
- Keep the graph small enough to inspect

## Output

- Nodes
- Edges
- Blockers
- Validation gates
- Suggested order
- Residual uncertainty

## Exit

Stop when the dependency structure is explicit enough to hand off or turn into phases. If the graph is still unstable, say what node or edge is missing.

## Adjacent frames

- Use `frame-plandev` when the workflow graph needs phases, verification, and handoff decisions.
- Use `frame-smeac` when the graph is already known and only needs compression into a brief.
- Use `frame-first-principles` when the task graph is still unclear and needs decomposition first.
