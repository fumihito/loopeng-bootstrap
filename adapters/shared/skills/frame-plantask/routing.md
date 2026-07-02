# Routing hints

```route-hints-v1
schema = "routing-hints/v1"
frame = "frame-plantask"
priority = 80
summary = "Design task graphs with dependencies, validation, and handoff points."

[[prefer]]
phrase = "task graph"
aliases = ["workflow DAG", "dependency graph", "explicit ordering"]
weight = 4

[[avoid]]
phrase = "no dependency"
aliases = ["single step", "flat list"]
weight = -4

[[good_for]]
phrase = "workflow validation"
aliases = ["dependency cleanup", "mermaid diagram"]
weight = 2

[[bad_for]]
phrase = "narrative summary"
aliases = ["open-ended analysis", "freeform notes"]
weight = -2

[[signals]]
phrase = "dependency"
weight = 1

[[signals]]
phrase = "validation"
weight = 1
```
