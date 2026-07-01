---
name: frame-distributed-incident-analysis
description: "Early-stage incident triage for distributed or concurrent systems with limited evidence."
user-invocable: true
---

## Purpose

Use this frame when an incident may involve timing, scheduling, stale state, duplicate processing, or partial failure.
The goal is triage first, root cause later.

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

## Output structure

- Symptom and scope
- Observations
- Hypotheses
- Missing evidence
- Axis classification
- Discriminating checks
- Risk level

