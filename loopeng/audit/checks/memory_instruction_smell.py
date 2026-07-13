from __future__ import annotations

from .common import AuditContext, AuditFinding


def check_memory_instruction_smell(context: AuditContext) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    for event in context.events:
        if event.get("kind") != "okf-apply":
            continue
        warnings = event.get("warnings")
        if isinstance(warnings, dict) and warnings.get("memory_instruction_smell"):
            findings.append(AuditFinding("memory_instruction_smell", "warn", "coarse instruction-smell pattern matched in memory text", tuple(str(item) for item in warnings["memory_instruction_smell"])))
    return findings
