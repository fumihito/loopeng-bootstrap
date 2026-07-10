from __future__ import annotations

from .common import AuditContext, AuditFinding, SECRET_RE, event_strings


def check_secret_persistence(context: AuditContext) -> list[AuditFinding]:
    for event in context.events:
        for text in event_strings(event):
            if SECRET_RE.search(text):
                return [
                    AuditFinding(
                        check_id="secret_persistence",
                        severity="critical",
                        category="block",
                        message="secret-like material appears in durable artifact input",
                        evidence=(text,),
                    )
                ]
    if context.journal_path.is_file():
        raw = context.journal_path.read_text(encoding="utf-8")
        if SECRET_RE.search(raw):
            return [
                AuditFinding(
                    check_id="secret_persistence",
                    severity="critical",
                    category="block",
                    message="secret-like material appears in journal text",
                    evidence=(str(context.journal_path),),
                )
            ]
    return []
