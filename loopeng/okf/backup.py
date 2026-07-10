from __future__ import annotations

import shutil
from pathlib import Path


def backup_tree(source: Path, backup_root: Path) -> None:
    if not source.exists():
        return
    for path in source.rglob("*"):
        relative = path.relative_to(source)
        target = backup_root / relative
        if path.is_dir():
            target.mkdir(parents=True, exist_ok=True)
        elif path.is_file():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)

