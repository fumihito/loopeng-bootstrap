#!/usr/bin/env python3
from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


MONITORED_PREFIXES = (
    ".agent-loop/",
    "tests/",
    "utils/",
    "docs/loop-structure",
)
MONITORED_FILES = {"install.py"}
DOCS_PREFIX = "docs/"


@dataclass(frozen=True)
class RefUpdate:
    local_ref: str
    local_sha: str
    remote_ref: str
    remote_sha: str


def run_git(root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        raise RuntimeError((completed.stderr or completed.stdout or "git command failed").strip())
    return completed.stdout.strip()


def parse_updates(stdin_text: str) -> list[RefUpdate]:
    updates: list[RefUpdate] = []
    for raw in stdin_text.splitlines():
        line = raw.strip()
        if not line:
            continue
        parts = line.split()
        if len(parts) != 4:
            continue
        updates.append(RefUpdate(*parts))
    return updates


def is_zero_sha(value: str) -> bool:
    return bool(value) and set(value) == {"0"}


def changed_paths(root: Path, commit: str) -> list[str]:
    output = run_git(root, "diff-tree", "--no-commit-id", "--name-only", "-r", "--root", commit)
    return [line.strip() for line in output.splitlines() if line.strip()]


def commit_range(root: Path, remote_sha: str, local_sha: str) -> list[str]:
    if is_zero_sha(local_sha):
        return []
    if is_zero_sha(remote_sha):
        output = run_git(root, "rev-list", "--reverse", local_sha)
    else:
        output = run_git(root, "rev-list", "--reverse", f"{remote_sha}..{local_sha}")
    return [line.strip() for line in output.splitlines() if line.strip()]


def commit_parent(root: Path, commit: str) -> str | None:
    output = run_git(root, "rev-list", "--parents", "-n", "1", commit)
    parts = output.split()
    if len(parts) < 2:
        return None
    return parts[1]


def is_docs_only(paths: list[str]) -> bool:
    return bool(paths) and all(path.startswith(DOCS_PREFIX) for path in paths)


def is_monitored_path(path: str) -> bool:
    return path in MONITORED_FILES or any(path.startswith(prefix) for prefix in MONITORED_PREFIXES)


def should_guard_commit(paths: list[str]) -> bool:
    if not paths:
        return False
    if is_docs_only(paths):
        return any(path.startswith("docs/loop-structure") for path in paths)
    return any(is_monitored_path(path) for path in paths)


def audit_log_has_parent(root: Path, parent_hash: str) -> bool:
    audit_log = root / "docs/audit-log.md"
    if not audit_log.is_file():
        return False
    return parent_hash in audit_log.read_text(encoding="utf-8")


def evaluate_update(root: Path, update: RefUpdate) -> tuple[bool, str]:
    commits = commit_range(root, update.remote_sha, update.local_sha)
    if not commits:
        return True, ""
    first_commit = commits[0]
    first_paths = changed_paths(root, first_commit)
    if not should_guard_commit(first_paths):
        return True, ""
    parent_hash = commit_parent(root, first_commit)
    if parent_hash is None:
        return False, f"pre-push audit guard cannot evaluate root commit {first_commit[:12]}: no parent hash is available"
    if audit_log_has_parent(root, parent_hash):
        return True, ""
    touched = ", ".join(first_paths[:6]) if first_paths else "<none>"
    return (
        False,
        "pre-push audit guard blocked the push: "
        f"the earliest pushed commit {first_commit[:12]} touches audited paths ({touched}) "
        f"but docs/audit-log.md does not contain its parent hash {parent_hash}.",
    )


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Deterministic pre-push audit guard for release-tracked changes.")
    parser.add_argument("--repo", type=Path, default=Path.cwd(), help="Repository root. Defaults to the current directory.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    root = args.repo.resolve()
    if not root.exists() or not root.is_dir():
        print(f"ERROR: repository root does not exist or is not a directory: {root}", file=sys.stderr)
        return 2

    updates = parse_updates(sys.stdin.read())
    if not updates:
        return 0

    for update in updates:
        try:
            ok, message = evaluate_update(root, update)
        except RuntimeError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 1
        if not ok:
            print(message, file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
