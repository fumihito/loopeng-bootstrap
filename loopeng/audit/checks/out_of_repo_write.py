from __future__ import annotations

from pathlib import Path

from .common import AuditContext, AuditFinding, event_paths


def check_out_of_repo_write(context: AuditContext) -> list[AuditFinding]:
    repo = context.repo.resolve()
    for event in context.events:
        for raw_path in event_paths(event):
            path = Path(raw_path)
            if path.is_absolute() and repo not in path.resolve().parents and path.resolve() != repo:
                return [
                    AuditFinding(
                        check_id="out_of_repo_write",
                        severity="critical",
                        category="block",
                        message="write outside repository root detected",
                        evidence=(raw_path,),
                    )
                ]
            if not path.is_absolute():
                candidate = (repo / path).resolve()
                if repo not in candidate.parents and candidate != repo:
                    return [
                        AuditFinding(
                            check_id="out_of_repo_write",
                            severity="critical",
                            category="block",
                            message="relative path escapes repository root",
                            evidence=(raw_path,),
                        )
                    ]
    return []
