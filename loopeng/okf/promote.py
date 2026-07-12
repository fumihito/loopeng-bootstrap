from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .draft import _document
from .query import query_bundle
from .schema import validate_document_text, validate_report_payload


def _entries(repo: Path) -> list[tuple[Path, dict[str, Any]]]:
    root = repo / ".agent-loop" / "state" / "learning"
    found = []
    for path in sorted(root.glob("*.json")):
        if path.name in {"learning-health.json", "learning-index.json"}:
            continue
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(value, dict) and not value.get("drafted") and not value.get("applied"):
            found.append((path, value))
    return found


def promote(repo: Path, top: int = 3, ids: list[str] | None = None, type_name: str = "Concept") -> list[dict[str, Any]]:
    selected = _entries(repo)
    def order(item):
        name = item[0].stem
        match = re.search(r"(\d+)$", name)
        return (str(item[1].get("timestamp") or item[1].get("created_at") or ""), int(match.group(1)) if match else 0, name)
    selected.sort(key=order)
    if ids:
        selected = [(p, e) for p, e in selected if p.stem in ids or str(e.get("id")) in ids]
    else:
        selected = selected[:top]
    out = []
    target_dir = repo / ".agent-loop" / "state" / "memory-drafts"
    target_dir.mkdir(parents=True, exist_ok=True)
    for path, entry in selected:
        title = str(entry.get("title") or entry.get("summary") or f"Learning from {path.stem}")
        tags = entry.get("tags") if isinstance(entry.get("tags"), list) else [str(entry.get("kind") or "learning")]
        body = str(entry.get("body") or entry.get("summary") or "Learning candidate pending review.")
        # Query the bundle once without the AND tag filter: duplicate policy
        # is overlap >= 2, not exact tag-set equality.
        matches = query_bundle(repo / "llmwiki", grep=title, status="all") if (repo / "llmwiki").is_dir() else []
        overlap = [m for m in matches if len(set(tags).intersection(m.get("tags", []))) >= 2 or str(title).casefold() in str(m.get("title", "")).casefold()]
        concept_id = overlap[0]["concept_id"] if overlap else f"concepts/{re.sub(r'[^a-z0-9]+', '-', title.casefold()).strip('-') or path.stem}"
        notes = f"duplicate candidate: UPSERT existing {concept_id}" if overlap else "new concept candidate"
        document = _document(type_name, title, [str(t) for t in tags], str(entry.get("source_run_id") or "learning"), float(entry.get("confidence", 0.7)), body)
        errors = validate_document_text(document)
        report = {"schema": "okf-report-v1", "role": "learning-promote", "authority": str(entry.get("source_run_id") or "learning"), "source_learning": str(path), "notes": notes,
                  "operations": [{"action": "UPSERT", "proposal_id": f"proposal-{path.stem}", "concept_id": concept_id, "document": document}]}
        errors.extend(validate_report_payload(report))
        if errors:
            raise ValueError(f"{path}: {'; '.join(errors)}")
        target = target_dir / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".json")
        target.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        entry["drafted"] = str(target)
        path.write_text(json.dumps(entry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        out.append({"learning": str(path), "draft": str(target), "concept_id": concept_id, "duplicate": bool(overlap)})
    return out
