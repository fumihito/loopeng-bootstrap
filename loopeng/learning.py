from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ._paths import agent_root, wiki_space


def learning_root(repo: Path) -> Path:
    return repo / agent_root("state", "learning")


def extract_learning_entries(repo: Path, run_id: str) -> list[dict[str, Any]]:
    journal = repo / agent_root("state", "journal") / f"{run_id}.jsonl"
    if not journal.is_file():
        return []
    entries: list[dict[str, Any]] = []
    for line in journal.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        if event.get("kind") in {"error", "warning", "validation"}:
            entries.append({
                "kind": event.get("kind"),
                "summary": event.get("summary"),
                "source_run_id": run_id,
                "space": wiki_space(repo)[0],
            })
    return entries


def save_learning_entries(repo: Path, run_id: str) -> list[Path]:
    root = learning_root(repo)
    root.mkdir(parents=True, exist_ok=True)
    saved: list[Path] = []
    for index, entry in enumerate(extract_learning_entries(repo, run_id), start=1):
        path = root / f"{run_id}-{index}.json"
        path.write_text(json.dumps(entry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        saved.append(path)
    return saved
