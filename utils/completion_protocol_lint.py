#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path


BEGIN = b"<!-- completion-protocol:begin -->\n"
END = b"<!-- completion-protocol:end -->\n"


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check that AGENTS.md and CLAUDE.md share the same completion protocol block.")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root to scan.")
    return parser.parse_args(argv)


def extract_block(path: Path) -> bytes:
    data = path.read_bytes()
    begin = data.find(BEGIN)
    end = data.find(END)
    if begin == -1 or end == -1:
        raise ValueError(f"missing completion protocol markers: {path.name}")
    if data.find(BEGIN, begin + 1) != -1 or data.find(END, end + 1) != -1:
        raise ValueError(f"duplicate completion protocol markers: {path.name}")
    if begin > end:
        raise ValueError(f"completion protocol markers out of order: {path.name}")
    return data[begin : end + len(END)]


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    if not root.exists() or not root.is_dir():
        print(f"ERROR: root does not exist or is not a directory: {root}", file=sys.stderr)
        return 2

    agents = root / "AGENTS.md"
    claude = root / "CLAUDE.md"
    missing = [str(path.name) for path in (agents, claude) if not path.is_file()]
    if missing:
        print(f"ERROR: missing file(s): {', '.join(missing)}", file=sys.stderr)
        return 1

    try:
        agents_block = extract_block(agents)
        claude_block = extract_block(claude)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if agents_block != claude_block:
        print("ERROR: completion protocol blocks diverge between AGENTS.md and CLAUDE.md", file=sys.stderr)
        return 1

    print("OK: AGENTS.md and CLAUDE.md share the same completion protocol block")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
