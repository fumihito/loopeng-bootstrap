#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from routing_hints import load_routing_hints, validate_routing_hints_document


def iter_routing_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(root.rglob("routing.md")):
        if not path.is_file():
            continue
        if ".git" in path.relative_to(root).parts:
            continue
        files.append(path)
    return files


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lint routing.md files using the routing-hints/v1 format.")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root to scan.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    if not root.exists() or not root.is_dir():
        print(f"ERROR: root does not exist or is not a directory: {root}", file=sys.stderr)
        return 2

    findings: list[str] = []
    for path in iter_routing_files(root):
        rel = path.relative_to(root)
        try:
            doc = load_routing_hints(path)
            errors = validate_routing_hints_document(doc, expected_frame=path.parent.name)
        except Exception as exc:
            findings.append(f"ERROR: {rel}: {type(exc).__name__}: {exc}")
            continue
        if errors:
            findings.extend(f"ERROR: {rel}: {message}" for message in errors)

    if findings:
        print(f"Found {len(findings)} routing hint issue(s) under {root}:")
        for finding in findings:
            print(finding)
        return 1

    print(f"OK: all routing hint files passed lint under {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
