---
name: frame-research-arch
description: "Explore software architecture options, tradeoffs, and conditions for choosing each option."
user-invocable: true
---

## Purpose

Use this frame when a system design needs architectural options, not a single answer.
It helps compare candidate structures, make tradeoffs explicit, and narrow the choice to the contexts where each option fits.

## Workflow

### Phase 0: Clarify the problem

If key facts are missing, ask once, in one batch, about:

1. system type
2. scale and availability
3. team size and skill set
4. cloud usage and provider
5. existing stack and hard constraints

### Phase 1: Enumerate patterns

List plausible architecture patterns and do not omit obvious candidates.

### Phase 2: Select top options

Score candidates by:

1. requirements fit
2. team fit
3. prior examples
4. change tolerance

Pick at least two viable options.

### Phase 3: Suggest OSS and components

When helpful, suggest standard OSS or middleware and note where each fits or does not fit.

### Phase 4: Check cloud best practices

If cloud use is confirmed, compare against the relevant well-architected guidance and note alignment and drift.

## Notes to preserve from the distilled version

- Do not force a one-answer result when multiple patterns fit different contexts
- Keep the selection criteria explicit: requirements fit, team fit, prior examples, and change tolerance
- Make the choice conditional on context rather than universal
- Do not skip context questions when the setup is incomplete
- Always state the conditions that justify each choice

## Output structure

- Requirements
- Candidate patterns
- Top options
- Conditions for choice
- Tradeoffs
- Residual risks
- OSS / components
- Cloud best-practice check
