# Routing hints

```route-hints-v1
schema = "routing-hints/v1"
frame = "frame-first-principles"
priority = 90
summary = "Decompose underspecified work before acting."

[[prefer]]
phrase = "underspecified work"
aliases = ["shaky assumptions", "needs decomposition", "unknowns"]
weight = 4

[[avoid]]
phrase = "established checklist"
aliases = ["already planned", "known process"]
weight = -4

[[good_for]]
phrase = "fact assumption separation"
aliases = ["subproblem breakdown", "verification design"]
weight = 2

[[bad_for]]
phrase = "architecture comparison"
aliases = ["source-backed research", "pattern comparison"]
weight = -2

[[signals]]
phrase = "assumptions"
weight = 1

[[signals]]
phrase = "unknowns"
weight = 1
```
