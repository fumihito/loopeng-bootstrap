# Routing hints

```route-hints-v1
schema = "routing-hints/v1"
frame = "frame-cynefin"
priority = 88
summary = "Choose this when you need to classify the domain before deciding which other frame should handle it."

[[prefer]]
phrase = "domain classification"
aliases = ["どう扱えばいい問題か", "分類", "複雑性"]
weight = 4

[[avoid]]
phrase = "already clear"
aliases = ["simple enough", "skip classification"]
weight = -4

[[good_for]]
phrase = "frame selection"
aliases = ["decision making", "domain split"]
weight = 2

[[bad_for]]
phrase = "detailed implementation"
aliases = ["research report", "tactical execution"]
weight = -2

[[signals]]
phrase = "複雑"
weight = 1

[[signals]]
phrase = "混沌"
weight = 1
```
