---
name: frame-proofread-ja
description: "Polish Japanese prose for clarity, tone, and AI-smell. Use when the issue is surface quality rather than argument validity or planning. The point is to improve the text without changing the underlying intent."
user-invocable: true
---

## Purpose

Use this frame for Japanese surface-quality review. It focuses on wording, rhythm, particle choice, notation, and readability rather than the argument itself.

## When to use

- The text is Japanese and needs polishing
- The main problem is style, not substance
- You need to remove AI-smell while preserving intent

## Workflow

1. Read the whole passage.
2. Check structure, wording, and notation.
3. Flag AI-smell, awkward phrasing, and readability issues.
4. Apply minimal edits that preserve meaning.
5. Verify the text still says the same thing.

## Review passes

- Structure
- Word choice
- Particle usage
- Notation and punctuation
- Tone and register

## AI-smell signals

Pass C で補完するための注意点。

- 言い換えの反復
- 構造的マーカーの過剰
- 受け身逃げ
- 形式的な締め
- 抽象語の多用
- 感情の起伏がない均一文体

## Output

- Issues found
- Minimal edits
- Notes on preserved meaning
- Remaining uncertainty

## Exit

Stop when the prose is readable and the intent is unchanged. If a sentence needs more than surface editing, say so and hand off to a more fitting frame.

## Adjacent frames

- Use `frame-critical-review` when the issue is whether the claim or argument holds, not whether the Japanese reads cleanly.
- Use `frame-smeac` when the text should be compressed into a handoffable brief rather than proofread.
