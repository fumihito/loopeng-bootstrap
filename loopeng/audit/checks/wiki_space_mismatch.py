from __future__ import annotations

from .common import AuditContext, AuditFinding
from ..._paths import wiki_space
from ...okf.schema import parse_document


def check_wiki_space_mismatch(context: AuditContext) -> list[AuditFinding]:
    expected, bundle = wiki_space(context.repo)
    mismatches = []
    if not bundle.is_dir():
        return []
    for path in sorted(bundle.rglob("*.md")):
        if path.name in {"index.md", "log.md"}:
            continue
        try:
            frontmatter, _ = parse_document(path)
        except OSError:
            continue
        actual = frontmatter.get("space")
        if actual in {"framework", "project"} and actual != expected:
            mismatches.append(path.relative_to(bundle).with_suffix("").as_posix())
    if not mismatches:
        return []
    return [AuditFinding("wiki_space_mismatch", "warn", f"LLMWiki entries are labeled for another space (expected {expected})", tuple(mismatches[:20]))]
