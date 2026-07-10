from __future__ import annotations

from .common import AuditContext, AuditFinding, SELF_EVIDENCE_RE
from ...okf.schema import parse_document


def _evidence_is_self_claim(value: object) -> bool:
    if isinstance(value, str):
        return bool(SELF_EVIDENCE_RE.search(value.strip())) or "self" in value.lower()
    if isinstance(value, list):
        strings = [item for item in value if isinstance(item, str)]
        return bool(strings) and all(_evidence_is_self_claim(item) for item in strings)
    return False


def check_unreviewed_claim_persisted(context: AuditContext) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    if not context.bundle_root.is_dir():
        return findings
    for path in sorted(context.bundle_root.rglob("*.md")):
        if path.name in {"index.md", "log.md"}:
            continue
        frontmatter, _ = parse_document(path)
        evidence = frontmatter.get("evidence")
        if evidence and _evidence_is_self_claim(evidence):
            findings.append(
                AuditFinding(
                    check_id="unreviewed_claim_persisted",
                    severity="warn",
                    message="llmwiki entry contains self-only evidence",
                    evidence=(str(path.relative_to(context.repo)),),
                )
            )
    return findings
