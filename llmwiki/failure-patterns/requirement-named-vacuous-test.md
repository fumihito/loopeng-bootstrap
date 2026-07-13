---
type: "Failure Pattern"
title: "Requirement-named vacuous test"
description: "Requirement-named vacuous test"
tags: ["completion-protocol", "testing", "verification"]
timestamp: "2026-07-13T05:08:57.560330+00:00"
status: active
sensitivity: internal
authority: "user"
confidence: 0.7
---

# Summary
A test named after a requirement can be vacuous if its assertion does not bind to the concrete requirement object.

# Evidence
Requirement coverage is meaningful only when each acceptance assertion targets a concrete artifact, behavior, or invariant named by the requirement. A passing test whose assertion can remain true after the target is removed is not evidence of coverage.

# Applicability
Review tests that claim to cover requirements, especially tests using broad snapshots, existence-only checks, or constant truth values.

# Invalidation Conditions
Revise this pattern if a formal coverage method demonstrates that name-based tests without one-to-one target binding reliably detect the required behavior.

# Decision Log
Require a one-to-one mapping from requirement claim to assertion target.

# Citations
SA-WP9 initial memory seed; requirement acceptance review notes.

