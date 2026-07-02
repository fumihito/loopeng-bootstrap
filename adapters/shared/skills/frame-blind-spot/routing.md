# Routing hints

```route-hints-v1
schema = "routing-hints/v1"
frame = "frame-blind-spot"
priority = 70
summary = "Surface hidden assumptions, avoided alternatives, and repeated patterns."

[[prefer]]
phrase = "hidden assumptions"
aliases = ["blind spot", "repeated pattern", "avoided alternatives"]
weight = 4

[[avoid]]
phrase = "factual lookup"
aliases = ["simple lookup", "no reasoning surface"]
weight = -4

[[good_for]]
phrase = "assumption scan"
aliases = ["hidden-commitment analysis", "repetition"]
weight = 2

[[bad_for]]
phrase = "syntax cleanup"
aliases = ["task execution", "implementation"]
weight = -2

[[signals]]
phrase = "assumption"
weight = 1

[[signals]]
phrase = "avoidance"
weight = 1
```
