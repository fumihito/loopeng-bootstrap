from __future__ import annotations

from .common import AuditContext, AuditFinding, event_actor


def check_single_author_memory_change(context: AuditContext) -> list[AuditFinding]:
    report_author = ""
    apply_author = ""
    for event in context.events:
        kind = str(event.get("kind", "")).strip().lower()
        actor = event_actor(event)
        if kind in {"memory_report", "okf_report", "report"} and actor:
            report_author = actor
        if kind in {"memory_apply", "okf_apply", "apply"} and actor:
            apply_author = actor
    if report_author and apply_author and report_author == apply_author:
        return [
            AuditFinding(
                check_id="single_author_memory_change",
                severity="warn",
                message="memory report and apply share the same author",
                evidence=(report_author,),
            )
        ]
    return []
