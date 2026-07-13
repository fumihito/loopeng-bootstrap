from __future__ import annotations

import json
import hashlib
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

from .._paths import agent_root
from ..journal import journal_path, sanitize_event

EXTERNAL_REVIEW_ACTOR = "separate-agent"


def packet_hash(packet: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in packet.rglob("*") if item.is_file() and item.name != "manifest.json"):
        digest.update(str(path.relative_to(packet)).encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _safe_text(value: str) -> str:
    return str(sanitize_event({"text": value}).get("text", ""))


def export_packet(repo: Path, run_id: str) -> Path:
    repo = repo.resolve()
    source_root = repo / agent_root("state")
    target = source_root / "review-packets" / run_id
    target.mkdir(parents=True, exist_ok=True)
    journal = journal_path(repo, run_id)
    events: list[dict[str, Any]] = []
    if journal.is_file():
        for line in journal.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                events.append(sanitize_event(event))
    (target / "journal.json").write_text(json.dumps(events, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    for suffix in ("md", "json"):
        source = source_root / "reports" / f"{run_id}.{suffix}"
        if not source.is_file():
            continue
        if suffix == "json":
            try:
                value = json.loads(source.read_text(encoding="utf-8"))
                value = sanitize_event(value) if isinstance(value, dict) else value
                (target / source.name).write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
            except (OSError, json.JSONDecodeError):
                pass
        else:
            (target / source.name).write_text(_safe_text(source.read_text(encoding="utf-8")), encoding="utf-8")
    proc = subprocess.run(["git", "-C", str(repo), "diff", "--stat", "HEAD~1..HEAD"], text=True, capture_output=True, check=False)
    (target / "git-diff-stat.txt").write_text(_safe_text(proc.stdout), encoding="utf-8")
    source = target / "source"
    source.mkdir(exist_ok=True)
    changed: set[str] = set()
    names = subprocess.run(["git", "-C", str(repo), "diff", "--name-only", "HEAD~1..HEAD"], text=True, capture_output=True, check=False)
    changed.update(line.strip() for line in names.stdout.splitlines() if line.strip())
    for line in subprocess.run(["git", "-C", str(repo), "status", "--porcelain=v1", "--untracked-files=all"], text=True, capture_output=True, check=False).stdout.splitlines():
        if len(line) >= 4:
            changed.add(line[3:])
    source_index: dict[str, int] = {}
    for relative in sorted(changed):
        source_path = repo / relative
        if not source_path.is_file() or relative.startswith(".git/"):
            continue
        try:
            text = _safe_text(source_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            continue
        destination = source / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(text, encoding="utf-8")
        source_index[relative] = len(text.splitlines())
    (target / "source-index.json").write_text(json.dumps(source_index, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    manifest = {"run_id": run_id, "files": sorted(path.name for path in target.iterdir()), "sanitized": True, "review_actor": EXTERNAL_REVIEW_ACTOR, "packet_hash": packet_hash(target)}
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return target
