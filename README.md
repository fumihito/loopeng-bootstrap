# Loop Engineering Bootstrap

Loop Engineering Bootstrap is a bootstrap kit for operating autonomous AI coding agents (Codex / Claude Code) as auditable loops. The v0.2 line is implemented in Python only (Golang was used in v0.1 but has been retired), minimizes pre-execution blocking, and instead makes every run's results visible through a deterministic Run Report and alerts. Durable memory is updated only through validated transactions to an OKF-format LLMWiki.

The Bootstrap has been self-applied to this repository.

## Core concept

v0.2 consists of four pillars.

1. **Autonomous operation** — Agents can execute runs without sequential human approval. The next turn's input is constructed deterministically from the handoff and Run Report written by the previous run; the model's self-reported memory is not carried forward.
2. **Auditability** — Each run's operations are recorded in a sanitized, append-only journal, and `audit run` performs inspections in a fixed order to generate a Run Report. A completion claim is made only when the Run Report has been generated.
3. **alert-not-block** — Pre-execution blocking is limited to an enumerated set of hard blocks (destructive commands, persistent storage of secrets, invalid memory application, and writes outside the repository). Other deviations do not stop the work and are recorded as alerts in the Run Report. A protected-path change is a warn when intent was declared in advance during the run, and critical when undeclared.

Pending durable-memory drafts are listed with `python3 -m loopeng memory drafts list`; explicit approval uses `memory approve <id> --quote "..."`, while `memory reject` and `memory snooze` retain the audit trail.
4. **OKF LLMWiki memory** — Durable-memory writes are limited to `okf apply` transactions that pass schema validation, namespace containment, proposal_id, and operation-count and document-size limits. Nothing is deleted; history is retained by reversing status with `DEPRECATE`.

## Components

| Component | What |
|---|---|
| `loopeng/` | Python control-layer package (stdlib only). The CLI is `python3 -m loopeng <subcommand>` |
| `loopeng okf` | `init` / `validate` / `apply` / `reindex` / `log` / `query` / `draft` — initialize, search, draft, and update LLMWiki bundles |
| `loopeng learning promote` | Generate validated memory drafts from learning backlog (does not apply them) |
| `loopeng memory curate` | Apply at most three provisional UPSERTs from autonomous namespaces after audit |
| `loopeng memory stats` | Summarize LLMWiki mutation windows and non-LLMWiki commits |
| `loopeng memory efficacy` | Compare signed learning entries with later recurrence and retrieval (`--space current|framework|project|all`) |
| `loopeng inbox --tui` / `--interactive` | Process inbox items with curses or line-oriented fallback |
| `loopeng journal add` | Append events to a run (`run-start` / `intent` / `mutation` / `run-end`, etc.) |
| `loopeng audit run` | Run inspections, generate the Run Report, and write the handoff |
| `loopeng run verify` / `run outcome` | Verify declared acceptance commands or append a human outcome label |
| `loopeng doctor` | Inspect loop state and apply only safe repairs with `--fix` |
| `loopeng inbox` | Show pending human approvals, held decisions, and unresolved outcomes |
| `loopeng run stats` | Display run outcomes and governance-overhead ratios without alerting |
| `loopeng audit export` | Export a sanitized journal, report, sidecar, and git-diff review packet |
| `loopeng review intake` / `request` | Deterministically accept an external-agent review or generate its request |
| `loopeng schedule next` | Generate the next turn's preamble from the previous run's handoff |
| `loopeng status` | Summarize the latest Run Report and learning backlog |
| `loopeng review` | Review recent run results, concerns, and premises; `--triage` guides review and `dag` renders a Mermaid/SVG loop view |
| `loopeng hook` | Claude Code / Codex hook entry point for automatic journal capture and pre-execution hard-block enforcement |
| `./loopeng.py` | Short launcher equivalent to `python3 -m loopeng` |
| `skills/frame-*` | Thinking-framework skill family (the only distributed skills; edit point: `adapters/shared/skills/`) |
| `utils/phase1_gate.py` / `utils/phase1_gate_ext.py` | Executable acceptance gates (must not be changed; the sole basis for completion judgment) |
| `utils/audit_guard.py` | This repository's completion protocol (pre-push audit) |

