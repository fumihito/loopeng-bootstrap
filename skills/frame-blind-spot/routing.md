# Routing hints

```route-hints-v1
schema = "routing-hints/v1"
frame = "frame-blind-spot"
priority = 80
summary = "Choose this when you are looking for what is being assumed, avoided, or left unsaid rather than a claim that can already be tested."

[[prefer]]
phrase = "implicit assumption scan"
aliases = ["見落とし", "思い込み", "無意識の前提"]
weight = 4

[[avoid]]
phrase = "claim testing"
aliases = ["主張は正しいか", "検証"]
weight = -4

[[good_for]]
phrase = "hidden commitment analysis"
aliases = ["反復", "回避"]
weight = 2

[[bad_for]]
phrase = "inherited judgment audit"
aliases = ["前例", "惰性"]
weight = -2

[[signals]]
phrase = "見落とし"
weight = 1

[[signals]]
phrase = "思い込み"
weight = 1
```
