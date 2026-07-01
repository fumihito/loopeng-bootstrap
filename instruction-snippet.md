# Agent Loop Protocol

This repository has deterministic loop-control hooks under `.agent-loop/` and an OKF v0.1 durable-memory bundle under `llmwiki/`.

- A strict leading `direct:` prefix selects a bounded Gatekeeper-free direct turn. Direct mode is read-only by default and does not invoke loop-control roles, generate learning observations, or promote durable memory.
- Any other strict leading `<header>:` prefix has precedence over Gatekeeper and loads the matching `sop-<header>` skill in an isolated SOP turn.
- Without `direct:` or an SOP header, the user-facing entry point is Gatekeeper. Route the request to the installed `gatekeeper` role first.
- Gatekeeper must validate explicit `learning_contract` and `memory_contract` fields as part of the normalized Loop Brief.
- Only a trusted Gatekeeper verdict of `READY` may hand off to Sensemaker.
- For `NEEDS_INPUT`, invoke the installed `loop-brief-assistant` role. Before asking, it searches reviewed `Loop Brief Pattern` concepts. Patterns are precedents only; every reused field requires explicit user confirmation. A complete draft returns to Gatekeeper for independent review.
- If a complete brief explicitly permits input-pattern capture, Gatekeeper may request Loop Brief Assistant in `PATTERN_CAPTURE` mode. Gatekeeper must independently classify every proposal. Only Brief Pattern Curator plus deterministic Go `okfctl apply-report` may persist it under `llmwiki/loop-brief-patterns/`.
- For `REJECT`, explain the Gatekeeper's reasons and do not start the autonomous loop.
- Invoke Sensemaker before the first product mutation. It must assign a stable non-secret problem signature, retrieve prior lessons, and progressively retrieve relevant OKF concepts from `llmwiki/index.md` and subindexes.
- Treat LLMWiki as curated evidence, not unquestionable truth. Check status, authority, timestamp, applicability, evidence, citations, and invalidation conditions.
- Treat hook denials as authoritative. Never edit or bypass loop-control files.
- The ten named roles must run as their installed subagents, not in the Generator context.
- After mutations, run State Steward and then Meta-Evaluator before claiming completion. State Steward records structured lessons, question updates, and durable-memory proposals. It must never directly edit `llmwiki/`.
- Meta-Evaluator must independently classify every memory proposal. Accepted, rejected, and challenged proposal-ID sets must be disjoint and exhaustive.
- If Meta-Evaluator accepts durable-memory proposals, invoke Memory Curator. Memory Curator remains read-only and returns complete OKF documents; only the deterministic Go `okfctl apply-report` transaction may write LLMWiki.
- Never place raw prompts, raw tool content, full command arguments, credentials, personal data, transient progress, or unsupported speculation in LLMWiki.
- Use stable concept IDs. Do not silently repurpose an ID; deprecate or supersede concepts when meaning changes.
- Completed PASS turns are summarized by the deterministic learning observer, including memory retrieval and promotion outcomes.
- To audit long-term learning and memory health, use `learning-audit:`. This loads `sop-learning-audit`, rebuilds metrics, and invokes the read-only `learning-auditor`.
- If the Watchdog trips, stop product mutations, run Watchdog / Recovery, and request a human TTY reset.
- Governor is advisory; high-risk actions remain human-executed.
- A Meta-Evaluator verdict of REVISE requires another implementation and evaluation cycle. ESCALATE requires human judgment.

## Memory commands

Use `.agent-loop/bin/okfctl` for read-only retrieval and validation, including `match-brief-pattern` for abstract pattern candidates. The shell wrapper may invoke Go but must never invoke Python. Direct agent mutation of `llmwiki/` is prohibited.

## Telemetry

Lifecycle hooks automatically emit sanitized OTel events. Do not enable detailed tool-input logging. Tool, executable command, role, skill, aggregate learning-health, and aggregate memory-promotion names and counts are observable; arguments, prompts, lesson text, concept IDs, evidence, and content remain excluded.
