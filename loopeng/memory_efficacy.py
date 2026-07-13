from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ._paths import agent_root
from .okf.schema import parse_document
from ._paths import wiki_space

INEFFECTIVE_RECURRENCES = 2


def _time(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _journals(repo: Path) -> list[tuple[str, dict[str, Any]]]:
    output = []
    for path in (repo / agent_root("state", "journal")).glob("*.jsonl") if (repo / agent_root("state", "journal")).is_dir() else ():
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                output.append((path.stem, event))
    return output


def collect_efficacy(repo: Path, windows: tuple[str, ...] = ("7d", "28d"), now: str | None = None, space: str = "current") -> dict[str, Any]:
    repo = repo.resolve()
    as_of = _time(now) or datetime.now(timezone.utc)
    docs: dict[str, tuple[datetime, str]] = {}
    current, bundle = wiki_space(repo)
    selected_space = current if space == "current" else space
    for path in bundle.rglob("*.md") if bundle.is_dir() else ():
        if path.name in {"index.md", "log.md"}:
            continue
        try:
            frontmatter, _ = parse_document(path)
        except OSError:
            continue
        signature = frontmatter.get("signature")
        if selected_space != "all" and str(frontmatter.get("space") or "unknown") != selected_space:
            continue
        stored = _time(frontmatter.get("timestamp"))
        if signature and stored:
            concept_id = path.relative_to(bundle).with_suffix("").as_posix()
            docs[concept_id] = (stored, str(signature))
    output: dict[str, Any] = {"space": selected_space, "coverage": {"signed": len(docs), "total": 0}, "windows": {}}
    events = _journals(repo)
    for label in windows:
        days = int(label[:-1])
        cutoff = as_of - timedelta(days=days)
        rows = []
        for concept_id, (stored, signature) in docs.items():
            recurrences = [event for _, event in events if event.get("kind") == "recurrence" and event.get("concept_id") == concept_id and (_time(event.get("timestamp")) or as_of) >= stored and (_time(event.get("timestamp")) or as_of) >= cutoff]
            retrievals = [(run, event) for run, event in events if event.get("kind") == "retrieval" and concept_id in event.get("read_ids", []) and (_time(event.get("timestamp")) or as_of) >= cutoff]
            same_run = sum(1 for run, _ in retrievals if any(r_run == run for r_run, _ in [(r_run, r) for r_run, r in events if r.get("kind") == "recurrence" and r.get("concept_id") == concept_id]))
            rows.append({"concept_id": concept_id, "signature": signature, "recurrences": len(recurrences), "retrievals": len(retrievals), "retrieved_then_recurred": same_run})
        output["windows"][label] = rows
    output["coverage"]["total"] = len(docs)
    return output


def render_efficacy(value: dict[str, Any]) -> str:
    lines = [f"space: {value.get('space', 'current')}", f"signature coverage: {value['coverage']['signed']}/{value['coverage']['total']}"]
    for window, rows in value["windows"].items():
        lines.append(f"{window}:")
        lines.extend(f"- {row['concept_id']}: recurrence={row['recurrences']} retrieval={row['retrievals']} retrieved_then_recurred={row['retrieved_then_recurred']}" for row in rows)
    return "\n".join(lines) + "\n"
