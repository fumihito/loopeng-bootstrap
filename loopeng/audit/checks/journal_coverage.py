from __future__ import annotations

from .common import AuditContext, AuditFinding, event_paths


def check_journal_coverage(context: AuditContext) -> list[AuditFinding]:
    covered: set[str] = set()
    for event in context.events:
        covered.update(event_paths(event))
    findings: list[AuditFinding] = []
    for path in context.changed_paths:
        normalized = path.replace("\\", "/")
        if normalized == context.report_path.relative_to(context.repo).as_posix():
            continue
        if normalized.startswith("." + "agent-loop" + "/state/learning/"):
            continue
        if normalized not in covered:
            findings.append(
                AuditFinding(
                    check_id="journal_coverage",
                    severity="critical",
                    message="worktree mutation not represented in journal",
                    evidence=(normalized,),
                )
            )
    return findings
