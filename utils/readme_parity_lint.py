#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

HEADING_RE = re.compile(r"^(#{1,6})\s+(\S.*)$")


def iter_headings(path: Path) -> list[tuple[int, str]]:
    headings: list[tuple[int, str]] = []
    in_fence = False
    fence_marker = ""
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.rstrip("\n")
        stripped = line.lstrip()
        if stripped.startswith("```"):
            marker = stripped[:3]
            if not in_fence:
                in_fence = True
                fence_marker = marker
            elif stripped.startswith(fence_marker):
                in_fence = False
                fence_marker = ""
            continue
        if in_fence:
            continue
        match = HEADING_RE.match(line)
        if match:
            headings.append((len(match.group(1)), match.group(2).strip()))
    return headings


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check that README.md and README.ja.md have matching heading structure.")
    parser.add_argument("--root", type=Path, default=ROOT, help="Repository root.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    en = root / "README.md"
    ja = root / "README.ja.md"
    if not en.is_file():
        print(f"ERROR: missing {en}", file=sys.stderr)
        return 2
    if not ja.is_file():
        print(f"ERROR: missing {ja}", file=sys.stderr)
        return 2

    en_headings = iter_headings(en)
    ja_headings = iter_headings(ja)
    en_levels = [level for level, _ in en_headings]
    ja_levels = [level for level, _ in ja_headings]

    if en_levels != ja_levels:
        print("ERROR: README heading structure mismatch")
        print(f"  README.md levels: {en_levels}")
        print(f"  README.ja.md levels: {ja_levels}")
        print(f"  README.md headings: {[text for _, text in en_headings]}")
        print(f"  README.ja.md headings: {[text for _, text in ja_headings]}")
        return 1

    print(f"OK: README heading structure matches for {len(en_levels)} headings")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
