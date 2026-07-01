# OKF LLMWiki memory system

## 1. Purpose

This package uses Open Knowledge Format (OKF) v0.1 as the durable, version-controlled memory interchange format for coding agents. The bundle lives at `llmwiki/` and is ordinary UTF-8 Markdown with YAML frontmatter.

OKF specifies how knowledge is represented and navigated. It does not establish truth, decide what deserves persistence, resolve contradictions, or define who may write. Those concerns are supplied by the Loop Engineering governance layer.

The memory pipeline is therefore:

```text
Sensemaker retrieval
  -> State Steward proposal
  -> Meta-Evaluator independent assessment
  -> Memory Curator rendering
  -> deterministic Go transaction
  -> OKF validation, indexes, log, backup
```

No Generator, Sensemaker, State Steward, Meta-Evaluator, or Memory Curator may directly edit `llmwiki/` through ordinary tools. The trusted Memory Curator report is applied only by `.agent-loop/bin/okfctl apply-report` from the lifecycle hook.

## 2. What belongs in LLMWiki

Persist knowledge only when it is reusable beyond the current turn and has explicit evidence, scope, invalidation conditions, and authority.

Eligible examples:

- stable architectural concepts;
- accepted decisions and their context;
- non-negotiable constraints;
- recurring failure patterns;
- evaluation rules;
- recovery patterns;
- validated runbooks;
- authoritative references.

Do not persist:

- raw prompts or transcripts;
- raw tool inputs or outputs;
- full command lines or environment variables;
- credentials, tokens, private keys, customer personal data;
- transient progress or work queues;
- unsupported speculation;
- unreviewed agent self-claims;
- absolute home-directory paths.

Runtime state remains under `.agent-loop/runtime/`. Structured but not yet durable learning remains under `.agent-loop/state/learning/`. LLMWiki is the curated durable-memory layer, not an event dump.

## 3. Bundle layout

```text
llmwiki/
  index.md
  log.md
  concepts/
  decisions/
  constraints/
  failure-patterns/
  evaluation-rules/
  recovery-patterns/
  runbooks/
  references/
```

A concept ID is its path relative to `llmwiki/`, without `.md`, for example:

```text
failure-patterns/stale-schema-cache
```

IDs are stable semantic identities. Do not silently reuse an ID for a different claim. Deprecate or supersede the old concept and create a new ID when meaning changes materially.

## 4. Progressive disclosure

Agents must not read the whole Wiki by default.

1. Read `llmwiki/index.md`.
2. Open only relevant subdirectory `index.md` files.
3. Use `okfctl search` for metadata/body matching when needed.
4. Use `okfctl show` only for selected concept IDs.
5. Record candidate, relevant, and deprecated IDs in `memory_retrieval`.

This makes retrieval observable and limits context pollution.

## 5. LLMWiki producer profile

OKF permits extensible YAML frontmatter. The bundled deterministic producer intentionally accepts a narrower profile so writes can be validated using the Go standard library without a hidden parser dependency.

Supported frontmatter syntax:

- top-level scalar fields;
- top-level inline lists such as `["tag-a", "tag-b"]`;
- unknown top-level fields, which remain in the document.

Not accepted by the producer:

- nested YAML mappings;
- block scalar YAML;
- flow maps.

This restriction applies to documents produced through this package. It is not a claim that those forms are invalid OKF. A broader OKF consumer should remain tolerant and preserve unknown fields.

Required frontmatter:

```yaml
type: "Failure Pattern"
title: "Example title"
description: "One-sentence progressive-disclosure description."
tags: ["example"]
timestamp: "2026-07-01T00:00:00Z"
status: "active"
sensitivity: "internal"
authority: "meta-evaluator accepted proposal MP-001"
confidence: "0.90"
```

Required body sections:

```text
# Summary
# Evidence
# Applicability
# Invalidation Conditions
# Decision Log
# Citations
```

External factual claims require citations. Internal evidence should use stable, non-secret references such as test names, issue IDs, commit IDs, or repository-relative paths where policy permits.

## 6. Role disciplines

### Gatekeeper

Gatekeeper requires a `memory_contract` before autonomous execution. It must establish:

- bundle scope;
- eligible knowledge classes;
- excluded and sensitive content;
- acceptable authority and citation sources;
- review and expiry policy;
- who may promote knowledge;
- whether memory promotion is required, optional, or forbidden for the task.

Gatekeeper must not invent permissions or lower confidentiality requirements.

### Sensemaker

Sensemaker retrieves memory before framing the task. It distinguishes:

- retrieval not performed;
- no relevant concept found;
- relevant active concepts;
- deprecated concepts that may explain historical decisions.

It does not treat Wiki content as automatically true. Status, authority, timestamp, evidence, applicability, and invalidation conditions must be considered.

