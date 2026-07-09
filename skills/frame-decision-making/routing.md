# Routing hints

```route-hints-v1
schema = "routing-hints/v1"
frame = "frame-decision-making"
priority = 85
summary = "Choose this when a commitment must be made or revisited under scarce resources, with dry facts, modal scoring, and pre-committed decision points."

[[prefer]]
phrase = "commitment decision"
aliases = ["決定", "コミット", "見直し"]
weight = 4

[[avoid]]
phrase = "phased delivery plan"
aliases = ["段取り", "フェーズ", "リリースまで"]
weight = -4

[[avoid]]
phrase = "dependency DAG design"
aliases = ["依存関係", "順番", "フロー図"]
weight = -4

[[avoid]]
phrase = "brief compression"
aliases = ["まとめて渡したい", "引き継ぎ"]
weight = -4

[[good_for]]
phrase = "tripwire"
aliases = ["見直し条件", "再検討", "分岐点"]
weight = 2

[[signals]]
phrase = "決める"
weight = 1

[[signals]]
phrase = "見直す"
weight = 1

[[signals]]
phrase = "will can must"
aliases = ["will / can / must"]
weight = 1
```
