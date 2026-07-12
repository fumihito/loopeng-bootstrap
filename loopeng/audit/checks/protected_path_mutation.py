from __future__ import annotations

from .common import AuditContext, AuditFinding
from ..policy import PROTECTED_PATH_FRAGMENTS
from ...journal import EVENT_INTENT


def check_protected_path_mutation(context: AuditContext) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    intents: list[str] = []
    for event in context.events:
        if str(event.get("kind") or "").lower() == EVENT_INTENT and isinstance(event.get("paths"), list):
            intents.extend(str(path) for path in event["paths"] if isinstance(path, str))
    for path in context.changed_paths:
        if any(fragment in path for fragment in PROTECTED_PATH_FRAGMENTS):
            declared = any(path == item or path.startswith(item.rstrip("/") + "/") for item in intents)
            findings.append(
                AuditFinding(
                    check_id="protected_path_mutation",
                    severity="warn" if declared else "critical",
                    message="protected path changed (declared)" if declared else "protected path changed (undeclared)",
                    evidence=(path, "declared" if declared else "undeclared"),
                )
            )
    return findings
