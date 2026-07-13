from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ._paths import agent_root
from .okf.schema import parse_document

INBOX_STALE_DAYS = 14
INBOX_MAX_ITEMS = 100


def _age_timestamp(value: Any, fallback: float) -> datetime:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return datetime.fromtimestamp(fallback, timezone.utc)


def collect_inbox(repo: Path, now: datetime | None = None) -> list[dict[str, Any]]:
    repo = repo.resolve()
    now = now or datetime.now(timezone.utc)
    items: list[dict[str, Any]] = []
    draft_root = repo / agent_root("state", "memory-drafts")
    for path in sorted(draft_root.glob("*.json")) if draft_root.is_dir() else ():
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(value, dict):
            timestamp = _age_timestamp(value.get("created_at"), path.stat().st_mtime)
            draft_id = str(value.get("draft_id") or path.stem)
            items.append({"kind":"draft", "target": draft_id, "path": str(path.relative_to(repo)), "label": "approval", "timestamp": timestamp})
    bundle = repo / "llmwiki"
    for path in bundle.rglob("*.md") if bundle.is_dir() else ():
        if path.name in {"index.md", "log.md"}:
            continue
        try:
            frontmatter, _ = parse_document(path)
        except OSError:
            continue
        if frontmatter.get("tier") == "provisional" and frontmatter.get("status", "active") == "active":
            items.append({"kind":"provisional", "target": str(path.relative_to(repo)), "label": "promotion", "timestamp": _age_timestamp(frontmatter.get("timestamp"), path.stat().st_mtime)})
    journal_root = repo / agent_root("state", "journal")
    accepted_reviews: set[str] = set()
    for path in sorted(journal_root.glob("*.jsonl")) if journal_root.is_dir() else ():
        try:
            events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
        except (OSError, json.JSONDecodeError):
            continue
        for event in events:
            if event.get("kind") == "external-review" and event.get("accepted_by") == "loopeng review intake":
                accepted_reviews.add(path.stem)
            if event.get("kind") == "decision" and event.get("choice") == "hold":
                items.append({"kind":"held", "target": str(event.get("item") or path.stem), "label": "judgment", "timestamp": _age_timestamp(event.get("timestamp"), path.stat().st_mtime)})
    report_root = repo / agent_root("state", "reports")
    for path in sorted(report_root.glob("*.json")) if report_root.is_dir() else ():
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(value, dict) and value.get("outcome") == "unverified":
            items.append({"kind":"outcome", "target": str(value.get("run_id") or path.stem), "label": "unverified", "timestamp": _age_timestamp(value.get("ended_at"), path.stat().st_mtime)})
        if isinstance(value, dict) and path.stem not in accepted_reviews and any(isinstance(alert, dict) and alert.get("check_id") == "external_review_due" for alert in value.get("alerts", [])):
            items.append({"kind":"external-review", "target": str(value.get("run_id") or path.stem), "label": "review", "timestamp": _age_timestamp(value.get("ended_at"), path.stat().st_mtime)})
    items.sort(key=lambda item: item["timestamp"])
    for item in items:
        item["age_days"] = max(0, (now - item["timestamp"]).total_seconds() / 86400)
        item["timestamp"] = item["timestamp"].isoformat()
    return items[:INBOX_MAX_ITEMS]


def render_inbox(repo: Path, now: datetime | None = None) -> str:
    items = collect_inbox(repo, now)
    lines = [f"Inbox ({len(items)} items)", "", "kind  target  label  age_days"]
    lines.extend(f"{item['kind']}  {item['target']}  {item['label']}  {item['age_days']:.1f}" for item in items)
    return "\n".join(lines) + "\n"
