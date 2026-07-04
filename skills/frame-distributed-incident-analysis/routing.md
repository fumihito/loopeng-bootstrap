# Routing hints

```route-hints-v1
schema = "routing-hints/v1"
frame = "frame-distributed-incident-analysis"
priority = 95
summary = "Choose this for early triage when timing, retries, duplication, or partial failure suggest a distributed incident."

[[prefer]]
phrase = "distributed incident triage"
aliases = ["たまに落ちる", "タイミングで変わる", "二重に起きる"]
weight = 4

[[avoid]]
phrase = "live incident diagnosis"
aliases = ["症状を追う", "その場しのぎの復旧"]
weight = -4

[[good_for]]
phrase = "parallel failure pattern"
aliases = ["分散", "並行", "片方だけ"]
weight = 2

[[bad_for]]
phrase = "post-incident redesign"
aliases = ["再発防止", "振り返り"]
weight = -2

[[signals]]
phrase = "たまに"
weight = 1

[[signals]]
phrase = "二重"
weight = 1
```
