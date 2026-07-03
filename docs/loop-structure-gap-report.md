# Loop Structure Gap Report

## Scope

This report compares the current repository structure with `docs/loop-structure.mmd` and identifies where the implementation matches the main loop, where the repository already goes beyond the diagram, and where the diagram still has no concrete runtime counterpart.

## Summary

The core loop is largely implemented as a hook-driven policy system:

- `direct:` routing exists and is enforced before the autonomous loop.
- `sop-<header>` routing exists and is isolated from the autonomous loop.
- Gatekeeper, Loop Brief Assistant, Sensemaker, Governor, State Steward, Meta-Evaluator, Memory Curator, Watchdog / Recovery, and Learning Auditor are all present as role contracts and enforced hook paths.

The main structural additions are now:

- the repository contains a long-running scheduler daemon and a matching systemd unit that consume the deterministic next-turn handoff artifact;
- each completed loop turn writes a machine-readable `gatekeeper-prompt.json` bundle and carries `trigger_cadence` forward;
- the diagram now shows the scheduler boundary explicitly, while still compressing the route/direct/FRAME/SOP exits into a compact entry routing block and leaving the `brief-pattern-curator` / `PATTERN_CAPTURE` branch as a secondary loop detail.

## Mapping

| Diagram element | Current state | Evidence | Gap |
|---|---|---|---|
| `direct:` entry | Implemented | `loop_hook.py` routes `direct:` before SOP and Gatekeeper, and `docs/DIRECT_MODE.md` defines the mode. | None. |
| `SOP router` | Implemented | `loop_hook.py` resolves `sop-<header>` and loads the matching skill; `docs/SOP_ROUTING.md` documents the isolation model. | None. |
| `Gatekeeper` | Implemented | `ROLES` includes `gatekeeper`; the hook blocks mutation and Sensemaker before trusted READY. | None. |
| `Loop Brief Assistant` | Implemented | `ROLES` includes `loop-brief-assistant`; the hook allows it only after NEEDS_INPUT or PATTERN_CAPTURE. | The diagram does not show the assistant's pattern-capture branch. |
| `Sensemaker` | Implemented | `ROLES` includes `sensemaker`; docs require prior memory retrieval and task framing. | None. |
| `Governor` | Implemented | `ROLES` includes `governor`; policy enforcement is checked before mutation. | None. |
| `Generator / Actor` and `Evaluator` | Partially implemented | The repo relies on the parent agent plus hook checks rather than a separate integrator runtime. | The integration step is still role-based rather than a first-class execution engine. |
| `Integrator` | Implemented | `ROLES` includes `integrator`; the hook validates `integrator.json`, and the policy can require it before mutation. | None. |
| `State Steward` | Implemented | `ROLES` includes `state-steward`; after mutation the hook requires a trusted report for the current mutation epoch. | None. |
| `Meta-Evaluator` | Implemented | `ROLES` includes `meta-evaluator`; tests cover the required PASS / REVISE / ESCALATE flow. | None. |
| `Memory Curator` | Implemented | `ROLES` includes `memory-curator`; `docs/OKF_LLMWIKI.md` requires curator-only commits via `okfctl apply-report`. | None. |
| `LLMWiki` durable memory | Implemented | The OKF bundle is stored under `llmwiki/` and is write-protected from ordinary tools. | None. |
| `Watchdog` / `Recovery` | Implemented | `ROLES` includes `watchdog-recovery`; the hook trips on failures and requires human reset. | The diagram compresses runtime monitoring and human reset into one node. |
| `Learning Observer` | Implemented | `docs/LEARNING_OBSERVABILITY.md` defines the observer pipeline and metrics; the hook records learning observations at turn completion. | None. |
| `Learning Auditor` | Implemented | `ROLES` includes `learning-auditor`; `sop-learning-audit` is read-only and isolated. | None. |
| `Scheduler / external trigger` | Implemented as daemon + handoff artifact | `Stop` writes `next-turn.json`; `gatekeeper-prompt.json` preserves the deterministic continuation prompt; `.agent-loop/bin/next_turn_scheduler.py` reports or validates the handoff; `.agent-loop/bin/next_turn_scheduler_daemon.py` polls ready handoffs and can run configured trigger or notification commands under systemd. | None. |
| `Turn completed` | Implemented as hook finalization | `Stop` handling in `loop_hook.py` sets `final_status`, records read-only completions, and writes runtime state. | None. |
| `Next loop execution` | Implemented as scheduler handoff | The repo now preserves `next-turn.json` plus a deterministic prompt bundle and exposes a daemon that consumes them. | None. |

## Additional repository behavior not shown in the diagram

The repository already has some control planes that are not explicit in `docs/loop-structure.mmd`:

- `brief-pattern-curator` and `PATTERN_CAPTURE` for reusable Loop Brief patterns;
- separate policy files for direct mode, SOP mode, memory, learning, and brief-pattern promotion;
- turn persistence under `.agent-loop/runtime/` and `.agent-loop/state/learning/`;
- explicit trust checks on subagent reports before curator and auditor roles are allowed to run.

These are not missing features. They are extra implementation constraints that make the current system stricter than the diagram suggests. The current diagram intentionally abstracts the scheduler's skip/notification distinction into a single cadence gate and keeps the isolated FRAME and SOP exits shallow so the main loop and its deterministic boundaries remain readable.

## Concrete evidence

- `docs/loop-structure.mmd:1-118`
- `docs/loop-structure-implementation-plan.md:1-57`
- `.agent-loop/hooks/loop_hook.py:21-31`
- `.agent-loop/hooks/loop_hook.py:44-56`
- `.agent-loop/hooks/loop_hook.py:905-963`
- `.agent-loop/hooks/loop_hook.py:1163-1225`
- `.agent-loop/hooks/loop_hook.py:1232-1263`
- `.agent-loop/hooks/loop_hook.py:1272-1322`
- `.agent-loop/hooks/loop_hook.py:1330-1358`
- `.agent-loop/hooks/loop_hook.py:1374-1519`
- `.agent-loop/hooks/loop_hook.py:1529-1664`
- `.agent-loop/bin/next_turn_scheduler.py:1-57`
- `.agent-loop/bin/next_turn_scheduler_daemon.py:1-262`
- `adapters/shared/skills/integrator/SKILL.md:1-18`
- `tests/test_smoke.py:170-216`
- `tests/test_smoke.py:233-302`
- `tests/test_smoke.py:316-351`
- `docs/SOP_ROUTING.md:7-39`
- `docs/OKF_LLMWIKI.md:9-20`
- `docs/LEARNING_OBSERVABILITY.md:16-49`

## Conclusion

The main loop is present and enforced, but it is implemented as a distributed set of hooks, role contracts, runtime files, and policy checks rather than as a single orchestrated DAG executor.

The repository now contains a dedicated Integrator implementation, a concrete next-turn handoff path, a deterministic continuation prompt bundle, support for read-only turn completion, and a persistent scheduler daemon suitable for systemd user service deployment. The Mermaid view now mirrors that boundary more closely: the terminal states feed the next-turn bundle, the daemon's cadence gate is explicit, and the only remaining abstraction is the compressed treatment of isolated entry modes and secondary pattern governance.

The follow-up defects from the companion review are now implemented and covered by targeted tests. What remains is deliberate diagram abstraction: the Mermaid view still compresses the scheduler into an external trigger, omits the extra loop branches to keep the boundary readable, and does not spell out the prompt artifact, cadence metadata, validation allowlist, or evidence distinctions enforced at turn completion.
