# Routing hints

```route-hints-v1
schema = "routing-hints/v1"
frame = "frame-smeac"
priority = 70
summary = "Choose this when the input is already a plan, incident note, or discussion that needs to be compressed into a handoffable brief."

[[prefer]]
phrase = "brief compression"
aliases = ["まとめて渡したい", "引き継ぎ", "要約ブリーフ"]
weight = 4

[[avoid]]
phrase = "phased delivery plan"
aliases = ["段取り", "フェーズ", "リリースまで"]
weight = -4

[[avoid]]
phrase = "commitment decision"
aliases = ["決定", "コミット", "見直し"]
weight = -4

[[good_for]]
phrase = "source reality summary"
aliases = ["状況整理", "要点整理"]
weight = 2

[[bad_for]]
phrase = "dependency DAG design"
aliases = ["依存関係", "順番", "フロー図"]
weight = -2

[[bad_for]]
phrase = "phased delivery checkpoint"
aliases = ["段取り", "フェーズ"]
weight = -2

[[signals]]
phrase = "引き継ぎ"
weight = 1

[[signals]]
phrase = "要約"
weight = 1
```
