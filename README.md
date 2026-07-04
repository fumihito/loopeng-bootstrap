# Loop Engineering Bootstrap

Fundamental configuration for Loop engineering with Codex and Claude Code.

## Design summary

This package is the basic structure for a constrained, human-governed loop. It is grounded in cybernetics and requisite variety: deterministic controls handle precision-critical behavior, LLMs handle discretionary judgment, and humans decide how the loop itself behaves. Cross-turn learning is emitted through OTEL, memory is managed in OKF-style LLMWiki, and sanitized telemetry keeps prompts and secrets out of the audit trail while still exposing skill names and executed command names.

Main roles are: Gatekeeper, Loop Brief Assistant, Sensemaker, Governor, State Steward, Watchdog / Recovery, Meta-Evaluator, Learning Auditor, and Memory Curator, with OKF LLMWiki durable memory and deterministic cross-turn learning observability and sanitized OpenTelemetry logging.

## Loop structure

![Loop structure diagram](docs/loop-structure.svg)

The SVG above makes the loop boundary explicit: state, memory, and human policy changes are the outputs that seed the next turn.

The repository also ships a systemd-backed scheduler daemon at `.agent-loop/bin/next_turn_scheduler_daemon.py` with a matching unit file at `.agent-loop/systemd/agent-loop-scheduler.service`. It polls `next-turn.json` handoffs, records scheduler state, and can run a configured trigger command when the next turn is ready.
Each completed loop turn also writes a deterministic `gatekeeper-prompt.json` artifact and records normalized `trigger_cadence` values (`immediate`, `manual`, `external-user-prompt`, or `on-event:<name>`) so the next turn can start from a machine-readable prompt bundle without manual reconstruction. Gatekeeper `validation_commands` are executed only from the policy allowlist.

## Entry Modes

The repository currently recognizes these common user-entry families:

- `list:` for a mode index that reports the current entry families and their canonical sources.
- `direct:` for bounded non-autonomous questions and inspection.
- `route:` for a pre-loop proposal mode that suggests `frame-*` candidates before Gatekeeper.
- no prefix for the autonomous loop and Gatekeeper intake path.

These four are the normal entry modes. Other strict leading headers, including `frame-<name>:` and `sop-<header>:`, are specialized manual operations for exceptional workflows rather than everyday entry points.
If you are unsure, just ask normally with no prefix; the loop will start from Gatekeeper and can guide you from there.

See `docs/DIRECT_MODE.md`, `docs/SOP_ROUTING.md`, and `docs/HUMAN_SKILL_NAMESPACE.md`.
The hook auto-routes strict leading `direct:`, `list:`, `frame-<name>:`, and other `<header>:` prompts into their dedicated modes before the model processes the request.
See `docs/COMMAND_ROUTING.md` for the separate `route:` pre-loop proposal mode.

## Troubleshooting routine

Use the routing profile when you want this repository as a bounded troubleshooting kit instead of a full autonomous loop:

```bash
python3 install.py --repo /path/to/repository --profile routing
```

Then use one of these entry families in one line: `direct:` for bounded help, `route:` for frame selection before the loop, or `diag:` for mandatory SOP diagnosis. The user does not need to know the prefixes ahead of time, so this README is the single place where the routing lesson is stated.

Examples:

```text
route: production is occasionally double-processing a request
diag: the service keeps restarting
```

## Design philosophy and architecture decisions

This archive now includes two Japanese design documents intended for maintainers and reviewers, not only operators.

- `docs/DESIGN_PHILOSOPHY.md`: derives the role structure from cybernetics, requisite variety, organizational learning, Principal-Agent/Common Agency, Goodhart/Campbell, STAMP, sensemaking, affordance, emergence, organizational routines, and the ironies of automation. It also defines the boundary between deterministic controls, LLM judgment, and human authority.
- `docs/ARCHITECTURE.md`: records rejected alternatives and their context, including the single-super-agent model, Generator/Evaluator-only design, all-LLM and all-deterministic control, self-resetting Watchdog, implicit skill loading, detailed OTel, unconditional symlink rejection, configuration overwrite, backup-only installation, and unrestricted semantic merging.

