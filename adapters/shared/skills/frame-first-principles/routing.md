# Routing hints

```route-hints-v1
schema = "routing-hints/v1"
frame = "frame-first-principles"
priority = 90
summary = "Choose this when the work is still underspecified and needs decomposition before any response."

[[prefer]]
phrase = "initial decomposition"
aliases = ["何から手を付ける", "分解", "前提整理"]
weight = 4

[[avoid]]
phrase = "claim testing"
aliases = ["主張は正しいか", "検証"]
weight = -4

[[avoid]]
phrase = "壁打ち"
aliases = ["premise challenge", "前提を疑って"]
weight = -4

[[good_for]]
phrase = "subproblem map"
aliases = ["facts", "constraints"]
weight = 2

[[bad_for]]
phrase = "implicit assumption scan"
aliases = ["見落とし", "思い込み"]
weight = -2

[[signals]]
phrase = "前提"
weight = 1

[[signals]]
phrase = "unknowns"
weight = 1
```
