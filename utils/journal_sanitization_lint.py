#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".agent-loop/hooks/loop_hook.py"


def load_hook_module(path: Path):
    spec = importlib.util.spec_from_file_location("loop_hook_journal_lint", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load hook module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lint journal sanitization rules in loop_hook.py.")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root to scan.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    if not root.exists() or not root.is_dir():
        print(f"ERROR: root does not exist or is not a directory: {root}", file=sys.stderr)
        return 2

    hook_path = root / ".agent-loop/hooks/loop_hook.py"
    if not hook_path.is_file():
        print(f"ERROR: hook file does not exist: {hook_path}", file=sys.stderr)
        return 2

    module = load_hook_module(hook_path)
    findings = module.journal_sanitization_findings(hook_path)
    if findings:
        print(f"Found {len(findings)} journal sanitization issue(s) under {root}:")
        for finding in findings:
            print(finding)
        return 1

    print(f"OK: journal sanitization lint passed under {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
