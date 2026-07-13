---
type: "Decision"
title: "Alert, not block, scope"
description: "Alert, not block, scope"
tags: ["goodhart", "audit-policy", "alerts"]
timestamp: "2026-07-13T05:08:58.320162+00:00"
status: active
sensitivity: internal
authority: "user"
confidence: 0.7
---

# Summary
Alerts should remain observable without expanding hard blocking beyond the narrowly defined catastrophic cases.

# Evidence
The audit policy reserves hard blocks for four categories; other findings are emitted in Run Reports with severity and evidence. This preserves visibility while allowing reversible work to proceed under review.

# Applicability
Use when deciding whether a new detector should stop execution or report a finding.

# Invalidation Conditions
Reconsider this boundary after a concrete incident shows that reporting alone cannot prevent compounding harm for the detector in question.

# Decision Log
Keep the hard-block set small and treat new blocking authority as an explicit policy decision.

# Citations
SA-WP9 initial memory seed; loopeng audit policy.

