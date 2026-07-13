from __future__ import annotations

import json

from .common import AuditContext, AuditFinding
from ..._paths import agent_root


def check_concurrent_runs_detected(context: AuditContext) -> list[AuditFinding]:
    path = context.repo / agent_root("state", "active-runs.json")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(value, dict):
        return []
    others = sorted(str(run_id) for run_id in value if str(run_id) != context.run_id)
    if not others:
        return []
    return [AuditFinding("concurrent_runs_detected", "warn", f"other active runs detected: {', '.join(others[:10])}", tuple(others[:10]))]
