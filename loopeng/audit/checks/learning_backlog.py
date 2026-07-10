from __future__ import annotations

from .common import AuditContext, AuditFinding


def check_learning_backlog(context: AuditContext) -> list[AuditFinding]:
    if not context.learning_root.is_dir():
        return []
    backlog = sorted(path for path in context.learning_root.glob("*.json") if path.is_file())
    if not backlog:
        return []
    return [
        AuditFinding(
            check_id="learning_backlog",
            severity="info",
            message="learning entries remain in backlog",
            evidence=(f"backlog={len(backlog)}",),
        )
    ]
