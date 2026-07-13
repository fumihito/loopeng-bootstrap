from __future__ import annotations

from .common import AuditContext, AuditFinding
from ...inbox import INBOX_STALE_DAYS, collect_inbox


def check_inbox_stale(context: AuditContext) -> list[AuditFinding]:
    stale = [item for item in collect_inbox(context.repo) if float(item.get("age_days", 0)) > INBOX_STALE_DAYS]
    if not stale:
        return []
    return [AuditFinding("inbox_stale", "info", f"oldest inbox item exceeds {INBOX_STALE_DAYS} days", tuple(str(item["target"]) for item in stale[:10]))]