The installer copies both documents to `.agent-loop/docs/` so that the reasoning remains available inside each installed repository.

## Direct mode

A prompt beginning with `direct:` starts a bounded non-autonomous turn without Gatekeeper:

```text
direct: explain why this test is flaky
```

Direct mode is intended for one-shot questions, inspection, and explanation. It does not invoke Gatekeeper or the loop-control roles, does not produce cross-turn learning observations, and does not promote OKF memory. It remains subject to destructive-command, protected-path, permission, Watchdog, LLMWiki, and telemetry controls. Mutations are disabled by default in `.agent-loop/direct-policy.json`.

See `docs/DIRECT_MODE.md`.

## Mode index

A prompt beginning with `list:` loads `sop-list` and returns a human-readable index of the currently available user-entry mode families and canonical sources.

## Mandatory SOP header routing

A prompt beginning with `<header>:` bypasses the autonomous loop and forces the corresponding `sop-<header>` skill to be loaded before the model processes the request.

```text
diag: investigate why the integration test is flaky
```

loads `sop-diag`. The hook reads and validates the platform-native `SKILL.md`, injects its complete content as developer context, records only the skill identity in OTel, and blocks the prompt if the skill is missing or invalid. SOP turns are read-only by default and do not invoke Gatekeeper or the other loop-control roles.

See `docs/SOP_ROUTING.md`. An installed `sop-diag` example and `templates/SOP_SKILL_TEMPLATE.md` are included.

## Gatekeeper-first intake

The user addresses Gatekeeper rather than Generator or Sensemaker. Every unprefixed prompt that is not in an outstanding Assistant dialogue is routed to the installed `gatekeeper` role. Gatekeeper validates the ten-part operating contract, including explicit learning and memory contracts and returns `READY`, `NEEDS_INPUT`, or `REJECT`.

- `READY`: writes a normalized `loop-brief.json` and hands off to Sensemaker.
- `NEEDS_INPUT`: activates the read-only Loop Brief Assistant. The Assistant asks the minimum questions, persists a draft across user turns, and returns a complete draft to Gatekeeper for independent revalidation.
- `REJECT`: no autonomous loop starts.

Loop Brief Assistant never hands directly to Sensemaker and may not invent authority, evaluation criteria, learning policy, memory policy, or escalation ownership. Hooks reject Sensemaker reports and product mutations until a trusted Gatekeeper `READY` report exists. See `docs/GATEKEEPER_PROTOCOL.md` and `docs/LOOP_BRIEF_ASSISTANT.md`.

## OKF LLMWiki durable memory

The repository-local `llmwiki/` directory is an Open Knowledge Format v0.1 bundle. OKF supplies a vendor-neutral Markdown/YAML interchange format and progressive-disclosure indexes; the loop-control layer supplies truth discipline, authority, promotion, correction, and deprecation.

```text
Sensemaker retrieval
  -> State Steward memory proposal
  -> Meta-Evaluator independent classification
  -> Memory Curator complete OKF documents
  -> deterministic Go okfctl transaction
```

Direct agent edits to `llmwiki/` are rejected. Only accepted proposals rendered by the read-only Memory Curator can reach `.agent-loop/bin/okfctl apply-report`. The Go transaction rejects secret-like content and invalid profile documents, updates `log.md`, regenerates indexes, validates the complete bundle, backs up the previous bundle, and atomically replaces it.

The additional memory command is implemented in Go. The bundled shell launchers invoke Go only and do not invoke Python.

```bash
.agent-loop/bin/build-okfctl.sh
.agent-loop/bin/okfctl validate --root llmwiki
.agent-loop/bin/okfctl search --root llmwiki --query "failure pattern"
.agent-loop/bin/okfctl show --root llmwiki --id failure-patterns/example
```

