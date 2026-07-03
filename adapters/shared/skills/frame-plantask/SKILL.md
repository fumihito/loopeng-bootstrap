---
name: frame-plantask
description: "Human workflow-DAG design frame for task graphs, dependencies, validation, and Mermaid renderings."
user-invocable: true
---

## Purpose

Frame for designing multi-step workflow graphs as a DAG.
Use it when you need to turn a process into named tasks with dependencies, validation steps, and a diagram that can be reviewed by humans.

This is a human planning frame. It does not require a specific executor or workflow engine.

## Adjacent frames

- Use `frame-plandev` when the workflow graph needs phases, verification, and handoff decisions.
- Use `frame-smeac` when the graph is already known and only needs compression into a brief.
- Use `frame-first-principles` when the task graph is still unclear and needs decomposition first.

## When to use

- You are designing a task pipeline
- The order of work matters
- You want to review dependencies before execution
- You need a Mermaid diagram or a task table

## Procedure

1. Capture the task sequence in stable task IDs.
2. Mark dependencies with explicit `needs` edges.
3. Identify inputs and outputs for each task.
4. Remove cycles and undefined dependencies.
5. Check for duplicate outputs and ambiguous ownership.
6. Render a Mermaid DAG for review.
7. Validate that the graph matches the intended process.

## Output structure

- Workflow name
- Task list
- Dependency graph
- Inputs and outputs
- Validation checks
- Mermaid diagram

## Constraints

- Prefer DAGs over implicit ordering
- Keep task IDs stable
- Do not mix source-of-truth spec with generated diagram
