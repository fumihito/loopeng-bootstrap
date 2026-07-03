# Routing hints

```route-hints-v1
schema = "routing-hints/v1"
frame = "frame-proofread-ja"
priority = 70
summary = "Choose this when the issue is sentence-level Japanese quality, not argument validity or planning."

[[prefer]]
phrase = "Japanese proofreading"
aliases = ["文章校正", "日本語", "読みやすさ"]
weight = 4

[[avoid]]
phrase = "claim testing"
aliases = ["主張は正しいか", "検証"]
weight = -4

[[good_for]]
phrase = "AI-smell"
aliases = ["spelling", "particle usage", "structure"]
weight = 2

[[bad_for]]
phrase = "technical decomposition"
aliases = ["planning", "diagnosis"]
weight = -2

[[signals]]
phrase = "日本語"
weight = 1

[[signals]]
phrase = "文章校正"
weight = 1
```
