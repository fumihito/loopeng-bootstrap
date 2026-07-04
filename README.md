# Loop Engineering Bootstrap

Loop Engineering Bootstrap is a bootstrap kit for running AI-agent work as engineered loops: a deterministic control layer around LLM roles, with humans holding final authority. It ships two usable layers: the exploration phase, which uses bounded entry routing (`direct:`, `route:`, and `frame-*` skills), and the autonomous phase, which runs as a contract-gated loop on top of it.

## Core concept

The turn contract starts with a Loop Brief, then Gatekeeper checks whether the request is legitimate, bounded, and explicit enough to start a loop.
Sensemaker then frames the task, while State Steward, Meta-Evaluator, and related roles keep state, learning, and memory separate from generation.
Deterministic hooks enforce protected paths, command boundaries, skill loading, and sanitized telemetry.
Every completed cycle is bounded by budgets and stop conditions.
The next cycle comes from handoff state plus the scheduler, not from a self-directed model rewrite.
See `docs/loop-structure.svg` and `docs/ARCHITECTURE.md` for the full loop picture.

## Install

Prerequisite for the full install: Go 1.21+.
The routing profile does not require the Go-backed loop layer.

```bash
python3 install.py --repo /path/to/repository
python3 install.py --repo /path/to/repository --profile routing
python3 install.py --repo .
```

Details for mixed Codex / Claude layouts, semantic merge workflows, and LLM-assisted installation live in `docs/INSTALL.md`.

## First contact

Start with no prefix if you want the package to route you into Gatekeeper intake; Gatekeeper and `loop-brief-assistant` will help form the contract.
Use `route:` when you want a pre-loop proposal that suggests `frame-*` candidates.
Use `direct:` when you want a bounded single-turn interaction without the autonomous loop.

```text
repair CI failures under this operating contract ...
```

See `docs/GATEKEEPER_PROTOCOL.md` and `docs/COMMAND_ROUTING.md`.

## Documentation map

| Doc | What it covers |
|---|---|
| `docs/ARCHITECTURE.md` | Why the loop is split into roles and guardrails, plus rejected alternatives. |
| `docs/COMMAND_ROUTING.md` | `route:` proposal flow and `frame-*` selection rules. |
| `docs/DIRECT_MODE.md` | Bounded read-only `direct:` turns. |
| `docs/SOP_ROUTING.md` | Mandatory `<header>:` routing for SOP skills. |
| `docs/GATEKEEPER_PROTOCOL.md` | Gatekeeper intake, contract fields, and verdicts. |
| `docs/LOOP_INPUT_GUIDE.md` | What humans should provide for an autonomous loop. |
| `docs/OKF_LLMWIKI.md` | Durable-memory rules for OKF LLMWiki. |
| `docs/LEARNING_OBSERVABILITY.md` | Cross-turn learning metrics and audit flow. |
| `docs/OBSERVABILITY.md` | Deterministic loop-status and learning-health views. |
| `docs/SCHEDULER.md` | Scheduler daemon, cadence, and handoff behavior. |
| `docs/TELEMETRY.md` | Sanitized OTel schema and collector behavior. |
| `docs/INSTALL.md` | Full install, routing profile, mixed layouts, and semantic merge. |
| `docs/RELEASE_AUDIT.md` | Completion protocol, audit guard, and release checks. |

## Status

Active development. Interfaces may change while the loop contract, install flow, and routing behavior continue to settle.
Licensed under the MIT License.
