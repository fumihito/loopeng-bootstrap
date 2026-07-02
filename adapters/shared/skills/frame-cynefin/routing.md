# Routing hints

```route-hints-v1
schema = "routing-hints/v1"
frame = "frame-cynefin"
priority = 80
summary = "Classify the domain before choosing a response."

[[prefer]]
phrase = "domain classification"
aliases = ["clear", "complicated", "complex", "chaotic"]
weight = 4

[[avoid]]
phrase = "already clear"
aliases = ["simple enough", "skip classification"]
weight = -4

[[good_for]]
phrase = "frame selection"
aliases = ["decision making", "domain split"]
weight = 2

[[bad_for]]
phrase = "detailed implementation"
aliases = ["research report", "tactical execution"]
weight = -2

[[signals]]
phrase = "complex"
weight = 1

[[signals]]
phrase = "chaotic"
weight = 1
```
