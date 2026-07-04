# Routing hints

```route-hints-v1
schema = "routing-hints/v1"
frame = "frame-diag"
priority = 90
summary = "Choose this when a live incident needs symptom diagnosis, stabilization, and the next safest check."

[[prefer]]
phrase = "live incident diagnosis"
aliases = ["落ちた", "エラーが出る", "動かない"]
weight = 4

[[avoid]]
phrase = "distributed incident triage"
aliases = ["たまに落ちる", "二重に起きる"]
weight = -4

[[good_for]]
phrase = "stabilize the failure"
aliases = ["復旧", "切り分け", "最小の確認"]
weight = 2

[[bad_for]]
phrase = "post-incident redesign"
aliases = ["振り返り", "再発防止"]
weight = -2

[[signals]]
phrase = "落ちる"
weight = 1

[[signals]]
phrase = "止まる"
weight = 1
```