The installer creates only missing LLMWiki skeleton files and never overwrites existing concepts. See `docs/OKF_LLMWIKI.md` and `templates/OKF_CONCEPT.md`.

## Learning observability

Every completed `PASS` loop turn is converted into a content-minimizing learning observation, and the observer emits sanitized OTEL learning signals while tracking stable problem signatures, explicit prior-learning retrieval and consideration by Sensemaker, structured lessons and question updates from State Steward, and Meta-Evaluator judgments about lesson validity and reuse outcomes. It then builds:
Read-only loop turns can also complete when the contract permits it; they still produce the same deterministic completion artifacts and learning observation pipeline.

```text
.agent-loop/state/learning/learning-health.json
.agent-loop/state/learning/learning-index.json
.agent-loop/state/learning/turns/<turn-id>.json
```

The main metrics are observation coverage, knowledge capture, learning reuse, learning-chain completion, time to first reuse, helpful or harmful reuse, recurrence after validated learning, question resolution, evaluation adaptation, stale lessons, orphan lessons, identifier collisions, trend deltas, OKF memory retrieval coverage, proposal-to-commit completion, memory commit failures, and a weighted learning-debt score. High PASS rate or high lesson count is never treated as learning by itself.

Rebuild or inspect the deterministic report:

```bash
python3 .agent-loop/bin/learning_health.py rebuild
python3 .agent-loop/bin/learning_health.py report --format json
python3 .agent-loop/bin/learning_health.py check --fail-on unhealthy
```

Run the independent cross-turn audit through the SOP router:

```text
learning-audit: audit the last 50 completed loop turns for reuse, recurrence, correction, adaptation, and learning debt
```

This loads `sop-learning-audit` and invokes the read-only `learning-auditor`. Existing pre-v11 history can be excluded from the health baseline with `history_start_at` in `.agent-loop/learning-policy.json`. See `docs/LEARNING_OBSERVABILITY.md`.

## Loop status

`loop_status.py` renders the current loop health from the deterministic runtime artifacts.

```bash
python3 .agent-loop/bin/loop_status.py --text
python3 .agent-loop/bin/loop_status.py --html
```

The HTML page is written to `.agent-loop/runtime/status.html` by default and stays self-contained for offline inspection. The default view omits Loop Brief goal text; use `--include-brief` only when you want the local page to show it. See `docs/OBSERVABILITY.md`.
Verified by `tests/test_loop_status.py::LoopStatusTests`.

## Telemetry contract

The hook emits OTLP/HTTP JSON events named `agent.loop.*`. It records only:

- platform (`claude` or `codex`)
- role/subagent name
- invoked skill name when observable
- tool name
- executable command name(s), such as `git`, `python3`, or `npm`
- success/failure, duration when supplied by the host, mutation epoch, watchdog state, and aggregate learning-health counts or ratios

It never emits raw prompts, command strings, command arguments, file paths, URLs, search patterns, tool input, tool output, hook headers, environment variables, credentials, problem signatures, lesson IDs, lesson text, question IDs, or evidence references. Local runtime journals use the same sanitized contract.

`tool_input_redacted=true` and `tool.identity_redacted=false` are intentional: raw inputs are suppressed while tool/skill/command identity remains visible. Setting Claude Code `OTEL_LOG_TOOL_DETAILS=1` would expose full Bash commands and all tool arguments, so this archive explicitly keeps it disabled.

## Claude Code

`.claude/settings.json` enables native Claude Code OTel with prompt, tool-detail, tool-content, and raw-body logging disabled. Native events provide general usage/tool activity; custom `agent.loop.*` events add exact project skill names and executable command names without arguments.

The hooks cover `UserPromptExpansion`, `SubagentStart`, `PreToolUse`, `PostToolUse`, `PostToolUseFailure`, permission events, and completion events. Direct `/skill-name` invocation and proactive Skill-tool invocation are both observed.

## Codex

Project hooks emit the same sanitized `agent.loop.*` schema for Codex-supported hook paths: Bash, apply_patch/Edit/Write aliases, MCP tools, and custom subagent lifecycle events. Codex currently does not expose every internal tool through project hooks, so this is not a complete audit of WebSearch or richer unified-exec paths.

