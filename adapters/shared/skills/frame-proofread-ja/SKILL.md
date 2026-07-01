---
name: frame-proofread-ja
description: "Interactive Japanese proofreading frame with lint, editor review, and AI-smell checks."
user-invocable: true
argument-hint: <filepath>
---

## Purpose

Use this frame to review Japanese Markdown or text.
It is for human editing: spelling, grammar, structure, and AI-smell all get checked, but nothing is auto-written.

## Activation

- User calls `/frame-proofread-ja <filepath>` or `proofread-ja: <filepath>`
- If the path is missing, ask for it before continuing

## Input

- Required: file path
- Optional: `--scope <blog|technical article|report>`

## Workflow

1. Read the file and confirm scope.
2. Run a quick mechanical check if available.
3. Review structure and reader flow.
4. Flag AI-smell patterns and repetition.
5. Summarize findings and offer repair options.

## Review passes

- Pass A: lint for spelling and particle usage
- Pass B: editor review for structure, paragraph logic, and readability
- Pass C: AI-smell review for repetition, weak endings, over-marking, and generic phrasing

If a local checker exists, run it first. If not, review manually.
Do not auto-write changes.

## Output structure

- Lint
- Editor review
- AI-smell
- Total issues
- Suggested fixes

## Constraints

- Do not auto-write changes
- Do not start without a file path
- If a local checker exists, run it first; otherwise review manually
