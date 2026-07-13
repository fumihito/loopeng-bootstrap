---
type: "Failure Pattern"
title: "Spec prose overrides sample"
description: "Spec prose overrides sample"
tags: ["specification", "semantics", "review"]
timestamp: "2026-07-13T05:08:57.805946+00:00"
status: active
sensitivity: internal
authority: "user"
confidence: 0.7
---

# Summary
When specification prose and its sample conflict, implementation should follow the governing rule expressed by the prose or executable semantics.

# Evidence
Examples are illustrations and can omit boundary conditions. A rule, pseudo-code definition, or explicit invariant carries the semantic obligation; review should identify and resolve a contradiction instead of silently treating the sample as authority.

# Applicability
Use during design and code review when examples and normative clauses disagree.

# Invalidation Conditions
Rewrite this pattern if a controlled review record shows that sample-first interpretation is the explicitly governed convention for the affected specification family.

# Decision Log
Make the semantic core executable or pseudo-code precise before implementation.

# Citations
SA-WP9 initial memory seed; review-dag Z1 finding.

