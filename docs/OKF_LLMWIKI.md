# OKF LLMWiki

## Purpose

`llmwiki/` is the durable-memory bundle for v0.2. It remains ordinary UTF-8 Markdown with YAML frontmatter, and it is updated only through validated OKF transactions.

## Framework and project spaces

Each repository-local bundle has a semantic space: the bootstrap source tree (identified by `loopeng/__main__.py`, `install.py`, and `utils/phase1_gate.py`) is `framework`; an installed target repository is `project`. Documents written by apply, draft, promote, or reindex carry `space: framework|project`. Queries default to the current space and accept `--space all` (or `framework`/`project`) when cross-space reading is intentional. The `wiki_space_mismatch` audit is a warning that lists mislabeled entries; it does not block cleanup. Stats and efficacy are scoped by space.

The inbox can be processed with `loopeng inbox --tui` or `--interactive`. Both are thin frontends over the existing approval, promotion, review-request, decision, and outcome functions; curses automatically falls back to the line-oriented mode when no TTY or curses support is available. In curses mode, the selected item's detail pager is always visible; `[`/`]` page the detail pane and `d` opens the full pager. Incoming review dimensions show verdict, note, and evidence refs. `x` marks an item, `a` opens the action prompt, and Tab completes/cycles the available action (including `intake` for incoming reviews). For an external review, `review` starts a key-only human-review wizard: choose each dimension with `p/f/u`, choose the overall result with `p/f/b`, and the wizard writes a contract JSON to incoming without opening an editor. Confirm it with `d`, then use `intake`. C-c on the main screen, like `q`/Esc, asks `exit? [y/N]`; press one key, and only `y` exits. Other keys and C-c cancel the confirmation. C-c during command/reason input rejects only that input. After the session, `Run audit now? [Y/n]` is also a one-key prompt on a TTY. If the packet is missing, `g` runs the existing audit export and then opens the generated packet.

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

## Machine-readable mutation log

Successful `okf apply` appends one JSON object per applied operation to `llmwiki/log.jsonl` in the same backup/rollback transaction as document writes, reindexing, and `log.md`. Each v1 row contains `ts`, `action`, `concept_id`, `type`, `namespace`, `tier`, `author`, `run_id`, `proposal_id`, `report`, and `v`. `ts` is the UTC application time; it is distinct from the document frontmatter `timestamp`, which describes authorship. `okf validate` validates every JSONL row and requires `v: 1`; bundles without the file remain valid for backward compatibility. `memory stats` uses this file as its only mutation-statistics source and does not infer historical updates from frontmatter.

`okf query` returns both tiers by default, includes `tier`, and labels provisional results `[provisional]`; `--tier provisional|established` filters them. `RUN_STOP` runs audit first and then invokes the same deterministic `memory curate` command; failures are fail-open and journaled. The Run Report lists applied, pending-approval, and rejected memory work. Review always shows provisional entries as `[PROV]`, oldest first, for asynchronous human promotion. Explicit `promote --establish`/apply is the route from provisional to established; automatic establishment is implemented but disabled by policy (`AUTO_ESTABLISH = False`). `single_author_memory_change` remains active, with provisional self-application reported as info, and `provisional_stagnation` reports entries older than 30 days.
