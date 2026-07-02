# Routing hints

```route-hints-v1
schema = "routing-hints/v1"
frame = "frame-inertia"
priority = 70
summary = "Check whether a judgment is inherited from convention or still justified."

[[prefer]]
phrase = "inherited judgment"
aliases = ["authority", "metric fixation", "habit"]
weight = 4

[[avoid]]
phrase = "explicit context"
aliases = ["fresh choice", "new decision"]
weight = -4

[[good_for]]
phrase = "conventional judgment"
aliases = ["still justified", "norms"]
weight = 2

[[bad_for]]
phrase = "implementation task"
aliases = ["direct remediation", "code change"]
weight = -2

[[signals]]
phrase = "always"
weight = 1

[[signals]]
phrase = "should"
weight = 1
```
