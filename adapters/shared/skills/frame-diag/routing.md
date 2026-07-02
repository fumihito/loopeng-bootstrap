# Routing hints

```route-hints-v1
schema = "routing-hints/v1"
frame = "frame-diag"
priority = 95
summary = "Troubleshoot a failure before changing anything."

[[prefer]]
phrase = "incident diagnosis"
aliases = ["bug triage", "failure triage", "troubleshooting"]
weight = 4

[[avoid]]
phrase = "planning work"
aliases = ["roadmap", "strategy work", "design planning"]
weight = -4

[[good_for]]
phrase = "symptom triage"
aliases = ["reproduce", "rollback", "stabilize"]
weight = 2

[[bad_for]]
phrase = "broad strategy"
aliases = ["brainstorming", "open-ended planning"]
weight = -2

[[signals]]
phrase = "symptom"
weight = 1

[[signals]]
phrase = "rollback"
weight = 1
```
