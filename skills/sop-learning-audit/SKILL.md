---
name: sop-learning-audit
description: Rebuild deterministic learning-health metrics and invoke the read-only learning-auditor across completed loop turns.
---

# SOP: Learning-health audit

This is an isolated, read-only audit. Do not start Gatekeeper, Sensemaker, Generator, State Steward, or Meta-Evaluator.

Required procedure:
1. Run `python3 .agent-loop/bin/learning_health.py rebuild`.
2. Run `python3 .agent-loop/bin/learning_health.py report --format json` and inspect the generated `.agent-loop/state/learning/learning-health.json`.
3. Invoke exactly one project custom subagent named `learning-auditor`.
4. Give it the deterministic report, policy thresholds, and relevant per-turn learning observations. Do not provide a persuasive conclusion.
5. Wait for the trusted JSON report and present a concise human-readable summary of its verdict, evidence limits, learning debt, recurrence, reuse, adaptation, and recommended policy changes.

Never change policy, lesson records, code, or thresholds during the audit.
