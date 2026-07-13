"""Explicit human approval workflow for durable memory drafts."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .._paths import agent_root
from ..journal import EVENT_APPROVAL_REQUEST, EVENT_DECISION, EVENT_MEMORY_DRAFT, append_event
from .apply import apply_report
from .schema import parse_frontmatter

APPROVAL_PROMPT_MAX = 5
SNOOZE_DAYS = 3


def _root(repo: Path) -> Path:
    return repo / agent_root("state", "memory-drafts")


def _id(path: Path, report: dict[str, Any]) -> str:
    value = report.get("draft_id")
    return str(value) if value else path.stem


def _entry(path: Path) -> dict[str, Any] | None:
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
        op = report.get("operations", [{}])[0]
        document = str(op.get("document") or "")
        frontmatter, _ = parse_frontmatter(document)
        return {"id": _id(path, report), "path": path, "type": frontmatter.get("type", "unknown"),
                "concept_id": str(op.get("concept_id") or ""), "report": report}
    except (OSError, json.JSONDecodeError, AttributeError, IndexError, TypeError):
        return None


def pending(repo: Path) -> list[dict[str, Any]]:
    root = _root(repo.resolve())
    if not root.is_dir():
        return []
    return [item for path in sorted(root.glob("*.json")) if (item := _entry(path)) is not None]


def _snooze_path(repo: Path) -> Path:
    return repo / agent_root("state", "approval-snooze.json")


def snoozed(repo: Path, now: datetime | None = None) -> bool:
    try:
        value = json.loads(_snooze_path(repo).read_text(encoding="utf-8"))
        until = datetime.fromisoformat(str(value.get("until")).replace("Z", "+00:00"))
        return (now or datetime.now(timezone.utc)) < until
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return False


def snooze(repo: Path, run_id: str | None = None, days: int = SNOOZE_DAYS) -> dict[str, Any]:
    if days < 0:
        raise ValueError("days must be non-negative")
    now = datetime.now(timezone.utc)
    until = now + timedelta(days=days)
    path = _snooze_path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"until": until.isoformat(), "days": days}, indent=2) + "\n", encoding="utf-8")
    append_event(repo, run_id or "memory-approval", {"kind": EVENT_DECISION, "item": "memory-approval", "choice": "hold", "days": days})
    return {"ok": True, "until": until.isoformat(), "days": days}


def _find(repo: Path, draft_id: str) -> dict[str, Any]:
    for item in pending(repo):
        if item["id"] == draft_id:
            return item
    raise ValueError(f"pending draft not found: {draft_id}")


def list_drafts(repo: Path) -> list[dict[str, Any]]:
    return [{key: value for key, value in item.items() if key not in {"path", "report"}} for item in pending(repo)]


def show_draft(repo: Path, draft_id: str) -> dict[str, Any]:
    item = _find(repo, draft_id)
    return {"id": item["id"], "path": str(item["path"]), "type": item["type"], "concept_id": item["concept_id"], "report": item["report"]}


def approve(repo: Path, draft_ids: list[str], quote: str, run_id: str | None = None, all_drafts: bool = False) -> dict[str, Any]:
    if not quote or len(quote) > 200:
        raise ValueError("--quote is required and must be 200 characters or fewer")
    repo = repo.resolve()
    items = pending(repo)
    if all_drafts:
        if len(items) > APPROVAL_PROMPT_MAX:
            raise ValueError("--all is not allowed when pending drafts exceed approval prompt max; specify IDs")
        selected = items
    else:
        selected = [_find(repo, draft_id) for draft_id in draft_ids]
    if not selected:
        raise ValueError("no drafts selected")
    applied: list[str] = []
    failed: list[dict[str, str]] = []
    for item in selected:
        result = apply_report(repo / "llmwiki", item["path"], repo / agent_root("runtime", "okf-backups"))
        if result.get("ok"):
            destination = _root(repo) / "applied"
            destination.mkdir(parents=True, exist_ok=True)
            item["path"].rename(destination / item["path"].name)
            applied.append(item["id"])
            append_event(repo, run_id or "memory-approval", {"kind": EVENT_MEMORY_DRAFT, "draft": item["id"], "status": "applied"})
        else:
            failed.append({"id": item["id"], "error": "; ".join(map(str, result.get("errors", [])))})
    append_event(repo, run_id or "memory-approval", {"kind": EVENT_DECISION, "item": "memory-approval", "choice": "approve",
                                                       "drafts": [item["id"] for item in selected], "applied": applied,
                                                       "failed": failed, "quote": quote})
    return {"ok": not failed, "applied": applied, "failed": failed}


def reject(repo: Path, draft_id: str, reason: str, run_id: str | None = None) -> dict[str, Any]:
    if not reason.strip():
        raise ValueError("--reason is required")
    item = _find(repo.resolve(), draft_id)
    destination = _root(repo) / "rejected"
    destination.mkdir(parents=True, exist_ok=True)
    item["path"].rename(destination / item["path"].name)
    append_event(repo, run_id or "memory-approval", {"kind": EVENT_DECISION, "item": "memory-approval", "choice": "reject", "drafts": [draft_id], "reason": reason})
    return {"ok": True, "rejected": [draft_id]}


def approval_context(repo: Path, session_id: str | None, run_id: str) -> str | None:
    """Return one bounded prompt, recording only after all reads succeed."""
    # Seed material is repository-owned and becomes pending on the first
    # hook-backed turn, before RUN_STOP has had a chance to curate.
    from .curate import _import_seed_drafts
    _import_seed_drafts(repo.resolve())
    items = pending(repo)
    if not items or snoozed(repo):
        return None
    ids = sorted(str(item["id"]) for item in items)
    digest = hashlib.sha256("\n".join(ids).encode()).hexdigest()
    state_path = repo / agent_root("state", "approval-prompt.json")
    try:
        previous = json.loads(state_path.read_text(encoding="utf-8"))
        if (previous.get("pending_hash") or previous.get("digest")) == digest and previous.get("session_id") == session_id:
            return None
    except FileNotFoundError:
        pass
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        # Corrupt anti-nag state must not become an injection source.
        return None
    lines = [f"{len(items)} memory drafts await approval:"]
    for item in items[:APPROVAL_PROMPT_MAX]:
        lines.append(f"  {item['id']}  {item['type']}  {item['concept_id']}")
    if len(items) > APPROVAL_PROMPT_MAX:
        lines.append(f"  ... and {len(items) - APPROVAL_PROMPT_MAX} more (specify draft IDs)")
    lines.append('Reply to approve/reject (e.g. "approve all", "approve d-...", "reject d-...: <reason>", "later").')
    state_path.parent.mkdir(parents=True, exist_ok=True)
    requested_at = datetime.now(timezone.utc).isoformat()
    state_path.write_text(json.dumps({"pending_hash": digest, "digest": digest, "session_id": session_id,
                                      "last_requested_at": requested_at, "requested_at": requested_at}, indent=2) + "\n", encoding="utf-8")
    append_event(repo, run_id, {"kind": EVENT_APPROVAL_REQUEST, "drafts": ids})
    return "\n".join(lines)
