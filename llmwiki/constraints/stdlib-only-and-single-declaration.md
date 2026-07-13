---
type: "Constraint"
title: "Stdlib-only and single declaration"
description: "Stdlib-only and single declaration"
tags: ["architecture", "policy", "dependencies"]
timestamp: "2026-07-13T05:08:59.069613+00:00"
status: active
sensitivity: internal
authority: "user"
confidence: 0.7
---

# Summary
The runtime should remain standard-library-only and each policy threshold, pattern, or topology should have one declaration point.

# Evidence
Duplicate declarations drift: one consumer can accept a value another rejects. Central declarations make review, testing, and policy comparison target the same source.

# Applicability
Use for dependency policy, thresholds, command patterns, audit topology, and installer manifests.

# Invalidation Conditions
Reconsider the standard-library constraint only when a required capability cannot be implemented safely with the standard library and the dependency is explicitly accepted.

# Decision Log
Keep policy facts centralized and avoid introducing external runtime dependencies.

# Citations
SA-WP9 initial memory seed; loopeng architecture and audit policy.

