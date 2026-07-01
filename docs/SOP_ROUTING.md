# SOP header routing

This package supports a workflow that is separate from the autonomous Loop Engineering roles.

## Routing rule

When a user prompt begins at character 1 with a lowercase header followed by a colon, the hook maps it to `sop-<header>`, except for the reserved `direct:` header and the discoverability header `list:`:

```text
diag: investigate why the integration test is flaky
```

loads:

```text
sop-diag
```

`list:` loads `sop-list`, which exists to enumerate the currently available user-entry modes and route families from the canonical repository sources.

Accepted headers match `[a-z][a-z0-9-]{0,31}`. URI prefixes such as `https://` are excluded. `direct:` is resolved first into dedicated DIRECT mode and never maps to `sop-direct`. `list:` maps to the mode-index SOP and never bypasses the router. All remaining headers have precedence over Gatekeeper routing.

## Enforcement model

The `UserPromptSubmit` hook resolves the canonical skill through either platform alias. Both names point to the same physical file:

```text
skills/sop-<header>/SKILL.md       # one physical file
.agents/skills -> ../skills/       # Codex resolves the same file
.claude/skills -> ../skills/       # Claude Code resolves the same file
```

It validates the frontmatter `name`, enforces a size limit, hashes the file, and inserts the complete skill into developer context before the model receives the prompt. This does not depend on implicit skill matching or on the model deciding to call a Skill tool.

If the skill is absent, invalid, outside the repository, too large, or has a mismatched name, the user prompt is blocked.

## Isolation from the autonomous loop

A routed SOP turn does not invoke Gatekeeper, Sensemaker, State Steward, or Meta-Evaluator. Normal destructive-command, protected-path, permission, Watchdog, and sanitized OTel controls remain active.

SOPs are read-only by default. Mutation permission is controlled by `.agent-loop/sop-policy.json` and must be explicitly enabled per skill after security review.

## Adding a new SOP

Create one canonical skill file:

```text
skills/sop-security/SKILL.md
```

The existing `.agents/skills` and `.claude/skills` aliases expose it to both clients. Do not create separate platform copies.

The file must contain:

```yaml
---
name: sop-security
description: Mandatory SOP for prompts beginning with security:.
---
```

Then use:

```text
security: inspect the reported finding
```

For mode discovery, use:

```text
list: show the currently available modes
```

Do not place credentials or secrets in a skill file. The skill body is injected into model context, but is not written to telemetry or runtime journals.

## Telemetry

The hook emits:

- `agent.loop.sop.loaded`
- `agent.loop.sop.load_failed`
- `agent.loop.sop.completed`

Attributes include only `skill.name`, `sop.header`, routing mode, and mutation policy. Prompt text and skill content are not logged.

## Learning audit SOP

The archive includes `sop-learning-audit` for periodic cross-turn review:

```text
learning-audit: inspect the last 50 completed loop turns
```

This SOP is read-only. It rebuilds deterministic learning-health metrics and permits only the `learning-auditor` control role inside the otherwise isolated SOP turn. Gatekeeper, Sensemaker, State Steward, Meta-Evaluator, Generator mutation, and policy changes remain excluded.
