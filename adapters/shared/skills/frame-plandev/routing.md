# Routing hints

```route-hints-v1
schema = "routing-hints/v1"
frame = "frame-plandev"
priority = 90
summary = "Multi-step delivery work with scope, phases, verification, and handoff."

[[prefer]]
phrase = "multi-step delivery"
aliases = ["phased implementation", "milestone planning", "planning work"]
weight = 4

[[avoid]]
phrase = "one-off question"
aliases = ["simple lookup", "single answer"]
weight = -4

[[good_for]]
phrase = "handoff"
aliases = ["transition", "release planning", "phased implementation"]
weight = 2

[[bad_for]]
phrase = "root cause analysis"
aliases = ["diagnosis", "source-backed research"]
weight = -2

[[signals]]
phrase = "scope"
weight = 1

[[signals]]
phrase = "verification"
weight = 1
```
