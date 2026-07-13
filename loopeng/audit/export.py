from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from .._paths import agent_root
from ..journal import journal_path, sanitize_event

EXTERNAL_REVIEW_ACTOR = "separate-agent"


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
    manifest = {"run_id": run_id, "files": sorted(path.name for path in target.iterdir()), "sanitized": True, "review_actor": EXTERNAL_REVIEW_ACTOR}
    (target / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return target
