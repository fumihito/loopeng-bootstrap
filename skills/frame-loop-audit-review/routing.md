# Routing hints

```route-hints-v1
schema = "routing-hints/v1"
frame = "frame-loop-audit-review"
priority = 95
summary = "Use when an audit export packet needs independent external-agent review."

[[prefer]]
phrase = "audit export packet review"
aliases = ["外部エージェントレビュー", "レビュー packet", "review contract"]
weight = 6

[[good_for]]
phrase = "loop report evidence intake"
aliases = ["D1", "D2", "D3", "D4", "D5"]
weight = 3

[[avoid]]
phrase = "implement a fix"
aliases = ["修正実装", "コード変更"]
weight = -5
```
