# Routing hints

```route-hints-v1
schema = "routing-hints/v1"
frame = "frame-research-tactics"
priority = 85
summary = "Choose this when sources or claims need hypotheses, verification, and falsification steps."

[[prefer]]
phrase = "hypothesis planning"
aliases = ["どう確かめる", "仮説を立てる", "反証"]
weight = 4

[[avoid]]
phrase = "external-source comparison"
aliases = ["一次情報", "比較する"]
weight = -4

[[good_for]]
phrase = "verification design"
aliases = ["検証計画", "反証計画"]
weight = 2

[[bad_for]]
phrase = "safe-to-fail probe"
aliases = ["実介入", "小さく実験"]
weight = -2

[[signals]]
phrase = "仮説"
weight = 1

[[signals]]
phrase = "反証"
weight = 1
```
