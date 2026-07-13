---
type: "Failure Pattern"
title: "Process compliance is not spec conformance"
description: "Process compliance is not spec conformance"
tags: ["goodhart", "completion-protocol", "verification"]
timestamp: "2026-07-13T05:08:57.311993+00:00"
status: active
sensitivity: internal
authority: "user"
confidence: 0.7
---

# Summary
Process compliance does not establish conformance to the requested specification.

# Evidence
A run can follow its declared procedure while its implementation, artifact, or acceptance result still diverges from the requirement. The discriminating check is an executable gate operated independently of the implementation claim.

# Applicability
Use when completion is being inferred from process steps, checklists, or a clean-looking change set.

# Invalidation Conditions
Replace this pattern if an independently executed gate is shown to be systematically unable to distinguish process compliance from specification conformance.

# Decision Log
Retain external executable acceptance as a separate evidence source.

# Citations
SA-WP9 initial memory seed; Phase 2 retirement acceptance run.

