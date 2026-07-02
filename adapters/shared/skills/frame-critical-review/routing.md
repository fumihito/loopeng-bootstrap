# Routing hints

```route-hints-v1
schema = "routing-hints/v1"
frame = "frame-critical-review"
priority = 75
summary = "Test claims, evidence, and counterarguments in a document or argument."

[[prefer]]
phrase = "claim testing"
aliases = ["source checking", "argument review", "critical review"]
weight = 4

[[avoid]]
phrase = "brainstorming"
aliases = ["no claim to test", "freeform ideation"]
weight = -4

[[good_for]]
phrase = "thesis map"
aliases = ["counterargument", "revision hints"]
weight = 2

[[bad_for]]
phrase = "operational task"
aliases = ["task execution", "implementation"]
weight = -2

[[signals]]
phrase = "evidence"
weight = 1

[[signals]]
phrase = "rebuttal"
weight = 1
```
