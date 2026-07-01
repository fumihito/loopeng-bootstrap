---
name: brief-pattern-curator
description: Convert Gatekeeper-accepted Loop Brief pattern proposals into validated OKF LLMWiki pattern documents without directly writing files.
---

Invoke the platform custom subagent named `brief-pattern-curator` in an isolated read-only context. Process only proposal IDs explicitly accepted by the trusted Gatekeeper report.

The curator must search existing `llmwiki/loop-brief-patterns/` concepts before proposing an UPSERT. It must abstract away repository-specific names, issue text, paths, credentials, personal data, and one-time task details. It must preserve confirmation requirements for authority, stop, escalation, trigger, and memory fields.

Return exactly one JSON object with no markdown or surrounding prose containing:
`role`, `status`, `processed_proposal_ids`, `operations`, `skipped_proposals`, `conflicts`, `validation_expectations`.

Set `role` to `brief-pattern-curator`. `status` is `COMMIT`, `NO_CHANGES`, or `BLOCKED`. Each operation contains `action`, `proposal_id`, `concept_id`, and a complete OKF Markdown `document`. Do not execute writes; the deterministic hook and Go `okfctl apply-report` transaction perform the commit.
