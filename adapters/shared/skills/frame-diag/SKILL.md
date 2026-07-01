---
name: frame-diag
description: "Human diagnostic frame for evidence-based triage, competing hypotheses, and safest next action."
user-invocable: true
---

## Purpose

Diagnostic frame for people who need to understand a failure before changing anything.
Use it to separate observations from interpretations, compare plausible causes, and choose the next safest check.

This frame is for human use. It does not imply a hook, a router, or an agent-only execution mode.

## When to use

- The symptom is unclear or intermittent
- Several causes remain plausible
- You need a bounded diagnosis before deciding on remediation
- You want a shared incident note or troubleshooting brief

## Workflow

1. Restate the symptom, affected scope, and time boundary.
2. List confirmed observations separately from inferences.
3. Name the missing evidence that would discriminate between causes.
4. Generate 2 to 4 competing hypotheses.
5. Rank hypotheses by explanatory power and prior plausibility.
6. Choose the next read-only check that best separates the top hypotheses.
7. State residual uncertainty and the safest next action.

## Output structure

- Symptom and scope
- Confirmed observations
- Competing hypotheses
- Evidence gaps
- Most likely causal chain
- Residual uncertainty
- Risk and blast radius
- Recommended next safe action

## Constraints

- Do not present hypotheses as facts
- Do not jump directly to remediation
- Prefer the smallest check that separates causes
- Stop if the next step would require destructive or privileged action

