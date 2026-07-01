#!/usr/bin/env python3
"""Inspect deterministic next-turn handoff metadata."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def find_root(start: Path | None = None) -> Path:
    path = (start or Path.cwd()).resolve()
    for candidate in (path, *path.parents):
        if (candidate / ".agent-loop/policy.json").is_file():
            return candidate
    raise SystemExit("Cannot find .agent-loop/policy.json")


def turn_dir(root: Path, turn_id: str) -> Path:
    return root / ".agent-loop/runtime/turns" / turn_id


def load_json(path: Path) -> dict[str, object]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def latest_completed_turn(root: Path) -> Path:
    turns_root = root / ".agent-loop/runtime/turns"
    candidates = []
    if turns_root.is_dir():
        for child in turns_root.iterdir():
            handoff = child / "next-turn.json"
            if handoff.is_file():
                candidates.append((handoff.stat().st_mtime_ns, child))
    if not candidates:
        raise SystemExit("No completed turn handoff was found")
    candidates.sort()
    return candidates[-1][1]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("report", "validate"), nargs="?", default="report")
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--turn-id")
    args = parser.parse_args()
    root = find_root(args.repo)
    turn = turn_dir(root, args.turn_id) if args.turn_id else latest_completed_turn(root)
    handoff = load_json(turn / "next-turn.json")
    if not handoff:
        raise SystemExit(f"missing next-turn.json for {turn.name}")
    if args.command == "validate":
        if not handoff.get("ready_for_next_turn"):
            raise SystemExit("next-turn handoff is not marked ready_for_next_turn")
        if handoff.get("next_entry_role") != "gatekeeper":
            raise SystemExit("next-turn handoff must target gatekeeper")
        return 0
    print(json.dumps(handoff, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
