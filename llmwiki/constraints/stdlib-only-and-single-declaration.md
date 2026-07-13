---
type: "Constraint"
title: "Stdlib only and single declaration"
description: "Keep runtime dependencies and policy declarations centralized."
tags: ["architecture", "policy"]
timestamp: "2026-07-13T00:00:00Z"
status: active
sensitivity: internal
authority: "user"
confidence: 0.7
tier: provisional
---

# Summary
Use the standard library and one declaration point for each policy fact.

# Invalidation Conditions
Reconsider when a required safe capability cannot use the standard library.
