from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .query import query_bundle
from .schema import validate_document_text, validate_report_payload


def _document(type_name: str, title: str, tags: list[str], authority: str, confidence: float, body: str) -> str:
    def q(value: object) -> str:
        return json.dumps(value, ensure_ascii=False)
    return "---\n" + "\n".join([
        f"type: {q(type_name)}", f"title: {q(title)}", f"description: {q(title)}",
        f"tags: {q(tags)}", f"timestamp: {q(datetime.now(timezone.utc).isoformat())}",
        "status: active", "sensitivity: internal", f"authority: {q(authority)}",
        f"confidence: {confidence}", "---", "", body or f"# {title}\n\nDraft pending review.", "",
    ])


def add_tier(document: str, tier: str = "provisional") -> str:
    """Add the autonomous tier without changing an existing document."""
    if tier not in {"provisional", "established"}:
        raise ValueError("tier must be provisional or established")
    if document.startswith("---\n"):
        return document.replace("---\n", f"---\ntier: {tier}\n", 1)
    return document


def make_draft(repo: Path, type_name: str, concept_id: str, title: str, tags: list[str],
               body: str = "", authority: str = "user", confidence: float = 0.7,
               notes: str = "") -> tuple[Path, list[dict[str, Any]]]:
    document = _document(type_name, title, tags, authority, confidence, body)
    errors = validate_document_text(document)
    if errors:
        raise ValueError("invalid draft document: " + "; ".join(errors))
    operation = {"action": "UPSERT", "proposal_id": "proposal-1", "concept_id": concept_id,
                 "document": document}
    report = {"schema": "okf-report-v1", "role": "draft-generator", "authority": authority,
              "notes": notes, "operations": [operation]}
    errors = validate_report_payload(report)
    if errors:
        raise ValueError("invalid draft report: " + "; ".join(errors))
    target_dir = repo / ".agent-loop" / "state" / "memory-drafts"
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".json")
    target.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target, query_bundle(repo / "llmwiki", tags=tags, grep=title, status="all") if (repo / "llmwiki").is_dir() else []
