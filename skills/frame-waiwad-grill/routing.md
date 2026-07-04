# Routing hints

```route-hints-v1
schema = "routing-hints/v1"
frame = "frame-waiwad-grill"
priority = 75
summary = "Choose this after containment when the task is to redesign the conditions from the WAI/WAD gap."

[[prefer]]
phrase = "post-incident redesign"
aliases = ["振り返り", "再発防止", "ポストモーテム"]
weight = 4

[[avoid]]
phrase = "live incident diagnosis"
aliases = ["落ちた", "障害が進行中"]
weight = -4

[[good_for]]
phrase = "WAI/WAD gap"
aliases = ["条件再設計", "ワークアラウンドの見直し"]
weight = 2

[[bad_for]]
phrase = "distributed incident triage"
aliases = ["たまに落ちる", "並行で壊れる"]
weight = -2

[[signals]]
phrase = "再発防止"
weight = 1

[[signals]]
phrase = "ポストモーテム"
weight = 1
```
