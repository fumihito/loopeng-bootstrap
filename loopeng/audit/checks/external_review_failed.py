from __future__ import annotations

import json

from .common import AuditContext, AuditFinding
from ..._paths import agent_root


def check_external_review_failed(context: AuditContext) -> list[AuditFinding]:
    root = context.repo / agent_root("state", "journal")
    failed: list[str] = []
    for path in root.glob("*.jsonl") if root.is_dir() else ():
        try:
            events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        except (OSError, json.JSONDecodeError):
            continue
        for event in events:
            if event.get("kind") != "external-review" or event.get("accepted_by") != "loopeng review intake" or event.get("overall") != "fail":
                continue
            run_id = str(event.get("run_id") or path.stem)
            handled = any(item.get("kind") == "run-start" and item.get("review_of") == run_id for item in events if isinstance(item, dict))
            if not handled:
                failed.append(run_id)
    return [AuditFinding("external_review_failed", "warn", "accepted external review failure has no declared follow-up", tuple(sorted(set(failed))[:10]))] if failed else []
