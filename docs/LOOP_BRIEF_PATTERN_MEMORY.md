# Loop Brief Pattern Memory

## Purpose

Loop Brief Assistant often encounters recurring operating-contract shapes: the same repository class, risk boundary, evaluation evidence, persistence discipline, stop conditions, or trigger cadence. Re-asking every field wastes user attention, while silently copying a previous brief creates authority and safety errors.

This design stores reusable input patterns in the OKF LLMWiki while preserving explicit human control.

## Knowledge object

A reusable pattern is an OKF concept with:

```text
type: Loop Brief Pattern
concept ID: loop-brief-patterns/<stable-slug>
```

It is not a raw prompt, transcript, completed task, user profile, or blanket permission. It is a reviewed abstraction of a Loop Brief structure.

## Read path

When Loop Brief Assistant is invoked it:

1. reads `llmwiki/loop-brief-patterns/index.md`;
2. runs `okfctl match-brief-pattern` using abstract match keys;
3. opens only active candidate concepts with `okfctl show`;
4. records candidate, relevant, deprecated, and applied pattern IDs;
5. presents any proposed reuse as an explicit confirmation question.

No pattern grants authority by itself.

## Matching keys

The deterministic matcher uses:

- `task_class`;
- `repository_kind`;
- `risk_class`;
- `trigger_kind`.

A pattern value of `*` is a wildcard. Exact matches rank above wildcard matches. Deprecated patterns are excluded.

Semantic judgment remains with Loop Brief Assistant. The matcher narrows candidates; it does not decide applicability.

## Reuse discipline

The following fields always require explicit user confirmation:

- `authority_envelope`;
- `memory_contract`;
- `stop_conditions`;
- `escalation_contract`;
- `trigger_cadence`.

`outcome` and `discovery_scope` are task-specific. A pattern may provide a shape or example, but the current task values must come from the user or current evidence.

`evaluation_contract`, `persistence_contract`, and `learning_contract` may be suggested as candidate defaults when applicability matches. They still cannot become a `READY_FOR_REVIEW` draft until the user confirms them.

## Write path

Loop Brief Assistant never writes LLMWiki directly.

```text
Loop Brief Assistant
  -> pattern proposal
Gatekeeper
  -> accept / reject / challenge every proposal
Brief Pattern Curator
  -> complete OKF documents
okfctl apply-report
  -> validate, backup, reindex, atomically commit
```

A Gatekeeper-accepted proposal is not enough by itself. The curator must remove one-time details, search for duplicates, preserve confirmation requirements, and return a complete OKF document. The deterministic Go transaction performs the write.

## Complete briefs

If Gatekeeper receives an already complete brief and the memory contract explicitly permits input-pattern capture, it may request Loop Brief Assistant in `PATTERN_CAPTURE` mode. The Assistant creates only an abstract proposal and sends it back to Gatekeeper for independent assessment.

If input-pattern capture is not explicitly permitted, no pattern is saved.

## Assistant output

The report contains:

- `interaction_mode`: `CLARIFY` or `PATTERN_CAPTURE`;
- `pattern_retrieval`;
- `pattern_application`;
- `pattern_proposals`.

A pattern-derived field that lacks explicit confirmation is treated as an assumption. Therefore the report cannot be `READY_FOR_REVIEW` while such a field remains unresolved.

## Non-goals

This mechanism does not:

- infer permissions from previous sessions;
- create a behavioral profile of the user;
- store raw prompts or answers;
- automatically choose the most frequent prior brief;
- treat a previously successful pattern as universally safe;
- replace Gatekeeper validation.
