from __future__ import annotations

import json
from datetime import datetime, timezone

from .common import AuditContext, AuditFinding
from ..policy import REVIEW_OVERDUE_DAYS
from ..._paths import agent_root


def _accepted(repo, run_id: str) -> bool:
    path = repo / agent_root("state", "journal") / f"{run_id}.jsonl"
    try:
        return any((event := json.loads(line)).get("kind") == "external-review" and event.get("accepted_by") == "loopeng review intake" for line in path.read_text(encoding="utf-8").splitlines() if line.strip())
    except (OSError, json.JSONDecodeError):
        return False


def check_external_review_overdue(context: AuditContext) -> list[AuditFinding]:
    now = datetime.now(timezone.utc)
    due: list[str] = []
    for path in (context.repo / agent_root("state", "reports")).glob("*.json") if (context.repo / agent_root("state", "reports")).is_dir() else ():
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            ended = datetime.fromisoformat(str(value.get("ended_at")).replace("Z", "+00:00"))
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            continue
        if any(isinstance(alert, dict) and alert.get("check_id") == "external_review_due" for alert in value.get("alerts", [])) and not _accepted(context.repo, str(value.get("run_id") or path.stem)) and (now - ended).total_seconds() > REVIEW_OVERDUE_DAYS * 86400:
            due.append(str(value.get("run_id") or path.stem))
    return [AuditFinding("external_review_overdue", "warn", f"external review remains due beyond {REVIEW_OVERDUE_DAYS} days", tuple(due[:10]))] if due else []
