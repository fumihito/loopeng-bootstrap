---
name: frame-distributed-incident-analysis
description: "Triage timing-sensitive incidents with partial failure, retries, or duplication. Use when concurrency, scheduling, or distributed state may matter. The point is to isolate the fastest discriminating checks before root cause work."
user-invocable: true
---

## Purpose

Use this frame when an incident may involve timing, scheduling, stale state, duplicate processing, or partial failure. The goal is triage first, root cause later.

## When to use

- The symptom is intermittent, duplicated, or order-dependent
- Several components may be involved
- You need a fast discriminating check before deeper diagnosis

## Workflow

1. Normalize the incident statement.
2. Separate observations, hypotheses, and missing evidence.
3. Classify the issue on all required axes.
4. Generate 2 to 3 competing hypotheses.
5. Pick the fastest discriminating checks.
6. Rank risk as safety-critical, liveness-critical, or mixed.

## Required axes

- Location
- Failure mode
- Time and ordering
- Broken guarantee

## Pattern prompts

- Half-dead: reachable but not progressing, blocked on GC/I/O/event loop/thread pool, or only healthy from one direction
- Thread-safety: changes with load, timing, retries, logging, parallelism, or scheduler interleaving
- Byzantine-like: consider stale cache, replica lag, replay artifact, read-path inconsistency, or observer bias before calling it arbitrary

## Output

- Symptom and scope
- Observations
- Hypotheses
- Missing evidence
- Axis classification
- Discriminating checks
- Risk level

## Exit

Stop when the fastest separating checks are clear or when the problem should be handed to live diagnosis or redesign. Do not collapse uncertainty prematurely.

## Adjacent frames

- Use `frame-diag` when the incident is live and the next step is symptom diagnosis or stabilization.
- Use `frame-waiwad-grill` when the incident is already contained and the next step is redesigning the conditions from the WAI/WAD gap.
