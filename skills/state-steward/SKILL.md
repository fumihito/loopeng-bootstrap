---
name: state-steward
description: Record an auditable state transition and propose reusable knowledge for independent OKF curation.
---

Invoke the platform custom subagent named `state-steward` in an isolated context. Explicitly spawn exactly one `state-steward` subagent, give it the current task and relevant loop state, wait for it to finish, and return its result to the parent flow.

The final message must be exactly one JSON object with no markdown or surrounding prose. The `SubagentStop` hook validates the actual `agent_type` and persists the trusted report. Do not synthesize or rewrite the role report in the parent context.

Telemetry is emitted automatically by lifecycle hooks. Do not add prompts, command arguments, file paths, tool inputs, tool outputs, credentials, memory documents, lesson statements, or question text to telemetry.
