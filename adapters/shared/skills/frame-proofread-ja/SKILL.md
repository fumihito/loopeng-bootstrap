---
name: frame-proofread-ja
description: "Interactive Japanese proofreading frame with lint, editor review, and AI-smell checks."
user-invocable: true
argument-hint: <filepath>
---

## Purpose

Use this frame to review Japanese Markdown or text.
It is for human editing: spelling, grammar, structure, and AI-smell all get checked, but nothing is auto-written.

If a local checker exists, run it first. If not, perform the review manually.

## Workflow

1. Read the file and confirm scope.
2. Run a quick mechanical check if available.
3. Review structure and reader flow.
4. Flag AI-smell patterns and repetition.
5. Summarize findings and offer repair options.

## Output structure

- Lint
- Editor review
- AI-smell
- Total issues
- Suggested fixes

