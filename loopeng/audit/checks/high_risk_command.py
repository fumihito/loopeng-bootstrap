from __future__ import annotations

from .common import AuditContext, AuditFinding, event_strings
from ..policy import HIGH_RISK_COMMAND_PATTERNS


def check_high_risk_command(context: AuditContext) -> list[AuditFinding]:
    for event in context.events:
        for text in event_strings(event):
            lowered = text.lower()
            if any(pattern in lowered for pattern in HIGH_RISK_COMMAND_PATTERNS):
                return [
                    AuditFinding(
                        check_id="high_risk_command",
                        severity="warn",
                        message="high risk command observed",
                        evidence=(text,),
                    )
                ]
    return []
