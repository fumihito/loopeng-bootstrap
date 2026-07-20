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

- Location: where the fault most likely sits
- Failure mode: what kind of failure is happening
- Time and ordering: when key events happened
- Broken guarantee: what promise may have been violated

## Discipline

- Do not jump to root cause too early.
- Do not confuse observation with inference.
- Do not treat uncertainty as evidence.
- Do not skip time ordering.
- Do not ignore duplicate or stale state.

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

## Merged operational contract

Use this sequence: normalize the incident; split evidence from interpretation;
classify all four axes; generate competing hypotheses; select discriminating
checks; and rank current risk. The axes are location, failure mode, time and
ordering, and broken guarantee.

Use the pattern prompts deliberately: half-dead for reachable-but-stalled
components, thread-safety for load/timing/retry sensitivity, and Byzantine-like
for stale, replayed, inconsistent, or observer-dependent evidence. These are
probes, not diagnoses. Do not skip ordering or collapse partial failure into a
single healthy/unhealthy state.
