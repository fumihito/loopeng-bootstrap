# Routing hints

```route-hints-v1
schema = "routing-hints/v1"
frame = "frame-research-tactics"
priority = 80
summary = "Turn research into hypotheses, verification, and falsification."

[[prefer]]
phrase = "research tactics"
aliases = ["hypotheses", "verification", "falsification"]
weight = 4

[[avoid]]
phrase = "generic summary"
aliases = ["no testable step", "implementation task"]
weight = -4

[[good_for]]
phrase = "framework survey"
aliases = ["top hypotheses", "define checks"]
weight = 2

[[bad_for]]
phrase = "code review"
aliases = ["implementation", "task execution"]
weight = -2

[[signals]]
phrase = "hypothesis"
weight = 1

[[signals]]
phrase = "falsify"
weight = 1
```