### State Steward

State Steward creates structured `memory_proposals`; it never writes LLMWiki directly. Each proposal must identify the concept ID, action, evidence, citations, scope, invalidation conditions, sensitivity, confidence, and source lessons.

Transient state must remain transient. A successful turn does not by itself justify durable memory.

### Meta-Evaluator

Meta-Evaluator independently classifies every proposal as accepted, rejected, or challenged. It checks:

- evidence sufficiency;
- citation quality;
- duplication and contradiction;
- applicability and invalidation conditions;
- sensitivity and secret exposure;
- whether a concept ID changes meaning;
- whether the proposal is genuinely reusable.

The three classification sets must be disjoint and must cover every State Steward proposal.

### Memory Curator

Memory Curator processes only accepted proposal IDs. It renders complete OKF documents but remains read-only. It may return:

- `COMMIT`: all accepted proposals have complete operations;
- `NO_CHANGES`: no accepted proposal exists;
- `BLOCKED`: conflict, insufficient authority, unsafe content, or unresolved ID semantics prevents promotion.

The curator must preserve useful unknown frontmatter on updates, deprecate instead of delete, and avoid rewriting historical claims without an explicit decision-log entry.

### Learning Auditor

Learning Auditor assesses whether durable memory is being retrieved, promoted, corrected, deprecated, and reused. It must distinguish memory growth from learning. More concepts are not automatically better.

## 7. Deterministic commands

The additional command is implemented in Go. The shell wrappers invoke only Go and native shell utilities; they never invoke Python.

Build or locate the binary:

```bash
.agent-loop/bin/build-okfctl.sh
```

Validate the bundle:

```bash
.agent-loop/bin/okfctl validate --root llmwiki
```

Regenerate progressive-disclosure indexes:

```bash
.agent-loop/bin/okfctl reindex --root llmwiki
```

Search without loading the whole Wiki:

```bash
.agent-loop/bin/okfctl search --root llmwiki --query "schema cache" --limit 10
```

Show one concept:

```bash
.agent-loop/bin/okfctl show --root llmwiki --id failure-patterns/stale-schema-cache
```

Create or update one concept from standard input:

```bash
.agent-loop/bin/okfctl put --root llmwiki --id concepts/example < concept.md
```

The normal agent path does not use `put`; it uses the trusted curator transaction:

```bash
.agent-loop/bin/okfctl apply-report \
  --root llmwiki \
  --report .agent-loop/runtime/turns/<turn>/memory-curator.json \
  --backup-dir .agent-loop/runtime/memory-backups
```

## 8. Transaction and recovery semantics

`apply-report` performs the following sequence:

1. copy the current bundle into a temporary sibling directory;
2. apply all accepted operations there;
3. reject secret-like material and invalid profile documents;
4. update `log.md`;
5. regenerate all `index.md` files;
6. validate the complete bundle;
7. rename the old bundle into the runtime backup area;
8. atomically rename the validated temporary bundle into place;
9. restore the old bundle if the final rename fails.

A partial multi-concept commit is not accepted.

## 9. Security model

The default Wiki admits only `public` and `internal` sensitivity. `restricted` content is rejected. Secret-pattern detection is defense in depth, not a complete data-loss-prevention system.

The Wiki should be protected by normal repository controls:

- filesystem permissions;
- branch protection;
- code review;
- secret scanning;
- repository access control;
- backup and retention policy.

Hook enforcement is not an OS sandbox.

## 10. Operational review

Periodically inspect:

- concepts never retrieved;
- accepted proposals that were not committed;
- commit failures;
- deprecated concepts still selected as active guidance;
- concepts past their review date;
- contradictory concepts;
- concepts without recent evidence;
- high growth with low useful reuse;
- concept-ID semantic collisions.

Run the deterministic learning report and then the independent auditor:

```text
learning-audit: inspect LLMWiki retrieval, promotion, correction, deprecation, and reuse over the last 50 turns
```

## 11. Specification status

This package targets the OKF v0.1 draft available in June 2026. Treat the format version as explicit compatibility data. A future OKF revision may require a migration; do not silently reinterpret existing bundles.

Primary references:

- Google Cloud: Open Knowledge Format announcement
- Google Cloud: Open Knowledge Format v0.1 specification

## Loop Brief Pattern concepts

Reusable operating-contract shapes use type `Loop Brief Pattern` and IDs under `loop-brief-patterns/`. These concepts are deliberately separate from runbooks and decisions because they describe how to elicit and validate a future Loop Brief, not how to execute a task.

Patterns must contain abstract match keys and an explicit reuse policy. They may not store raw prompts, repository-specific secrets, or blanket permissions. See `LOOP_BRIEF_PATTERN_MEMORY.md`.
