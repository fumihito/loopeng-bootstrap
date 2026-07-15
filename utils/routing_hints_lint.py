#!/usr/bin/env python3
"""Check that every distributed frame skill has valid routing hints."""
from __future__ import annotations

import argparse
import re
from pathlib import Path


REQUIRED_FIELDS = ("schema", "frame", "priority", "summary")
REQUIRED_BLOCKS = ("prefer", "avoid", "good_for", "bad_for", "signals")
FIELD_RE = re.compile(r"^(schema|frame|priority|summary)\s*=\s*(.+)$", re.M)
BLOCK_RE = re.compile(r"^\[\[(prefer|avoid|good_for|bad_for|signals)\]\]$", re.M)


def iter_frame_dirs(root: Path) -> list[Path]:
    return sorted(path for path in (root / "adapters/shared/skills").glob("frame-*") if path.is_dir())


def lint(root: Path) -> list[str]:
    errors: list[str] = []
    for skill_dir in iter_frame_dirs(root.resolve()):
        name = skill_dir.name
        path = skill_dir / "routing.md"
        if not path.is_file():
            errors.append(f"{name}: missing routing.md")
            continue
        text = path.read_text(encoding="utf-8")
        if "```route-hints-v1" not in text:
            errors.append(f"{name}: missing route-hints-v1 fenced block")
            continue
        body = text.split("```route-hints-v1", 1)[1].split("```", 1)[0]
        fields = {match.group(1): match.group(2).strip() for match in FIELD_RE.finditer(body)}
        for field in REQUIRED_FIELDS:
            if field not in fields:
                errors.append(f"{name}: missing field {field}")
        if fields.get("schema") != '"routing-hints/v1"':
            errors.append(f"{name}: schema must be \"routing-hints/v1\"")
        if fields.get("frame") != f'"{name}"':
            errors.append(f"{name}: frame field must be \"{name}\"")
        if "priority" in fields:
            try:
                priority = int(fields["priority"])
            except ValueError:
                errors.append(f"{name}: priority must be an integer")
            else:
                if not 0 <= priority <= 100:
                    errors.append(f"{name}: priority must be between 0 and 100")
        blocks = set(BLOCK_RE.findall(body))
        for block in REQUIRED_BLOCKS:
            if block not in blocks:
                errors.append(f"{name}: missing [[{block}]] block")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check routing hints for every frame skill.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    errors = lint(args.root)
    if errors:
        print("routing hints lint: FAIL")
        print("\n".join(errors))
        return 1
    print("routing hints lint: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
