#!/usr/bin/env python3
from __future__ import annotations

import argparse
from pathlib import Path

from legacy_hook_disarm import disarm_legacy_hooks


def main() -> int:
    parser = argparse.ArgumentParser(description="Remove legacy loop_hook registrations from installed repos.")
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    result = disarm_legacy_hooks(args.repo, dry_run=args.dry_run)
    for path in result.skipped_paths:
        print(f"Skipped missing file: {path}")
    if result.backup_root is not None:
        print(f"Backups: {result.backup_root}")
    print(f"Removed {result.removed_entries} legacy hook entr{'y' if result.removed_entries == 1 else 'ies'}")
    if args.dry_run:
        print("Dry-run complete; no files were modified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
