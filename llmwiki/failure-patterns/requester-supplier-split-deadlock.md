---
type: "Failure Pattern"
title: "Requester-supplier split deadlock"
description: "Requester-supplier split deadlock"
tags: ["migration", "contracts", "verification"]
timestamp: "2026-07-13T05:08:58.050192+00:00"
status: active
sensitivity: internal
authority: "user"
confidence: 0.7
---

# Summary
Separately distributing or removing requester and supplier halves can create a deadlock intermediate state.

# Evidence
The transition where a consumer expects a provider that has already been removed, or where a provider is installed without its contract, can make every next action fail. The gatekeeper-skill absence combined with a retained legacy hook is a representative contract mismatch.

# Applicability
Use for migrations that change both sides of a contract, including skills, hooks, manifests, and adapters.

# Invalidation Conditions
Revise this pattern if an independently verified migration protocol proves that the two halves can be safely staged separately under all supported intermediate states.

# Decision Log
Move or remove contract participants as one tested unit, with a migration detector for old states.

# Citations
SA-WP9 initial memory seed; v0.1 retirement migration analysis.

