# Routing hints

```route-hints-v1
schema = "routing-hints/v1"
frame = "frame-wall"
priority = 88
summary = "Choose this when the user's framing, premises, or problem definition itself needs challenge or reframing."

[[prefer]]
phrase = "壁打ち"
aliases = ["premise challenge", "反論して", "前提を疑って", "甘い点を指摘", "厳しめに見て", "スパーリング", "本当にそれが問題?"]
weight = 4

[[prefer]]
phrase = "framing challenge"
aliases = ["前提再構成", "問題設定", "問い直し"]
weight = 3

[[avoid]]
phrase = "initial decomposition"
aliases = ["何から手を付ける", "分解", "前提整理"]
weight = -4

[[avoid]]
phrase = "claim testing"
aliases = ["主張は正しいか", "検証"]
weight = -4

[[avoid]]
phrase = "implicit assumption scan"
aliases = ["見落とし", "思い込み", "無意識の前提"]
weight = -4

[[avoid]]
phrase = "inherited judgment audit"
aliases = ["今まで通り", "前例", "惰性"]
weight = -4

[[good_for]]
phrase = "double-loop learning"
aliases = ["枠組み", "前提の見直し"]
weight = 2

[[bad_for]]
phrase = "artifact review"
aliases = ["完成文書", "成果物"]
weight = -2

[[signals]]
phrase = "壁打ち"
weight = 1

[[signals]]
phrase = "前提を疑って"
weight = 1
```
