# Routing hints

```route-hints-v1
schema = "routing-hints/v1"
frame = "frame-research-arch"
priority = 80
summary = "Choose this when the task is narrowing design options and their conditions."

[[prefer]]
phrase = "architecture option narrowing"
aliases = ["構成の比較", "アーキテクチャ案", "採用条件"]
weight = 4

[[avoid]]
phrase = "external-source comparison"
aliases = ["一次情報", "比較する"]
weight = -4

[[good_for]]
phrase = "option tradeoff"
aliases = ["team fit", "change tolerance"]
weight = 2

[[bad_for]]
phrase = "safe-to-fail probe"
aliases = ["実介入", "小さく実験"]
weight = -2

[[signals]]
phrase = "構成"
weight = 1

[[signals]]
phrase = "採用"
weight = 1
```
