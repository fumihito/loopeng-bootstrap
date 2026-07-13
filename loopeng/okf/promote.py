from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .draft import _document, add_tier
from .query import query_bundle
from .schema import validate_document_text, validate_report_payload, concept_prefix_for_type
from .schema import parse_frontmatter
from ..locking import repo_lock


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


def promote(repo: Path, top: int = 3, ids: list[str] | None = None, type_name: str = "Concept", autonomous: bool = False) -> list[dict[str, Any]]:
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
        selected_type = str(entry.get("type") or ("Failure Pattern" if autonomous else type_name))
        matches = query_bundle(repo / "llmwiki", grep=title, status="all") if (repo / "llmwiki").is_dir() else []
        overlap = [m for m in matches if len(set(tags).intersection(m.get("tags", []))) >= 2 or str(title).casefold() in str(m.get("title", "")).casefold()]
        concept_id = overlap[0]["concept_id"] if overlap else f"{concept_prefix_for_type(selected_type)}/{re.sub(r'[^a-z0-9]+', '-', title.casefold()).strip('-') or path.stem}"
        notes = f"duplicate candidate: UPSERT existing {concept_id}" if overlap else "new concept candidate"
        signature = entry.get("signature")
        if not signature and entry.get("failed_command"):
            command_prefix = str(entry["failed_command"]).strip().split(None, 1)[0]
            signature = json.dumps({"command_prefix": command_prefix, "error_tokens": [str(token) for token in entry.get("error_tokens", [])]}, ensure_ascii=False)
        document = _document(selected_type, title, [str(t) for t in tags], str(entry.get("source_run_id") or "learning"), float(entry.get("confidence", 0.7)), body, str(signature) if signature else None)
        if autonomous:
            document = add_tier(document, "provisional")
        errors = validate_document_text(document)
        report = {"schema": "okf-report-v1", "role": "learning-promote", "authority": str(entry.get("source_run_id") or "learning"), "source_learning": str(path), "notes": notes,
                  "operations": [{"action": "UPSERT", "proposal_id": f"proposal-{path.stem}", "concept_id": concept_id, "document": document}]}
        errors.extend(validate_report_payload(report))
        if errors:
            raise ValueError(f"{path}: {'; '.join(errors)}")
        target = target_dir / (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + ".json")
        with repo_lock(repo, str(path)):
            target.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            entry["drafted"] = str(target)
            path.write_text(json.dumps(entry, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        out.append({"learning": str(path), "draft": str(target), "concept_id": concept_id, "duplicate": bool(overlap), "namespace": concept_id.split("/", 1)[0], "type": selected_type})
    return out


def establish(repo: Path, concept_ids: list[str]) -> dict[str, Any]:
    """Create explicit-user approval reports; do not apply them here."""
    out = []
    target_dir = repo / ".agent-loop" / "state" / "memory-drafts"
    target_dir.mkdir(parents=True, exist_ok=True)
    for concept_id in concept_ids:
        path = repo / "llmwiki" / f"{concept_id}.md"
        if not path.is_file():
            out.append({"concept_id": concept_id, "error": "missing document"})
            continue
        frontmatter, body = parse_frontmatter(path.read_text(encoding="utf-8"))
        if frontmatter.get("tier", "established") != "provisional":
            out.append({"concept_id": concept_id, "error": "document is not provisional"})
            continue
        frontmatter["tier"] = "established"
        rendered = ["---"]
        for key, value in frontmatter.items():
            rendered.append(f"{key}: {json.dumps(value, ensure_ascii=False) if isinstance(value, (str, list)) else value}")
        rendered.extend(["---", "", body.rstrip("\n"), ""])
        report = {"schema": "okf-report-v1", "role": "explicit-establish", "authority": "user", "operations": [{"action": "UPSERT", "proposal_id": f"establish-{concept_id.replace('/', '-')}", "concept_id": concept_id, "document": "\n".join(rendered)}]}
        target = target_dir / f"establish-{concept_id.replace('/', '-')}.json"
        target.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        out.append({"concept_id": concept_id, "draft": str(target)})
    return {"drafts": out}
