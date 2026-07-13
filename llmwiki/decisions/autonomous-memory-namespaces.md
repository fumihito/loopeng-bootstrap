---
type: "Decision"
title: "Autonomous memory namespaces"
description: "Autonomous memory namespaces"
tags: ["memory", "autonomy", "approval"]
timestamp: "2026-07-13T05:08:58.570191+00:00"
status: active
sensitivity: internal
authority: "user"
confidence: 0.7
---

# Summary
Autonomous memory writes are limited to observational namespaces, provisional tier, and bounded operation counts; normative changes require explicit approval.

# Evidence
The apply path distinguishes autonomous and explicitly approved writes. Autonomous writes are restricted to failure-patterns, recovery-patterns, and references, while established knowledge and deprecation remain outside that path.

# Applicability
Use when designing memory automation, proposal promotion, and safeguards around durable knowledge.

# Invalidation Conditions
Revise this decision after one observed provisional-memory error causes incorrect operational guidance, or after the policy gains an independently accepted stronger control.

# Decision Log
Preserve explicit approval for normative memory and keep autonomous writes provisional and bounded.

# Citations
SA-WP9 initial memory seed; loopeng memory policy.

