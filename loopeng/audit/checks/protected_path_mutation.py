from __future__ import annotations

from .common import AuditContext, AuditFinding
from ..policy import PROTECTED_PATH_FRAGMENTS


def check_protected_path_mutation(context: AuditContext) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    for path in context.changed_paths:
        if any(fragment in path for fragment in PROTECTED_PATH_FRAGMENTS):
            findings.append(
                AuditFinding(
                    check_id="protected_path_mutation",
                    severity="critical",
                    message="protected path changed",
                    evidence=(path,),
                )
            )
    return findings
