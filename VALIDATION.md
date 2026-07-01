# Validation

Version: 15.0.0

## Automated tests

The 45 unit and integration tests were executed in grouped runs because a single discovery run repeatedly rebuilds and reinstalls the package and can exceed the execution limit of the validation environment. All groups passed.

Validated lifecycle behavior:

- Gatekeeper, Loop Brief Assistant, Sensemaker, Governor, State Steward, Watchdog / Recovery, Meta-Evaluator, Learning Auditor, and Memory Curator components install for both Codex and Claude Code.
- Gatekeeper requires the ten-part Loop Brief, including `learning_contract` and `memory_contract`.
- A strict `direct:` prefix selects DIRECT mode before generic SOP routing, bypasses Gatekeeper, remains read-only by default, rejects loop-control roles, and completes without learning or memory promotion.
- Gatekeeper `NEEDS_INPUT` requires `handoff_to_loop_brief_assistant=true`; the hook then activates the read-only Loop Brief Assistant.
- Loop Brief Assistant persists a draft across user turns, rejects READY drafts containing assumptions, and returns complete drafts to Gatekeeper rather than Sensemaker.
- Product mutation is denied before trusted Gatekeeper `READY` and Sensemaker reports.
- Control roles remain read-only.
- State Steward and Meta-Evaluator remain mandatory after mutation.
- State Steward reports require structured learning records, question updates, and memory proposals.
- Meta-Evaluator reports independently classify every memory proposal and provide structured learning and memory assessments.
- Memory Curator may run only after a current-epoch Meta-Evaluator `PASS` with accepted proposals.
- Direct LLM writes to `llmwiki/` are rejected; only the trusted curator report can invoke the deterministic Go transaction.
- Every completed `PASS` loop turn produces a content-minimizing learning observation and rebuilds cross-turn health.
- `learning-audit:` loads `sop-learning-audit`, allows only the read-only Learning Auditor role, and requires its trusted report before the SOP completes.
- Watchdog counts failures without falsely advancing the mutation epoch.

## OKF LLMWiki validation

The tests and manual command checks cover:

- Go standard-library-only build of `okfctl`;
- shell launchers that invoke Go only and contain no Python invocation;
- `init`, `validate`, `reindex`, `put`, `apply-report`, `search`, `show`, `stats`, and `version` command paths;
- UTF-8 Markdown and YAML-frontmatter profile validation;
- root and directory indexes plus append-only bundle log maintenance;
- concept IDs derived from paths;
- complete-bundle validation before commit;
- transaction backup, atomic replacement, and rollback behavior;
- duplicate proposal and concept-operation rejection;
- maximum operation and document-size limits;
- secret-like content rejection;
- direct-write denial by the hook;
- trusted current-epoch curator provenance;
- preservation of an existing `llmwiki/` and existing concepts during installation and reinstallation;
- `--validate-only` checks for the Go source, launchers, memory policy, curator role, skeleton, template, and design documentation.

The producer intentionally accepts a narrow deterministic YAML profile: top-level scalar values and inline scalar lists. It does not claim to implement every valid YAML construct. Consumers are instructed to preserve unknown fields and tolerate broader OKF-valid documents.

## Learning-observability validation

The tests cover:

- stable problem-signature recurrence across turns;
- validated lesson capture;
- explicit learning and OKF-memory retrieval;
- candidate discovery and relevant-knowledge selection;
- explicit prior-learning consideration;
- HELPFUL and HARMFUL reuse assessment;
- recurrence after validated learning;
- question OPEN to ANSWERED lifecycle and resolution rate;
- memory proposal, evaluation, promotion, and commit completion;
- accepted memory that was not committed and memory-commit failures;
- UNKNOWN classification when the observation window is too small;
- UNHEALTHY classification and non-zero CLI exit when harmful reuse, repeated recurrence, or memory-promotion failures exceed policy;
- observations exclude lesson statements, OKF documents, raw session identifiers, prompts, tool input, and command arguments.

The deterministic observer exposes:

- observation coverage;
- knowledge capture and learning reuse rates;
- learning-chain completion and average turns to first reuse;
- memory retrieval coverage and proposal-to-commit completion;
- helpful or harmful reuse, recurrence, and correction;
- unknown references and unassessed reuse;
- stale and orphan lesson counts;
- identifier meaning collisions;
- overdue questions and weighted learning debt;
- evaluation adaptation rate;
- equal-window trend deltas.

## Structural validation

- Python syntax compilation passed for installer, hook, observer, CLI, and tests.
- Go formatting, build, and vet passed for `okfctl`.
- POSIX shell syntax checks passed for the Go launchers.
- All JSON files parse successfully.
- All Codex TOML custom-agent files parse successfully.
- All Claude agent and skill frontmatter is structurally valid.
- Installing twice produces no duplicate managed hook groups.
- Existing unrelated hooks are preserved while older managed hook groups are replaced.
- Fresh install, repeated install, dry run, canonical root-level skills, physical-directory consolidation, exact symlink normalization, conflict handling, and `--validate-only` passed.
- Archive extraction, manifest verification, installation from the extracted archive, Go build, and strict LLMWiki validation passed.

## Telemetry and confidentiality

Custom OTel events retain only platform, role, skill, tool, executable command names, outcomes, durations, aggregate learning-health counts or ratios, and aggregate memory-promotion counts.

The following are excluded:

- prompts and prompt hashes;
- command strings, arguments, options, paths, and environment variables;
- tool input and output;
- problem signatures;
- lesson, question, proposal, and OKF concept identifiers;
- lesson statements and OKF document bodies;
- evidence references and Memory Curator recommendations.

Learning observations replace raw session IDs with a short one-way `session_ref`. Statement bodies are represented only by local SHA-256 digests in content-minimized observation records.

## Product limitation

Codex and Claude Code hooks are guardrails rather than complete security boundaries. Codex does not expose every internal tool path to project hooks. Keep OS or container isolation, IAM, branch protection, required CI checks, and human authority for irreversible actions.

The Learning Observer measures explicit identifiers and lifecycle reports. It deliberately does not use semantic embeddings or raw-content similarity, so semantically equivalent problems with different signatures require Learning Auditor or human review.

The installed environment used for package validation did not contain interactive Codex or Claude Code executables. Host-product end-to-end interaction therefore remains an environment-specific acceptance test.

## Canonical skill identity

The v15 regression suite verifies that:

- only `adapters/shared/skills` exists in the package source;
- fresh installation creates a real `{ROOT}/skills` directory;
- `.agents/skills` and `.claude/skills` store the exact target `../skills/`;
- Codex, Claude Code, and canonical skill paths are the same filesystem object;
- legacy physical platform skill directories are backed up and consolidated;
- unrelated custom skills survive consolidation;
- differing unknown same-path custom files cause a no-mutation failure;
- known package skill variants are replaced by the current shared implementation after backup.

## v15 Loop Brief pattern memory

The v15 suite additionally verifies:

- OKF `Loop Brief Pattern` concepts under `llmwiki/loop-brief-patterns/`;
- deterministic `okfctl match-brief-pattern` ranking;
- no pattern body in matcher output;
- explicit confirmation of pattern-suggested fields;
- Gatekeeper PATTERN_CAPTURE handoff;
- exhaustive Gatekeeper proposal classification;
- read-only Brief Pattern Curator;
- transactional pattern commit through Go `okfctl apply-report`;
- Sensemaker remains blocked until accepted pattern proposals are committed;
- pattern IDs and content remain excluded from OTel.
