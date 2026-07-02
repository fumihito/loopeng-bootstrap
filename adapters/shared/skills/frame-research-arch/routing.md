# Routing hints

```route-hints-v1
schema = "routing-hints/v1"
frame = "frame-research-arch"
priority = 85
summary = "Compare architecture options and choose by context."

[[prefer]]
phrase = "architecture questions"
aliases = ["tradeoffs", "multiple patterns", "option narrowing"]
weight = 4

[[avoid]]
phrase = "single obvious fix"
aliases = ["purely local change", "tactical fix"]
weight = -4

[[good_for]]
phrase = "pattern comparison"
aliases = ["conditional recommendations", "team fit"]
weight = 2

[[bad_for]]
phrase = "tactical implementation"
aliases = ["line-by-line code change"]
weight = -2

[[signals]]
phrase = "tradeoff"
weight = 1

[[signals]]
phrase = "option"
weight = 1
```
