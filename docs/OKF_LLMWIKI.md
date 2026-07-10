# OKF LLMWiki

## Purpose

`llmwiki/` is the durable-memory bundle for v0.2. It remains ordinary UTF-8 Markdown with YAML frontmatter, and it is updated only through validated OKF transactions.

The old multi-role memory pipeline is gone. In v0.2, any agent may prepare a report, but the bundle itself changes only when `python3 -m loopeng okf apply <report.md>` validates and applies the report successfully.

## What belongs here

Persist knowledge only when it is reusable beyond the current turn and has explicit scope, evidence, and invalidation conditions.

Keep out:

- raw prompts or transcripts;
- secrets, tokens, and private keys;
- transient work-in-progress state;
- self-claims without evidence;
- absolute home-directory paths.

## Bundle shape

The bundle keeps the current OKF directory structure:

- `llmwiki/index.md`
- `llmwiki/log.md`
- `llmwiki/concepts/`
- `llmwiki/decisions/`
- `llmwiki/constraints/`
- `llmwiki/failure-patterns/`
- `llmwiki/evaluation-rules/`
- `llmwiki/recovery-patterns/`
- `llmwiki/runbooks/`
- `llmwiki/references/`

The `llmwiki/loop-brief-patterns/` subtree is removed in v0.2.

## Validation rule

The Python CLI is the canonical way to validate and apply OKF reports. The transaction must validate the report, apply it atomically, rebuild indexes, append to `log.md`, and leave the bundle unchanged on failure.

## Role separation

The old Sensemaker / State Steward / Meta-Evaluator / Memory Curator split is no longer enforced as a runtime pipeline. Their useful functions survive as deterministic validation, audit, and alert checks instead.
