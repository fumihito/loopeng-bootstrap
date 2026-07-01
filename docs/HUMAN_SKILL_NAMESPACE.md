# Human Skill Namespace

Human-facing skills in this repository use the `frame-*` namespace.
The hook auto-routes a strict leading `frame-<name>:` prompt into isolated `FRAME` mode and loads the matching `frame-*` skill.

Rules:

- `frame-*` is for human planning, analysis, review, and troubleshooting frames.
- agent-facing skills keep their role or SOP names.
- when a human workflow and an agent workflow overlap, prefer separate names rather than dual-use naming.
- `sop-*` is reserved for agent-oriented SOP behavior already used by the loop runtime.

This naming choice keeps human runbooks distinct from agent contracts and makes install-time validation unambiguous.
