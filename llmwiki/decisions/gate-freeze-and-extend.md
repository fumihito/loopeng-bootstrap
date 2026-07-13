---
type: "Decision"
title: "Gate freeze and extend"
description: "Gate freeze and extend"
tags: ["acceptance", "gates", "verification"]
timestamp: "2026-07-13T05:08:58.822826+00:00"
status: active
sensitivity: internal
authority: "user"
confidence: 0.7
---

# Summary
Acceptance gates should evolve from a frozen source of truth through explicitly authorized extensions.

# Evidence
An implementation can make a gate pass by changing the gate rather than satisfying the original condition. Separating the frozen baseline from approved extensions preserves comparability across runs and keeps gate authority auditable.

# Applicability
Use when adding acceptance checks to a mature gate suite or when a change proposes to relax an existing check.

# Invalidation Conditions
Revise this decision if an independently governed replacement process demonstrates equivalent historical comparability without a frozen baseline.

# Decision Log
Treat unapproved gate changes as invalid and record authorized extensions separately.

# Citations
SA-WP9 initial memory seed; Phase 1 gate design.

