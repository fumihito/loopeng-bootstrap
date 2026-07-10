from __future__ import annotations

from collections import Counter

from .common import AuditContext, AuditFinding
from ..policy import BUDGET_LIMITS


def _command_like_events(context: AuditContext) -> list[str]:
    kinds: list[str] = []
    for event in context.events:
        kind = str(event.get("kind", "")).strip().lower()
        if kind in {"command", "tool", "mutation", "failure"}:
            kinds.append(kind)
            continue
        if any(key in event for key in ("command", "tool", "mutation")):
            kinds.append(kind or "event")
    return kinds


def check_budget_exceeded(context: AuditContext) -> list[AuditFinding]:
    counts = Counter(_command_like_events(context))
    findings: list[AuditFinding] = []
    limits = {
        "tool": BUDGET_LIMITS["max_tool_calls"],
        "mutation": BUDGET_LIMITS["max_mutations"],
        "failure": BUDGET_LIMITS["max_failures"],
    }
    for name, limit in limits.items():
        if counts.get(name, 0) > limit:
            findings.append(
                AuditFinding(
                    check_id="budget_exceeded",
                    severity="warn",
                    message=f"{name} count exceeded budget",
                    evidence=(f"{name}={counts.get(name, 0)} > {limit}",),
                )
            )

    same_action = 0
    previous_action = ""
    for action in _command_like_events(context):
        if action == previous_action and action:
            same_action += 1
        else:
            same_action = 1 if action else 0
            previous_action = action
    if same_action > BUDGET_LIMITS["same_action_repeats"]:
        findings.append(
            AuditFinding(
                check_id="budget_exceeded",
                severity="warn",
                message="same action repeats exceeded budget",
                evidence=(f"same_action_repeats={same_action} > {BUDGET_LIMITS['same_action_repeats']}",),
            )
        )
    return findings
