# Gatekeeper Protocol

Gatekeeper is the validation authority for starting an autonomous loop. It normally precedes Sensemaker, but it is not the only user-entry mode: `direct:` selects a bounded non-loop interaction, and explicit SOP headers select isolated SOP workflows.

## Why Gatekeeper exists

Sensemaker should reinterpret a valid problem; it should not invent missing authority, decide who owns a value conflict, create acceptance criteria from nothing, or guess how an unattended loop is triggered, stopped, and remembered. Gatekeeper prevents those omissions from becoming hidden assumptions.

Gatekeeper is deliberately not the conversational drafting role. When material conditions are missing, it activates Loop Brief Assistant. This separation prevents the validator from relaxing its own standard merely to complete the brief.

## Required conditions

Gatekeeper evaluates ten fields:

1. Outcome
2. Discovery scope
3. Authority envelope
4. Evaluation contract
5. Persistence contract
6. Learning contract
7. Memory contract
8. Stop conditions
9. Escalation contract
10. Trigger cadence

It also classifies risk, detects irreversible operations and conflicting principals, and decides whether the request is an autonomous loop or advisory-only work.

Gatekeeper output may also include `validation_commands`, but the hook only executes argv arrays that are present in `.agent-loop/policy.json` under `validation_command_allowlist`. Unlisted commands are rejected before execution. `trigger_cadence` must be one of `immediate`, `manual`, `external-user-prompt`, or `on-event:<safe-name>`.

## Verdicts

### READY

All material conditions are sufficiently explicit. Gatekeeper emits a normalized Loop Brief and a handoff to Sensemaker. READY does not mean the proposed implementation is correct; it means the loop has a legitimate, observable, and bounded problem to sensemake.

`handoff_to_loop_brief_assistant` must be false and `handoff_to_sensemaker` must be non-empty.

### NEEDS_INPUT

Material conditions are missing or ambiguous. Gatekeeper identifies the missing conditions and sets `handoff_to_loop_brief_assistant=true`. The hook then starts Loop Brief Assistant, which normalizes the partial brief and asks the smallest useful question set.

Gatekeeper does not itself continue the user dialogue and must not invent placeholder authority, acceptance criteria, learning rules, or memory policy.

Gatekeeper may also include an optional `mode_recommendation` object in `NEEDS_INPUT` when the request looks like a one-shot, read-only, or otherwise non-autonomous task. The object has the shape `{mode, reason}` and is written in user vocabulary. It may point to `direct:`, `route:`, or a matching `frame-<name>:` prefix so the user can rerun the request in a more appropriate mode. This is a hint only; the hook does not auto-route from it.

### REJECT

The requested autonomous loop is structurally unsafe, prohibited, lacks a legitimate decision owner, or requires authority the user cannot delegate. Gatekeeper explains what would need to change; neither Loop Brief Assistant nor Sensemaker is used to circumvent the rejection.

When useful, `REJECT` may also carry `mode_recommendation` to point the user toward a safer explicit mode for rerunning the request. The hint is informational only and does not trigger a routing change.

## Loop Brief Assistant handoff

```text
User request
  -> Gatekeeper
     -> READY: Sensemaker
     -> REJECT: stop
     -> NEEDS_INPUT: Loop Brief Assistant
          -> ASK_USER: user dialogue
          -> READY_FOR_REVIEW: Gatekeeper revalidation
          -> BLOCKED: human resolution
```

Loop Brief Assistant cannot hand directly to Sensemaker. A completed draft always returns to Gatekeeper for independent validation.

## Runtime files

- Current report: `.agent-loop/runtime/turns/<turn>/gatekeeper.json`
- Normalized brief after READY: `.agent-loop/runtime/turns/<turn>/loop-brief.json`
- Prior report copied into a new turn: `.agent-loop/runtime/turns/<turn>/prior-gatekeeper.json`
- Session-level latest report: `.agent-loop/runtime/gatekeeper-sessions/<session>.json`
- Assistant report: `.agent-loop/runtime/turns/<turn>/loop-brief-assistant.json`
- Assistant draft: `.agent-loop/runtime/turns/<turn>/loop-brief-draft.json`

These files are local runtime state and are excluded from Git. Raw prompts and answers are not emitted through OTel.

## User interaction

For autonomous work, the user addresses Gatekeeper with a goal or a partly completed Loop Brief. The parent coding agent must not answer as Generator before Gatekeeper has returned READY.

For a one-shot question that should not enter Gatekeeper, the user may explicitly choose:

```text
direct: explain the current retry logic
```

Direct mode is a separate non-autonomous workflow and is read-only by default.

## Memory contract

Gatekeeper must not return READY without an explicit `memory_contract`. The contract states the OKF bundle scope, eligible durable knowledge, excluded and sensitive content, authority and citation requirements, review and expiry rules, and the actor allowed to promote knowledge. The default promoter is Memory Curator through deterministic `okfctl`; no other role receives direct write authority.

Gatekeeper must not infer that all useful observations belong in durable memory. It preserves the distinction between runtime state, structured learning observations, and curated LLMWiki concepts.

## Loop Brief pattern governance

Gatekeeper also governs whether a completed brief may become a reusable OKF pattern. It never treats a prior pattern as current authority.

Additional output fields:

- `assistant_handoff_reason`: `MISSING_INPUT`, `PATTERN_CAPTURE`, or `NONE`;
- `brief_pattern_directive`: capture action and reason;
- `brief_pattern_assessment`: exhaustive, disjoint accepted/rejected/challenged proposal IDs plus duplicate and correction findings.

A READY brief may temporarily hand back to Loop Brief Assistant only for PATTERN_CAPTURE. During that phase it must not hand off to Sensemaker. After Assistant returns a proposal, Gatekeeper performs a second independent review. Accepted proposals must be committed by Brief Pattern Curator before Sensemaker starts.

## When does the loop actually run?

Use this checklist when a request seems complete on paper but still does not start the autonomous loop.

- A READY Loop Brief exists from Gatekeeper.
- `trigger_cadence` permits automatic execution for the current profile.
- The scheduler daemon is running.
- `trigger_command` is configured and has been validated with the dry-run path.
- A notification path exists for non-PASS outcomes.

See `docs/SCHEDULER.md` for the scheduler daemon and command behavior. That document explains the execution path; it does not repeat this checklist.
