from __future__ import annotations

from .common import AuditContext, AuditFinding


def check_intent_overdeclaration(context: AuditContext) -> list[AuditFinding]:
    declared = sum(len(event.get("paths", [])) for event in context.events
                   if str(event.get("kind") or "").lower() == "intent" and isinstance(event.get("paths"), list))
    changed = len(context.changed_paths)
    if changed and declared > changed * 3:
        return [AuditFinding("intent_overdeclaration", "warn", "intent declarations exceed three times changed paths", (str(declared), str(changed)))]
    return []
