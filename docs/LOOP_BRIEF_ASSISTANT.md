# Loop Brief Assistant

Loop Brief Assistant is a read-only clarification role activated when Gatekeeper returns `NEEDS_INPUT`. Gatekeeper remains the authority that decides whether a Loop Brief is valid; the Assistant only conducts the dialogue needed to make the user's intended contract explicit.

## Why it is separate from Gatekeeper

Gatekeeper is a validator and boundary decision point. Combining validation with a conversational drafting role creates pressure to fill gaps merely to reach `READY`. The Assistant instead optimizes for elicitation, normalization, and traceability, while Gatekeeper independently rechecks the resulting draft.

## State machine

```text
Normal user request
  -> Gatekeeper
     -> READY: Sensemaker
     -> REJECT: stop
     -> NEEDS_INPUT: Loop Brief Assistant
          -> ASK_USER: ask the user and persist the draft
          -> READY_FOR_REVIEW: return the draft to Gatekeeper
          -> BLOCKED: stop for human resolution
```

When the Assistant returns `ASK_USER`, the session stores its latest trusted draft. The next ordinary user message in that session is treated as an answer to the outstanding questions and enters the Assistant before Gatekeeper. Prefixing the new prompt with `direct:` or another SOP header starts that explicitly selected mode instead.

## Non-invention discipline

The Assistant must not invent or silently infer:

- authority or permission;
- forbidden and approval-required actions;
- acceptance criteria;
- persistence, learning, or memory policy;
- stop and escalation ownership;
- trigger cadence;
- value judgments or legitimate decision owners.

It may normalize wording, combine duplicate statements, and structure explicit user answers. Any tentative interpretation must remain in `assumptions`; a draft with assumptions cannot be `READY_FOR_REVIEW`.

## Runtime files

- Current report: `.agent-loop/runtime/turns/<turn>/loop-brief-assistant.json`
- Draft: `.agent-loop/runtime/turns/<turn>/loop-brief-draft.json`
- Prior report: `.agent-loop/runtime/turns/<turn>/prior-loop-brief-assistant.json`
- Session state: `.agent-loop/runtime/loop-brief-assistant-sessions/<session>.json`

These files are runtime state and are excluded from Git.

## Output states

- `ASK_USER`: minimal questions are returned to the user.
- `READY_FOR_REVIEW`: the hook asks Gatekeeper to validate the draft.
- `BLOCKED`: the hook stops and reports the conflicts requiring human resolution.

The Assistant never hands directly to Sensemaker.

## LLMWiki pattern retrieval and capture

The Assistant reads reviewed OKF concepts under `llmwiki/loop-brief-patterns/`. It uses the deterministic `okfctl match-brief-pattern` command to narrow candidates, then opens only relevant active concepts. A match is a suggestion, not authorization.

The Assistant may reuse a pattern only through explicit confirmation. Authority, memory, stop, escalation, and trigger fields are never silently copied. Outcome and discovery scope remain current-task-specific.

When a completed brief is eligible for durable reuse, the Assistant creates a structured pattern proposal. Gatekeeper independently classifies every proposal. `brief-pattern-curator` converts only accepted proposals into complete OKF documents, and the Go transaction writes them atomically.

See `LOOP_BRIEF_PATTERN_MEMORY.md` for the full protocol.
