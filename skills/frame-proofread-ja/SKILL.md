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

1. Read the whole passage. If it cannot be read, report the error and stop.
2. Run the fast AI-smell pre-check:

   ```bash
   python3 scripts/proofread-ng-check.py <filepath>
   ```

   Preserve its output, including line numbers, categories, and matching text.
   Exit code 0 means below the threshold; exit code 1 means the document is
   over the threshold.

3. Run the following review passes in parallel and wait for all of them to
   finish before integrating the pre-check output:

   - **Pass A — Lint:** Check typos, omissions, and particle usage (`てにをは`).
     Be careful not to over-detect proper names and technical terms.
   - **Pass B — Editor review:** Extract the first sentence of each paragraph
     and assess whether the document's outline is readable from them alone;
     identify paragraphs containing multiple logical points; and flag places
     that feel under-explained, abrupt, or assumption-heavy to an ordinary
     reader.
   - **Pass C — AI-smell completion:** Use contextual analysis only for patterns
     the script is unlikely to catch: repeated paraphrase, excessive headings
     or bullets in a short document, and a uniformly flat style. Do not repeat
     findings already reported by the script.

4. Flag awkward phrasing and readability issues, then propose minimal edits
   that preserve meaning.
5. Verify that the revised text still says the same thing.

## Review passes

- Structure
- Word choice
- Particle usage
- Notation and punctuation
- Tone and register

## AI-smell signals

Pass C で拾う観点。スクリプトとの照合時は、必要に応じて
[references/ai-smell-signals.md](references/ai-smell-signals.md) を参照する。

- 列挙前置き
- 冗長強調
- 受け身逃げ
- 空中の締め
- 言い換えの反復
- 構造的マーカーの過剰
- 反論回避
- 曖昧修飾語
- 接続詞の文頭固定
- 評価定型句
- 形式書き言葉

- 抽象語の多用
- 感情の起伏がない均一文体

## Output

Present an integrated report with these sections:

```text
## Lint（誤字脱字・てにをは）
<Pass A>

---

## 編集者レビュー（構造・論理・読者視点）
<Pass B>

---

## AIくさい表現（スクリプト検出 + AI補完）
<script output>
<Pass C>

---
指摘の合計: Lint X件 / 編集 Y件 / AI-smell Z件
```

If there are no findings in a section, say so explicitly.

After presenting the report, ask which section or finding to address. For each
selected finding, show the original text, the problem, and a proposed revision
in a code block, then ask whether to adopt it, produce another option, or skip
it. Continue until the selected findings are handled, and announce completion.

## Exit

Stop when the prose is readable and the intent is unchanged. If a sentence needs more than surface editing, say so and hand off to a more fitting frame.

Do not write to or overwrite the file automatically. Do not update
the project's decision-memory file, run `./check`, or transition automatically
to `dev:`.

## Adjacent frames

- Use `frame-critical-review` when the issue is whether the claim or argument holds, not whether the Japanese reads cleanly.
- Use `frame-smeac` when the text should be compressed into a handoffable brief rather than proofread.

## Operational contract

This is the standalone contract for this skill. The adjacent-frame references
above are optional handoffs, not prerequisites or additional instructions.

Activation is explicit: use this frame for a Japanese Markdown or plain-text
passage when the user requests `proofread-ja:` or the corresponding command.
The scope may be a blog, technical article, or report, but the default is
public-facing Web prose. If the path is absent or unreadable, ask or report the
error instead of starting with no target.

For the editor pass, list paragraph-opening sentences and judge whether they
show the document's skeleton. Identify paragraphs containing more than one
logical point and flag under-explained, abrupt, or assumption-heavy passages.
For the AI-smell pass, combine script findings with contextual completion and
deduplicate them. Present counts by Lint, editor review, script findings, and
AI completion. Offer each finding as original text, problem, revision, and an
adopt/alternative/skip choice; never write the file automatically.
