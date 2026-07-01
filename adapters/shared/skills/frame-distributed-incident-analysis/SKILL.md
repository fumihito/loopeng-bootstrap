---
name: frame-distributed-incident-analysis
description: "Early-stage incident triage for distributed or concurrent systems with limited evidence."
user-invocable: true
---

## Purpose

Use this frame when an incident may involve timing, scheduling, stale state, duplicate processing, or partial failure.
The goal is triage first, root cause later.

## Core rule

Separate observations, inferences, and next checks.
Do not present hypotheses as facts.

## Required axes

- Location
- Failure mode
- Time and ordering
- Broken guarantee

## Workflow

1. Normalize the incident statement.
2. Separate observations, hypotheses, and missing evidence.
3. Classify the issue on all 4 axes.
4. Generate 2 to 3 competing hypotheses.
5. Pick the fastest discriminating checks.
6. Rank risk as safety-critical, liveness-critical, or mixed.

## Pattern prompts

- Half-dead: reachable but not progressing, heartbeating but not useful, blocked on GC/I/O/event loop/thread pool, or only healthy from one direction
- Thread-safety: changes with load, timing, retries, logging, parallelism, or scheduler interleaving
- Byzantine-like: consider stale cache, replica lag, replay artifact, read-path inconsistency, or observer bias before calling it arbitrary

## Anti-patterns

Apply the anti-pattern list before finalizing a conclusion.

## Style requirements

- Be skeptical and precise
- Prefer "most consistent with" over "is"
- Prefer "need evidence" over "probably"
- Name uncertainty explicitly
- Triage before fix

## Output structure

- Symptom and scope
- Observations
- Hypotheses
- Missing evidence
- Axis classification
- Discriminating checks
- Risk level

