from __future__ import annotations

from datetime import datetime, timezone

from .common import AuditContext, AuditFinding
from ..policy import STAGNATION_DAYS
from ...okf.schema import parse_document


def check_provisional_stagnation(context: AuditContext) -> list[AuditFinding]:
    if not context.bundle_root.is_dir():
        return []
    cutoff = datetime.now(timezone.utc).timestamp() - STAGNATION_DAYS * 86400
    stale: list[str] = []
    for path in context.bundle_root.rglob("*.md"):
        if path.name in {"index.md", "log.md"}:
            continue
        try:
            frontmatter, _ = parse_document(path)
            if frontmatter.get("tier", "established") != "provisional":
                continue
            timestamp = path.stat().st_mtime
            if timestamp < cutoff:
                stale.append(path.relative_to(context.bundle_root).with_suffix("").as_posix())
        except OSError:
            continue
    if not stale:
        return []
    return [AuditFinding("provisional_stagnation", "info", f"{len(stale)} provisional entries exceeded {STAGNATION_DAYS} days", tuple(stale[:10]))]
