# Routing hints

```route-hints-v1
schema = "routing-hints/v1"
frame = "frame-smeac"
priority = 65
summary = "Compress discussion, research, or incident notes into a handoffable brief."

[[prefer]]
phrase = "handoffable brief"
aliases = ["summary", "brief", "incident notes"]
weight = 4

[[avoid]]
phrase = "deep design work"
aliases = ["needs decomposition", "architecture planning"]
weight = -4

[[good_for]]
phrase = "command and signal"
aliases = ["distortion report", "handoff"]
weight = 2

[[bad_for]]
phrase = "root cause analysis"
aliases = ["planning graph", "raw workflow"]
weight = -2

[[signals]]
phrase = "situation"
weight = 1

[[signals]]
phrase = "mission"
weight = 1
```
