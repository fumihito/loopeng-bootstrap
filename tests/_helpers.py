import shutil
import unittest
from pathlib import Path


requires_go = unittest.skipUnless(
    shutil.which("go"),
    "Go toolchain required: install.py builds okfctl at install time",
)


def class_requires_go(cls):
    return requires_go(cls)


def normalize_repo_permissions(repo: Path) -> None:
    writable_dirs = [
        repo,
        repo / ".agents",
        repo / ".codex",
        repo / ".claude",
        repo / ".agent-loop",
        repo / ".agent-loop/runtime",
        repo / ".agent-loop/docs",
        repo / ".agent-loop/hooks",
    ]
    for path in writable_dirs:
        if path.exists():
            path.chmod(0o755)
