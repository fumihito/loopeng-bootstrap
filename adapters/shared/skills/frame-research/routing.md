# Routing hints

```route-hints-v1
schema = "routing-hints/v1"
frame = "frame-research"
priority = 85
summary = "Investigate external sources, compare evidence, and synthesize."

[[prefer]]
phrase = "external-source investigation"
aliases = ["primary sources", "comparison", "synthesis"]
weight = 4

[[avoid]]
phrase = "local repository change"
aliases = ["implementation planning", "code editing"]
weight = -4

[[good_for]]
phrase = "primary-source review"
aliases = ["competing interpretations", "practical implications"]
weight = 2

[[bad_for]]
phrase = "speculative design"
aliases = ["ungrounded answer", "no evidence"]
weight = -2

[[signals]]
phrase = "source"
weight = 1

[[signals]]
phrase = "synthesize"
weight = 1
```
