# Routing hints

```route-hints-v1
schema = "routing-hints/v1"
frame = "frame-experiments"
priority = 75
summary = "Choose this when only a bounded live probe can separate the options."

[[prefer]]
phrase = "safe-to-fail probe"
aliases = ["試してみる", "小さく実験", "プローブ"]
weight = 4

[[avoid]]
phrase = "hypothesis planning"
aliases = ["どう確かめる", "仮説を立てる"]
weight = -4

[[good_for]]
phrase = "blast-radius probe"
aliases = ["timebox", "reversible"]
weight = 2

[[bad_for]]
phrase = "external-source comparison"
aliases = ["一次情報", "文書比較"]
weight = -2

[[signals]]
phrase = "試す"
weight = 1

[[signals]]
phrase = "プローブ"
weight = 1
```
