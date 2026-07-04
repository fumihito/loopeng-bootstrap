# Routing hints

```route-hints-v1
schema = "routing-hints/v1"
frame = "frame-plantask"
priority = 80
summary = "Choose this when the task is mainly to make dependencies, order, and validation steps explicit."

[[prefer]]
phrase = "dependency DAG design"
aliases = ["依存関係", "順番", "フロー図"]
weight = 4

[[avoid]]
phrase = "phased delivery plan"
aliases = ["段取り", "フェーズ", "リリースまで"]
weight = -4

[[good_for]]
phrase = "workflow validation"
aliases = ["依存の整理", "Mermaid"]
weight = 2

[[bad_for]]
phrase = "brief compression"
aliases = ["まとめて渡したい", "引き継ぎ"]
weight = -2

[[signals]]
phrase = "依存関係"
weight = 1

[[signals]]
phrase = "順番"
weight = 1
```
