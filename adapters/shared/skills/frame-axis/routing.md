# Routing hints

```route-hints-v1
schema = "routing-hints/v1"
frame = "frame-axis"
priority = 86
summary = "Choose this when one overloaded term is carrying several meanings and the disagreement needs independent axes before a decision or metric is set."

[[prefer]]
phrase = "overloaded term"
aliases = ["同じ言葉", "意味が違う", "定義が揺れる", "言葉の分解"]
weight = 4

[[prefer]]
phrase = "independent axes"
aliases = ["軸に分ける", "多面的", "評価軸"]
weight = 3

[[avoid]]
phrase = "initial decomposition"
aliases = ["何から手を付ける", "前提整理", "問題を分解"]
weight = -4

[[avoid]]
phrase = "implicit assumption scan"
aliases = ["見落とし", "思い込み", "隠れた前提"]
weight = -3

[[good_for]]
phrase = "guardrail against Goodhart"
aliases = ["指標の暴走", "評価の副作用", "ガードレール"]
weight = 2

[[bad_for]]
phrase = "single claim review"
aliases = ["主張の正しさ", "証拠の確認", "文書レビュー"]
weight = -2

[[signals]]
phrase = "同じ言葉"
weight = 1

[[signals]]
phrase = "多面的"
weight = 1
```
