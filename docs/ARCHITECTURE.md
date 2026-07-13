# Architecture

v0.2 removes the old role-pipeline contract and replaces it with four deterministic concerns:

1. autonomous execution without step-by-step human approval;
2. deterministic audit reconstruction through append-only journal and Run Report artifacts;
3. learning extraction into runtime learning state;
4. validated OKF LLMWiki updates through a Python transaction layer.

The runtime surface is intentionally smaller than the v15/v0.1 line:

- journal recording;
- learning extraction;
- next-turn handoff generation;
- audit checks and Run Report generation;
- OKF bundle validation and transactional apply.

The frame-* skill family remains as the only skill family kept from the previous layout. Everything else that used to drive Gatekeeper, Sensemaker, Meta-Evaluator, memory promotion, or loop brief pattern capture is removed from the v0.2 branch.

The design principle is simple: block only what directly threatens safety or bundle integrity, and report everything else as a post-run alert.

## Hook invariants and standard operation

Hooks are the standard automatic event layer for both Claude Code and Codex. The
CLI remains the canonical journal/audit implementation; `loopeng/hooks/` contains
thin platform adapters and one shared handler. Manual `loopeng journal add` is
the fallback for headless runs and scripts. With hooks disabled, the CLI still
works, but automatic journal capture is absent and `journal_coverage` may alert.

The following are normative invariants:

1. A hook must never require an LLM-produced report, JSON artifact, or
   sub-agent output as a condition for stopping or continuing. The v0.1
   `_trusted_subagent` pattern is prohibited.
2. RUN_STOP hooks observe and generate reports only. They always allow stopping;
   they never return a deny, block, or continuation demand.
3. PRE_TOOL may deny only the four `HARD_BLOCKS` declared in `audit/policy.py`,
   and only `destructive_command` and `out_of_repo_write` are evaluated before
   the tool runs. Hook code must not add policy conditions.
4. Hook failures, timeouts, and corrupt state fail open and are recorded.
   Fail-closed behavior is reserved for an established HARD_BLOCK.
5. A PRE_TOOL HARD_BLOCK is evaluated in the fixed order decision → best-effort
   journal record → deny response. Recording cannot relax or create the control
   decision; a journal failure leaves the deny unchanged.

The D10 enforcement point is therefore `PreToolUse` for destructive commands and
out-of-repository writes; secret persistence and invalid OKF applications remain
post-run audit findings.
