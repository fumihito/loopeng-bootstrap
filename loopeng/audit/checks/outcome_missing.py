from __future__ import annotations

from .common import AuditContext, AuditFinding


def check_outcome_missing(context: AuditContext) -> list[AuditFinding]:
    starts = [event for event in context.events if event.get("kind") == "run-start"]
    if not starts or str(starts[-1].get("mode") or "standard") == "exploratory":
        return []
    if any(event.get("kind") == "outcome" for event in context.events):
        return []
    return [AuditFinding("outcome_missing", "info", "standard run has no outcome event")]
