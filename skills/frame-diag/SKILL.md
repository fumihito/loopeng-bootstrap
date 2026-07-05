---
name: frame-diag
description: "Troubleshoot failures with structured evidence and safe next checks. Use when an incident is active, unclear, or intermittent. The point is to separate symptoms, hypotheses, and stabilization work."
user-invocable: true
---

## Purpose

Diagnostic frame for people who need to understand a failure before changing anything. Use it to separate observations from interpretations, compare plausible causes, and choose the next safest check.

This frame is for human use. It does not imply a hook, a router, or an agent-only execution mode.

This is a troubleshooting mode for incidents, defects, and unexpected behavior. It starts from an unclear picture of what is happening. It uses the medical SOAP model (Subjective / Objective / Assessment / Plan) as its backbone, switching between `Emergency Mode`, which prioritizes urgent stabilization, and `Standard Mode`, which prioritizes root-cause understanding.

## When to use

- The symptom is unclear or intermittent
- Several causes remain plausible
- You need a bounded diagnosis before deciding on remediation
- You want a shared incident note or troubleshooting brief
- The intended workflow and the actual workflow may differ

## Workflow

### Mode selection

Use `diag:` to decide whether to start in `Emergency Mode` or `Standard Mode`.

- `Emergency Mode` is for irreversible risk, cascading failure, or suspected security/data loss.
- `Standard Mode` is for reversible situations where root-cause identification first is better.

### SOAP Framework

#### S — Subjective

Extract the phenomenon, context, scope, reproducibility, and attempts so far. If the picture is incomplete, ask clarifying questions before moving on.

#### O0 — Rescue

Use only in `Emergency Mode`. Collect the minimum objective data needed for containment, isolation, and evidence preservation.

#### O — Objective

Request low-cost, read-only evidence that narrows the hypotheses. Keep location, failure mode, time and ordering, and broken guarantee distinct.

#### A0 — Rescue Survey

Use only in `Emergency Mode`. Identify what must be stopped immediately rather than performing detailed diagnosis.

#### A — Assessment

Run four personas in parallel and keep observations, inferences, and next checks separate. The first classification is provisional and should be revised as evidence appears.

#### P — Plan

In `Emergency Mode`, produce P0 containment first and then move to standard planning. In `Standard Mode`, produce the next safest plan from the generalist perspective.

### Interaction flow

`diag:` -> S -> mode selection -> O0/A0 when needed -> O -> A -> P -> repeat as evidence changes.

## Output

- S — Subjective
- Mode
- O — Objective
- A0 — Rescue Survey
- A — Assessment
- P0 — Immediate Actions
- P — Plan
- Final response structure

## Exit

Ask before proceeding if the cause appears identified and the next step would move from investigation into code changes, configuration changes, or remediation. `diag:` does not perform implementation.
If this session produced a deliverable goal or verification conditions, you can hand it to the autonomous loop (when installed) by stating the request in a plain, prefix-less message.

## Adjacent frames

- Use `frame-distributed-incident-analysis` when timing, duplication, or partial failure across components still needs early triage.
- Use `frame-waiwad-grill` when the incident is already contained and the task is redesigning the conditions rather than diagnosing the live failure.
