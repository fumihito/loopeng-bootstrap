#!/usr/bin/env python3
"""Rebuild, print, or check deterministic learning-health observations."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

LIB = Path(__file__).resolve().parents[1] / "lib"
sys.path.insert(0, str(LIB))
from learning_observer import markdown_report, rebuild  # noqa: E402


def find_root(start: Path | None = None) -> Path:
    path = (start or Path.cwd()).resolve()
    for candidate in (path, *path.parents):
        if (candidate / ".agent-loop/learning-policy.json").is_file():
            return candidate
    raise SystemExit("Cannot find .agent-loop/learning-policy.json")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("rebuild", "report", "check"), nargs="?", default="report")
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--window", type=int)
    parser.add_argument("--format", choices=("json", "markdown"), default="json")
    parser.add_argument("--fail-on", choices=("degraded", "unhealthy", "never"), default="unhealthy")
    args = parser.parse_args()
    root = find_root(args.repo)
    summary = rebuild(root, window=args.window)
    if args.command in {"report", "check"}:
        if args.format == "markdown":
            sys.stdout.write(markdown_report(summary))
        else:
            print(json.dumps(summary, indent=2, ensure_ascii=False))
    if args.command == "check":
        health = summary.get("health")
        if args.fail_on == "degraded" and health in {"DEGRADED", "UNHEALTHY"}:
            return 3
        if args.fail_on == "unhealthy" and health == "UNHEALTHY":
            return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
