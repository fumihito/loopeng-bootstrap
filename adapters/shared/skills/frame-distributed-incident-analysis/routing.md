# Routing hints

```route-hints-v1
schema = "routing-hints/v1"
frame = "frame-distributed-incident-analysis"
priority = 95
summary = "Triage distributed or concurrent incidents with limited evidence."

[[prefer]]
phrase = "distributed incident"
aliases = ["concurrent incident", "partial failure", "stale state"]
weight = 4

[[avoid]]
phrase = "single-cause bug"
aliases = ["local bug", "isolated defect"]
weight = -4

[[good_for]]
phrase = "competing hypotheses"
aliases = ["early triage", "risk ranking"]
weight = 2

[[bad_for]]
phrase = "documentation task"
aliases = ["long-term planning", "rewrite"]
weight = -2

[[signals]]
phrase = "race"
weight = 1

[[signals]]
phrase = "stale state"
weight = 1
```
