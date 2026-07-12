from __future__ import annotations

from .common import AuditContext, AuditFinding


def check_learning_backlog(context: AuditContext) -> list[AuditFinding]:
    if not context.learning_root.is_dir():
        return []
    backlog = sorted(path for path in context.learning_root.glob("*.json") if path.is_file())
    drafted = [path for path in backlog if _is_drafted(path)]
    backlog = [path for path in backlog if path not in drafted]
    if not backlog:
        return []
    return [
        AuditFinding(
            check_id="learning_backlog",
            severity="info",
            message="learning entries remain in backlog",
            evidence=(f"backlog={len(backlog)}", f"drafted_unapplied={len(drafted)}"),
        )
    ]


def _is_drafted(path):
    import json
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return bool(isinstance(value, dict) and value.get("drafted") and not value.get("applied"))
    except (OSError, json.JSONDecodeError):
        return False
