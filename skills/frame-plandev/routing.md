# Routing hints

```route-hints-v1
schema = "routing-hints/v1"
frame = "frame-plandev"
priority = 90
summary = "Choose this when you need a phased delivery plan that includes decisions, verification, and the next handoff."

[[prefer]]
phrase = "phased delivery plan"
aliases = ["段取り", "フェーズ", "リリースまで"]
weight = 4

[[avoid]]
phrase = "dependency DAG design"
aliases = ["依存関係", "順番", "フロー図"]
weight = -4

[[good_for]]
phrase = "delivery checkpoint"
aliases = ["検証", "次の一手"]
weight = 2

[[bad_for]]
phrase = "brief compression"
aliases = ["まとめて渡したい", "引き継ぎ"]
weight = -2

[[signals]]
phrase = "段取り"
weight = 1

[[signals]]
phrase = "フェーズ"
weight = 1
```