Codex ignores `[otel]` in project-local `.codex/config.toml`. This archive therefore uses its own project hook OTLP exporter. Native Codex OTel is intentionally not enabled by the installer because current native `codex.tool_result` events may include an output snippet and do not expose a documented field-level suppression switch.

## Install

Prerequisite: Go toolchain `go1.21` or newer.

```bash
python3 install.py --repo /path/to/repository
```

Dry run:

```bash
python3 install.py --repo /path/to/repository --dry-run
```

Validate the installed OKF memory layer:

```bash
.agent-loop/bin/okfctl validate --root llmwiki
```

## Collector

A local debug collector example is included at `.agent-loop/otel-collector.yaml`:

```bash
otelcol-contrib --config .agent-loop/otel-collector.yaml
```

Default hook endpoint: `http://127.0.0.1:4318/v1/logs`. Override without committing credentials:

```bash
export AGENT_LOOP_OTEL_ENDPOINT=https://collector.example/v1/logs
export AGENT_LOOP_OTEL_HEADERS='Authorization=Bearer ...'
export AGENT_LOOP_ENVIRONMENT=production
```

Claude Code does not forward `OTEL_*` variables to hook subprocesses, so the hook exporter deliberately uses the `AGENT_LOOP_*` prefix.

## Self-test

```bash
python3 .agent-loop/hooks/loop_hook.py telemetry-test --platform claude
python3 .agent-loop/hooks/loop_hook.py telemetry-test --platform codex
```

If no collector is listening, a sanitized fallback record is written to `.agent-loop/runtime/telemetry.jsonl`. The self-test contains a fake secret argument and validates that only the command name `git` is emitted.

## Security boundary

Hooks are guardrails, not a complete sandbox. Keep OS/container isolation, IAM, branch protection, and required CI checks. Do not enable `OTEL_LOG_TOOL_DETAILS`, `OTEL_LOG_TOOL_CONTENT`, raw API bodies, or user-prompt logging unless a separate security review accepts the resulting data exposure.

## Interaction routing examples

```text
direct: explain the repository architecture
  -> direct, Gatekeeper-free, read-only by default

diag: investigate the current failure
  -> mandatory sop-diag

repair CI failures under this operating contract ...
  -> Gatekeeper
     -> NEEDS_INPUT -> Loop Brief Assistant -> Gatekeeper review
     -> READY -> Sensemaker and autonomous loop
```

## Starting an autonomous loop

Hooks and the ten named roles govern one execution and its cross-turn learning evidence. A scheduler plus persistent state is still required to start later executions automatically.

Before use, define a stable operating contract and provide a Loop Brief covering outcome, discovery scope, authority, evaluation evidence, persistence, learning, durable memory, stop conditions, escalation, and trigger cadence.

- Gatekeeper protocol: `docs/GATEKEEPER_PROTOCOL.md`
- Japanese input guide: `docs/LOOP_INPUT_GUIDE.md`
- Ready-to-edit Loop Brief: `templates/LOOP_BRIEF.md`

The installer also copies `docs/SOP_ROUTING.md` and `templates/SOP_SKILL_TEMPLATE.md` to `.agent-loop/`.
Developers can opt into the pre-push audit guard with `utils/install-dev-hooks.sh` from the repository root.


## LLM-assisted semantic installation

The deterministic installer merges valid JSON hook/settings files and managed Markdown blocks. It must not guess how to reinterpret an arbitrary legacy file, a same-name custom skill, or a file-versus-directory conflict. For those cases, generate an installation dossier for Codex or Claude Code:

```bash
python3 install.py \
  --repo /path/to/repository \
  --conflict agent \
  --agent-plan-dir /safe/path/install-plan
```

This makes no changes to the target repository. It creates:

```text
INSTALL_AGENT.md
merge-plan.json
source-inventory.json
PROMPT.txt
INSTALL_MERGE_REPORT.md
```

