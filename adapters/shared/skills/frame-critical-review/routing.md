# Routing hints

```route-hints-v1
schema = "routing-hints/v1"
frame = "frame-critical-review"
priority = 85
summary = "Choose this when there is a claim, source set, or argument that can be checked right now."

[[prefer]]
phrase = "claim testing"
aliases = ["主張は正しいか", "反論", "検証"]
weight = 4

[[avoid]]
phrase = "initial decomposition"
aliases = ["何から手を付ける", "分解"]
weight = -4

[[good_for]]
phrase = "counterargument review"
aliases = ["証拠", "反証"]
weight = 2

[[bad_for]]
phrase = "implicit assumption scan"
aliases = ["見落とし", "無意識の前提"]
weight = -2

[[signals]]
phrase = "主張"
weight = 1

[[signals]]
phrase = "証拠"
weight = 1
```