## Install

Set `LANG` to choose English help; Japanese is used when `LANG` is unset or starts with `ja`.

Python 3.10+ is the prerequisite.

```bash
# frame-* skill のみ(routing プロファイル)
python3 install.py --repo /path/to/repository --profile routing

# skill + loopeng 制御層 + state 雛形(full プロファイル)
python3 install.py --repo /path/to/repository --profile full

# 既存環境の更新。v0.1 の導入痕跡(旧フック・旧ポリシー)を検出した場合は
# 退避アーカイブへ移して v0.2 へ収束させます(削除はしません)
python3 install.py --repo /path/to/repository --profile full --update
```

In environments where v0.1 was installed, the v0.1 materials are archived under `.loop-engineering-backups/<timestamp>/`. The migration is recorded in a migration report under `.agent-loop/state/reports/`. See `docs/INSTALL.md` for details.

## Run cycle

```bash
cd /path/to/repository
# `./loopeng.py` is the equivalent short form of `python3 -m loopeng`.
python3 -m loopeng okf init llmwiki        # 初回のみ

RUN_ID=$(date +%Y%m%d-%H%M%S)
python3 -m loopeng journal add --run "$RUN_ID" \
  --event '{"kind":"run-start","agent":"codex","goal":"..."}'
# ... エージェント作業。protected path に触れる前に intent を宣言し、
#     各ステップを journal に追記する ...
python3 -m loopeng okf apply memory-report.json --bundle llmwiki   # メモリ更新がある場合
python3 -m loopeng journal add --run "$RUN_ID" --event '{"kind":"run-end"}'
python3 -m loopeng audit run --run "$RUN_ID"   # Run Report + handoff を生成
python3 -m loopeng schedule next               # 次ターンの前文
```

When the Run Report contains critical alerts (such as an undeclared protected-path change or a mutation missing from the journal), it receives a banner requiring human review at the top. The banner does not retroactively invalidate the work, but acceptance of completion should be decided after review.

## Documentation map

| Doc | What |
|---|---|
| `docs/ARCHITECTURE.md` | v0.2 architecture and control policy, including hard-block enforcement points. |
| `docs/RUN_REPORT.md` | Run Report schema and journal event conventions. |
| `docs/OKF_LLMWIKI.md` | Durable-memory rules and transactions for OKF LLMWiki. |
| `docs/INSTALL.md` | Profiles, updates, and convergence migration from v0.1. |
| `docs/LOOP_INPUT_GUIDE.md` | Human input required for autonomous runs. |
| `docs/RELEASE_AUDIT.md` | Completion protocol and pre-push audit guard. |
| `docs/DESIGN_PHILOSOPHY.md` | Design principles (single declaration point, mechanism first, and so on). |
| `docs/v0.2-phase1/` | v0.2 redesign implementation instructions and audit records (historical materials). |

## Development

Development of this repository follows these disciplines: changes are performed as journaled runs, and completion is claimed through a Run Report. Release-bound changes must pass the audit record from `utils/audit_guard.py record` before being pushed. The acceptance gates (`utils/phase1_gate.py` / `utils/phase1_gate_ext.py`) must remain GREEN, and the gates themselves must not be changed.

## Status

v0.2 series (active development). The version restarts from the v15 line (v0.1 design) and is not compatible with v0.1. The v0.1 governance mechanisms (Gatekeeper / Sensemaker / Loop Brief, the `route:` / `brief:` / `direct:` entry points, the Go implementation, and OTel/systemd residency) are retired and replaced by convergence migration with `--update`. Implemented in this release: shared hooks, `review:`/`review dag`, and audit-record absorption. Ongoing extensions:

<!-- ongoing-start -->
none
<!-- ongoing-end -->

Memory retrieval follows `index.md → okf query → top K (default 5) document reads`; do not bulk-read `llmwiki/`.
`okf query` defaults to the current framework/project space; use `--space all` for an explicit cross-space read. `memory stats` and `memory efficacy` likewise support `--space` and report only the selected space.
Provisional entries are observations; prefer established entries as the basis for constraints and decisions. `memory curate` may apply only bounded provisional UPSERTs in autonomous namespaces; other drafts require explicit user instruction.

Licensed under the MIT License.
