# Loop Engineering Bootstrap

Loop Engineering Bootstrap is a bootstrap kit for running AI-agent work as engineered loops: a deterministic control layer around LLM roles, with humans holding final authority. v0.2 is a redesign line, not a continuation of the v15/v0.1 contract, and the two are intentionally incompatible.

## Core concept

v0.2 keeps only the frame-* skill family plus a Python control layer for autonomous execution, auditability, learning extraction, and OKF LLMWiki memory updates. It removes the old role-pipeline gatekeeping model, replaces hook-driven observability with file-based journal and Run Report artifacts, and treats post-run alerts as the primary deviation surface.

## Install

The routing profile installs only the frame-* skills and the shared installer/runtime scaffolding.

```bash
python3 install.py --repo /path/to/repository
python3 install.py --repo /path/to/repository --profile routing
python3 install.py --repo .
```

Details for mixed Codex / Claude layouts, semantic merge workflows, and LLM-assisted installation live in `docs/INSTALL.md`.

## First contact

Use a plain prompt when you want the loop runtime to execute under the v0.2 contract. The frame-* skill family remains available for exploratory framing, but the old route:/brief:/Gatekeeper intake flow is removed in this line.

## Documentation map

| Doc | What it covers |
|---|---|
| `docs/ARCHITECTURE.md` | v0.2 architecture and the remaining Python control layer. |
| `docs/OKF_LLMWIKI.md` | Durable-memory rules for OKF LLMWiki. |
| `docs/RUN_REPORT.md` | Run Report schema and completion discipline. |
| `docs/INSTALL.md` | Full install, routing profile, mixed layouts, and semantic merge. |
| `docs/RELEASE_AUDIT.md` | Completion protocol, audit guard, and release checks. |

## Status

v0.2 is the redesign line. It is not compatible with the v15/v0.1 role-pipeline contract or its hook-based control flow.
Licensed under the MIT License.
