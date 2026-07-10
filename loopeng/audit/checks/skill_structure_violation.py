from __future__ import annotations

from .common import AuditContext, AuditFinding
from utils.skill_structure_lint import validate_skill


def check_skill_structure_violation(context: AuditContext) -> list[AuditFinding]:
    skill_root = context.repo / "adapters" / "shared" / "skills"
    if not skill_root.exists():
        return []
    findings: list[AuditFinding] = []
    for path in sorted(skill_root.glob("frame-*/SKILL.md")):
        for error in validate_skill(path):
            findings.append(
                AuditFinding(
                    check_id="skill_structure_violation",
                    severity="warn",
                    message=error,
                    evidence=(str(path.relative_to(context.repo)),),
                )
            )
    return findings