Give `PROMPT.txt` to the coding agent, or start the agent with:

```text
install: install this package into /path/to/repository and semantically merge all existing configuration
```

The package includes `sop-install` for that routed workflow. The installation agent must inspect real existing files, back them up, preserve unrelated behavior, merge rather than overwrite, resolve structural blockers, run the deterministic baseline installer, semantically merge project-specific content back from backups, and finish with:

```bash
python3 install.py --repo /path/to/repository --validate-only
```

The root `INSTALL_AGENT.md` and `docs/MERGE_RULES.md` define the authoritative procedure. Plans and reports intentionally contain hashes and paths rather than configuration contents, to avoid copying credentials into logs or chat.

## Deterministic mixed Codex / Claude layouts

The installer now enforces one canonical skill layout for every repository:

```text
skills/                         # the only real skill tree
.agents/skills -> ../skills/    # Codex alias
.claude/skills -> ../skills/    # Claude Code alias
```

Package skills are authored under `adapters/shared/skills` and installed into `{ROOT}/skills`, so the repository intentionally contains the same skill files in both locations. `adapters/shared/skills` is the shared source tree, while `skills/` is the canonical post-install tree that Codex and Claude Code consume through the `../skills/` aliases. They expose the same inode-backed `SKILL.md` files rather than two independently maintained copies.

If an older installation contains physical `.agents/skills` or `.claude/skills` directories, the installer backs them up, merges unrelated skills into `{ROOT}/skills`, replaces known package-managed skills with the current shared version, and then creates the canonical symlinks. Unknown same-path files with different contents are not guessed or overwritten; installation stops for semantic review.

A regular `.codex` file is migrated automatically only when it is valid UTF-8 TOML. The exact original is backed up and copied to `.codex/config.toml`, after which hooks and custom-agent definitions are installed beside it. Codex officially reads project-scoped configuration from `.codex/config.toml`.

```bash
python3 install.py --repo /path/to/repository --dry-run
python3 install.py --repo /path/to/repository
python3 install.py --repo /path/to/repository --validate-only
```

The recognized migration does not print configuration values. The install manifest records only the migration action and paths.

The installer still stops safely for:

- skills symlinks that resolve outside the repository;
- symlink cycles or non-directory targets;
- a `.codex` file that is not valid UTF-8 TOML;
- ambiguous file-versus-directory conflicts elsewhere;
- malformed existing JSON or managed Markdown markers.

For those cases, generate an LLM-assisted semantic merge plan:

```bash
python3 install.py --repo /path/to/repository --conflict agent
```

`--conflict backup` remains available only when a human has already determined that plain relocation is correct. Incompatible nodes and replaced managed files are preserved under:

```text
.loop-engineering-backups/<UTC timestamp>/<original relative path>
```

Existing valid `hooks.json` and `settings.json` files are structurally merged. Older Loop Engineering hook groups are replaced, unrelated user hooks are retained, writes are atomic, and `.agent-loop/install-manifest.json` records installation actions.

See `docs/SHARED_LAYOUTS.md` for the exact resolution and migration rules.

## Reusing Loop Brief input patterns

v15 can store and retrieve reviewed Loop Brief patterns in the OKF LLMWiki. Patterns live under `llmwiki/loop-brief-patterns/` and are used only as precedents. Loop Brief Assistant searches them, asks for explicit field-level confirmation, and proposes new abstractions after a brief is completed. Gatekeeper and Brief Pattern Curator must approve and curate before the Go transaction writes anything.

See `docs/LOOP_BRIEF_PATTERN_MEMORY.md`.

Pattern matching command:

```bash
.agent-loop/bin/okfctl match-brief-pattern \
  --root llmwiki \
  --task-class ci-repair \
  --repository-kind software \
  --risk-class medium \
  --trigger-kind ci-failure \
  --json
```

The command returns metadata and confirmation requirements only; it does not return the pattern body. Loop Brief Assistant opens selected candidates separately with `okfctl show`.
