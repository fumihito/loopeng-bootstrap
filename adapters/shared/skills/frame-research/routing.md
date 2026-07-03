# Routing hints

```route-hints-v1
schema = "routing-hints/v1"
frame = "frame-research"
priority = 90
summary = "Choose this when the evidence comes from external sources and the task is comparison or synthesis."

[[prefer]]
phrase = "external-source comparison"
aliases = ["一次情報", "比較する", "根拠を集める"]
weight = 4

[[avoid]]
phrase = "hypothesis planning"
aliases = ["どう確かめる", "反証計画"]
weight = -4

[[avoid]]
phrase = "architecture option narrowing"
aliases = ["構成の比較", "アーキテクチャ案", "採用条件"]
weight = -4

[[good_for]]
phrase = "source-backed synthesis"
aliases = ["公開情報", "文書比較"]
weight = 2

[[bad_for]]
phrase = "safe-to-fail probe"
aliases = ["実介入", "小さく実験"]
weight = -2

[[signals]]
phrase = "一次情報"
weight = 1

[[signals]]
phrase = "比較"
weight = 1
```
