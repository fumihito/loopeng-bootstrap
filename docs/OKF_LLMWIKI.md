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

## Draft and approval pipeline

`learning promote` and `okf draft` create validated JSON reports under `.agent-loop/state/memory-drafts/`. Autonomous `memory curate` may apply only bounded `UPSERT` operations in `failure-patterns`, `recovery-patterns`, and `references`, at most three per run, and every such document is `tier: provisional`. Normative namespaces and established overwrites remain explicit-user-only; concepts are excluded by default. `tier` is optional for legacy documents and defaults to `established`.

`okf query` returns both tiers by default, includes `tier`, and labels provisional results `[provisional]`; `--tier provisional|established` filters them. `RUN_STOP` runs audit first and then invokes the same deterministic `memory curate` command; failures are fail-open and journaled. The Run Report lists applied, pending-approval, and rejected memory work. Review always shows provisional entries as `[PROV]`, oldest first, for asynchronous human promotion. Explicit `promote --establish`/apply is the route from provisional to established; automatic establishment is implemented but disabled by policy (`AUTO_ESTABLISH = False`). `single_author_memory_change` remains active, with provisional self-application reported as info, and `provisional_stagnation` reports entries older than 30 days.
