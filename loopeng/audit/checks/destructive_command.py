from __future__ import annotations

import re

from .common import AuditContext, AuditFinding, event_strings
from ..policy import DESTRUCTIVE_COMMAND_PATTERNS


def check_destructive_command(context: AuditContext) -> list[AuditFinding]:
    for event in context.events:
        for text in event_strings(event):
            lowered = text.lower()
            if any(re.search(pattern, lowered, re.IGNORECASE) for pattern in DESTRUCTIVE_COMMAND_PATTERNS):
                return [
                    AuditFinding(
                        check_id="destructive_command",
                        severity="critical",
                        category="block",
                        message="destructive command pattern detected",
                        evidence=(text,),
                    )
                ]
    return []
