# Routing hints

```route-hints-v1
schema = "routing-hints/v1"
frame = "frame-inertia"
priority = 75
summary = "Choose this when the question is whether a decision is being repeated by habit, authority, or metric fixation."

[[prefer]]
phrase = "inherited judgment audit"
aliases = ["今まで通りでいいのか", "前例", "惰性"]
weight = 4

[[avoid]]
phrase = "implicit assumption scan"
aliases = ["見落とし", "思い込み"]
weight = -4

[[avoid]]
phrase = "壁打ち"
aliases = ["premise challenge", "前提を疑って"]
weight = -4

[[good_for]]
phrase = "habit check"
aliases = ["authority", "metric fixation"]
weight = 2

[[bad_for]]
phrase = "claim testing"
aliases = ["主張は正しいか", "検証"]
weight = -2

[[signals]]
phrase = "前例"
weight = 1

[[signals]]
phrase = "惰性"
weight = 1
```
