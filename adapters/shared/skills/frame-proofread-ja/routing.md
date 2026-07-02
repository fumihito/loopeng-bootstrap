# Routing hints

```route-hints-v1
schema = "routing-hints/v1"
frame = "frame-proofread-ja"
priority = 70
summary = "Review Japanese Markdown or text for editing quality."

[[prefer]]
phrase = "Japanese text"
aliases = ["文章校正", "日本語", "proofreading"]
weight = 4

[[avoid]]
phrase = "code change"
aliases = ["implementation", "non-textual task"]
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
