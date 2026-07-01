---
name: sop-diag
description: Mandatory read-only diagnostic SOP for any user input beginning with diag:. Diagnose evidence and causal hypotheses without modifying the system.
---

# SOP: Diagnostic investigation

Use this SOP when the routing hook loads `sop-diag` from a leading `diag:` header.

## Objective

Produce an evidence-based diagnosis. Do not implement a fix, edit files, alter configuration, change external state, or disclose credentials.

## Procedure

1. Restate the observed symptom, affected scope, expected behavior, and known time boundary.
2. Separate direct observations from interpretations and user assumptions.
3. Inventory available evidence and identify missing evidence that would discriminate between causes.
4. Generate multiple causal hypotheses. Include at least one environmental, configuration, dependency, state, and implementation hypothesis when applicable.
5. Rank hypotheses by explanatory power and prior plausibility; do not collapse uncertainty prematurely.
6. Run only read-only, bounded diagnostic checks. Prefer commands that inspect status, logs, versions, configuration shape, and reproducibility without changing state.
7. For each check, state which hypotheses it supports or weakens.
8. Identify the most likely causal chain, residual uncertainty, blast radius, and the safest next action.
9. Stop and request human authorization if diagnosis would require credentials, destructive commands, protected-path changes, production writes, or access outside the approved environment.

## Output

Return a diagnostic report with:

- Symptom and scope
- Confirmed observations
- Competing hypotheses
- Evidence and discriminating tests
- Most likely causal chain and confidence
- Unresolved uncertainty
- Risk and blast radius
- Recommended next safe action

Do not claim root cause unless the evidence distinguishes it from material alternatives.
