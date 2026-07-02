# Routing hints

```route-hints-v1
schema = "routing-hints/v1"
frame = "frame-experiments"
priority = 80
summary = "Design small safe-to-fail experiments for uncertainty."

[[prefer]]
phrase = "small probe"
aliases = ["safe-to-fail", "causal test", "experimentation"]
weight = 4

[[avoid]]
phrase = "immediate deterministic action"
aliases = ["just do it", "no learning needed"]
weight = -4

[[good_for]]
phrase = "decision rule"
aliases = ["blast radius", "reversibility", "timebox"]
weight = 2

[[bad_for]]
phrase = "pure explanation"
aliases = ["summary only", "no action plan"]
weight = -2

[[signals]]
phrase = "probe"
weight = 1

[[signals]]
phrase = "falsify"
weight = 1
```
