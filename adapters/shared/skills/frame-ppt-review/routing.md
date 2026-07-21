# Routing hints

```route-hints-v1
schema = "routing-hints/v1"
frame = "frame-ppt-review"
priority = 85
summary = "Choose this when a presentation draft needs a decision-readiness gap review before design, rewriting, or executive review."

[[prefer]]
phrase = "presentation foundation review"
aliases = ["プレゼンの不足要素", "資料の抜け漏れ", "意思決定に足りるか"]
weight = 4

[[avoid]]
phrase = "visual slide design"
aliases = ["見栄え", "レイアウト", "デザイン改善"]
weight = -4

[[avoid]]
phrase = "sentence-level proofreading"
aliases = ["文章校正", "てにをは", "表記ゆれ"]
weight = -4

[[good_for]]
phrase = "decision readiness gaps"
aliases = ["Who What Why", "費用対効果", "工数根拠", "目的 状況 手段 結果"]
weight = 2

[[bad_for]]
phrase = "implementation planning"
aliases = ["実行計画", "タスク分解", "ロードマップ作成"]
weight = -2

[[signals]]
phrase = "PowerPoint"
aliases = ["pptx", "Marp", "スライド"]
weight = 1

[[signals]]
phrase = "missing elements"
aliases = ["不足", "足りない要素", "土台"]
weight = 1
```
