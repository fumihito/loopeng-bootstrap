# Sanitized telemetry schema

All custom records use the `agent.loop.*` namespace and OTLP/HTTP JSON.

## Common attributes

| Attribute | Meaning | Content policy |
|---|---|---|
| `agent.platform` | `claude` or `codex` | Allowed |
| `agent.session.id` | Sanitized host session identifier | Allowed |
| `agent.turn.id` | Sanitized turn identifier | Allowed |
| `agent.role` | Named control subagent | Allowed |
| `skill.name` | Invoked project skill when observable | Allowed |
| `tool.name` | Host tool name | Allowed |
| `command.name` | First executable basename | Allowed |
| `command.names` | Executable basenames in a shell pipeline/list | Allowed, max 8 |
| `tool.success` | Tool outcome | Allowed |
| `tool.duration_ms` | Host-provided duration | Allowed |
| `tool_input_redacted` | Always `true` | Required |
| `tool.identity_redacted` | `false`; identity fields remain visible | Required |
| `tool.arguments_logged` | Always `false` | Required |
| `command.arguments_logged` | Always `false` | Required |

## Event names

- `agent.loop.turn.started`
- `agent.loop.turn.stopping`
- `agent.loop.turn.completed`
- `agent.loop.skill.activated`
- `agent.loop.agent.started`
- `agent.loop.agent.stopped`
- `agent.loop.role.reported`
- `agent.loop.tool.started`
- `agent.loop.tool.completed`
- `agent.loop.tool.permission_requested`
- `agent.loop.tool.permission_denied`
- `agent.loop.watchdog.tripped`
- `agent.loop.telemetry.self_test`
- `agent.loop.learning.turn_observed`
- `agent.loop.learning.health_updated`
- `agent.loop.learning.observation_failed`
- `agent.loop.learning.audit_reported`

## Explicitly excluded

Raw prompts, prompt hashes in OTel, command strings, subcommands, options, arguments, file paths, URLs, search patterns, tool input, tool output, error text, environment variables, headers, credentials, and role-report bodies are never attached to custom OTel events.

## Gatekeeper events

Gatekeeper activation and report persistence use the same `agent.loop.agent.*`, `agent.loop.skill.activated`, and `agent.loop.role.reported` events. `agent.role=gatekeeper` and `skill.name=gatekeeper` are emitted; the user prompt, normalized brief, questions, and rejection reasons are not emitted.

## Direct-mode events

| Event | Meaning | Safe attributes |
|---|---|---|
| `agent.loop.direct.started` | A strict `direct:` header started a Gatekeeper-free turn | `routing.mode`, `direct.allow_mutations`, `prompt.content_logged=false` |
| `agent.loop.direct.completed` | The bounded direct turn stopped normally | `routing.mode`, `turn.status`, `mutation.epoch` |

Prompt text and answer content are excluded.

## Loop Brief Assistant events

Gatekeeper and Loop Brief Assistant use the normal agent, skill, and role events. A trusted Assistant report additionally emits `agent.loop.loop_brief_assistant.reported` with only `brief_assistant.status`, remaining-condition count, and question count. Draft values, user answers, assumptions, and conflicts are not emitted.

## SOP routing events

| Event | Meaning | Safe attributes |
|---|---|---|
| `agent.loop.sop.loaded` | A leading header resolved and the mandatory skill was injected | `routing.mode`, `sop.header`, `skill.name`, `sop.loaded`, `sop.allow_mutations` |
| `agent.loop.sop.load_failed` | The required skill was absent or invalid and the prompt was blocked | `routing.mode`, `sop.header`, `skill.name`, `sop.loaded` |
| `agent.loop.sop.completed` | An isolated SOP turn stopped normally | `routing.mode`, `sop.header`, `skill.name`, `turn.status`, `mutation.epoch` |

Prompt text and skill body are never included.

## Learning-observability events

| Event | Meaning | Safe attributes |
|---|---|---|
| `agent.loop.learning.turn_observed` | A completed PASS turn was converted into a structured learning observation | `learning.observation_complete`, counts of lessons considered/recorded/questions updated |
| `agent.loop.learning.health_updated` | Cross-turn deterministic health summary was rebuilt | health classification, coverage, reuse/helpful-reuse ratios, recurrence count, overdue-question count, stale-lesson count, debt score |
| `agent.loop.learning.observation_failed` | The local deterministic observer failed | success flag and exception class only |
| `agent.loop.learning.audit_reported` | The read-only Learning Auditor returned a trusted report | health verdict and human-review flag |

The exporter never includes `problem_signature`, lesson IDs, question IDs, lesson statements, evidence references, applicability conditions, invalidation conditions, or policy recommendations. Those remain local to the repository.

## OKF LLMWiki memory events

| Event | Meaning | Safe attributes |
|---|---|---|
| `agent.loop.memory.curated` | A trusted Memory Curator report was processed by the deterministic Go transaction | curator status, commit success, created/updated/deprecated/applied counts |
| `agent.loop.learning.turn_observed` | Also records memory retrieval and promotion structure for the completed turn | retrieval-performed flag, candidate/relevant counts, proposal/accepted/applied counts, commit success |
| `agent.loop.learning.health_updated` | Also records cross-turn memory pipeline health | retrieval coverage, promotion completion ratio, commit-failure count, accepted-not-committed count |

Concept IDs, proposal IDs, Wiki document bodies, citations, source references, frontmatter, search terms, and validation error content are excluded from OTel. A failed deterministic commit records only the failure class or aggregate status; detailed diagnostics remain in repository-local protected state.

## Loop Brief pattern events

The following sanitized events are emitted:

- `agent.loop.brief_pattern.retrieved`
- `agent.loop.brief_pattern.assessed`
- `agent.loop.brief_pattern.curated`

Only counts, status, and booleans are exported. Pattern IDs, pattern documents, user answers, Loop Brief field values, and match-key values are not exported.
