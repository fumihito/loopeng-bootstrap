---
name: gatekeeper
description: Validate the operating contract and independently assess reusable Loop Brief pattern proposals before the autonomous loop starts.
---

Invoke exactly one platform custom subagent named `gatekeeper` in an isolated read-only context. Give it the current task, relevant loop state, and any trusted Loop Brief Assistant report.

For missing input, hand off to Loop Brief Assistant. For a complete brief whose memory contract explicitly permits input-pattern capture, Gatekeeper may request Assistant `PATTERN_CAPTURE`. Gatekeeper must independently classify every returned pattern proposal before any curator is invoked. Previous patterns never grant present authority.

If a request looks like a one-shot, read-only, or otherwise non-autonomous task, Gatekeeper may add a `mode_recommendation` field to `NEEDS_INPUT` or `REJECT` reports. The field is a user-facing hint only, with `{mode, reason}` in user vocabulary, and it should suggest `direct:`, `route:`, or a matching `frame-<name>:` prefix when that would let the user rerun the request without drafting a loop brief. Do not auto-route or otherwise change execution based on this hint.

Return exactly one JSON object with the Gatekeeper schema documented in `.agent-loop/docs/GATEKEEPER_PROTOCOL.md` and `.agent-loop/docs/LOOP_BRIEF_PATTERN_MEMORY.md`. The hook validates the actual agent type and persists the report. Do not include prompts, answers, pattern IDs, documents, paths, tool contents, command arguments, or credentials in telemetry.

If the report includes `validation_commands`, they must select from the human-owned `validation_command_allowlist` in `.agent-loop/policy.json`; Gatekeeper must not invent new commands. `trigger_cadence` must be normalized to the machine-readable values accepted by the hook (`immediate`, `manual`, `external-user-prompt`, or `on-event:<safe-name>`), not free text.
