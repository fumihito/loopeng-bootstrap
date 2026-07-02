# Routing hints

```route-hints-v1
schema = "routing-hints/v1"
frame = "frame-waiwad-grill"
priority = 80
summary = "Compare work-as-imagined and work-as-done, then redesign conditions."

[[prefer]]
phrase = "work as imagined"
aliases = ["work as done", "process gap", "retrospective"]
weight = 4

[[avoid]]
phrase = "no process gap"
aliases = ["simple lookup", "proofreading"]
weight = -4

[[good_for]]
phrase = "adaptation chain"
aliases = ["constraint analysis", "redesign"]
weight = 2

[[bad_for]]
phrase = "broad research synthesis"
aliases = ["simple proofreading"]
weight = -2

[[signals]]
phrase = "gap"
weight = 1

[[signals]]
phrase = "redesign"
weight = 1
```
