from __future__ import annotations

from .common import AuditContext, AuditFinding
from ...memory_efficacy import INEFFECTIVE_RECURRENCES, collect_efficacy


def check_learning_ineffective(context: AuditContext) -> list[AuditFinding]:
    try:
        value = collect_efficacy(context.repo, windows=("28d",))
    except (OSError, ValueError):
        return []
    bad = [row["concept_id"] for row in value["windows"].get("28d", []) if row["recurrences"] >= INEFFECTIVE_RECURRENCES]
    return [AuditFinding("learning_ineffective", "info", f"stored learning recurred at least {INEFFECTIVE_RECURRENCES} times", tuple(bad[:10]))] if bad else []
