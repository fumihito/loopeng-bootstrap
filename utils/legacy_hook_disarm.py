from __future__ import annotations

import copy
import difflib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


LEGACY_HOOK_EVENTS = (
    "UserPromptSubmit",
    "PreToolUse",
    "Stop",
    "StopFailure",
    "SubagentStart",
    "SubagentStop",
)

LEGACY_HOOK_MARKER = "loop_hook.py"


@dataclass(frozen=True)
class DisarmResult:
    repo: Path
    backup_root: Path | None
    removed_entries: int
    touched_paths: tuple[Path, ...]
    skipped_paths: tuple[Path, ...]


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")


def _load_json(path: Path) -> dict[str, object]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"Top-level JSON object required: {path}")
    return data


def _entry_mentions_legacy_hook(entry: object) -> bool:
    return LEGACY_HOOK_MARKER in json.dumps(entry, sort_keys=True)


def _disarm_payload(payload: dict[str, object]) -> tuple[dict[str, object], int]:
    updated = copy.deepcopy(payload)
    hooks = updated.get("hooks")
    if hooks is None:
        updated["hooks"] = {}
        return updated, 0
    if not isinstance(hooks, dict):
        raise ValueError("hooks field must be an object")

    removed = 0
    for event in LEGACY_HOOK_EVENTS:
        groups = hooks.get(event)
        if groups is None:
            continue
        if not isinstance(groups, list):
            raise ValueError(f"Hook event {event!r} must contain a list")
        filtered_groups: list[object] = []
        for group in groups:
            if not isinstance(group, dict):
                filtered_groups.append(group)
                continue
            group_copy = copy.deepcopy(group)
            inner_hooks = group_copy.get("hooks")
            if not isinstance(inner_hooks, list):
                filtered_groups.append(group_copy)
                continue
            remaining_hooks = [hook for hook in inner_hooks if not _entry_mentions_legacy_hook(hook)]
            removed += len(inner_hooks) - len(remaining_hooks)
            if remaining_hooks:
                group_copy["hooks"] = remaining_hooks
                filtered_groups.append(group_copy)
        hooks[event] = filtered_groups
    return updated, removed


def _backup_path(repo: Path, source: Path, backup_root: Path) -> Path:
    relative = source.relative_to(repo)
    return backup_root / relative


def _render_diff(path: Path, before: str, after: str) -> str:
    diff = difflib.unified_diff(
        before.splitlines(),
        after.splitlines(),
        fromfile=str(path),
        tofile=str(path),
        lineterm="",
    )
    return "\n".join(diff)


def disarm_legacy_hooks(repo: Path, *, dry_run: bool = False) -> DisarmResult:
    repo = repo.expanduser().resolve()
    backup_root = repo / ".loop-engineering-backups" / _stamp()
    touched: list[Path] = []
    skipped: list[Path] = []
    removed_total = 0

    targets = (
        repo / ".claude" / "settings.json",
        repo / ".codex" / "hooks.json",
    )
    for path in targets:
        if not path.exists():
            skipped.append(path)
            continue
        payload = _load_json(path)
        updated, removed = _disarm_payload(payload)
        if removed == 0:
            continue
        touched.append(path)
        removed_total += removed
        before = path.read_text(encoding="utf-8")
        after = json.dumps(updated, indent=2, ensure_ascii=False) + "\n"
        if dry_run:
            diff = _render_diff(path, before, after)
            print(diff or f"[dry-run] no textual diff for {path}")
            continue
        original_mode = path.stat().st_mode
        backup_target = _backup_path(repo, path, backup_root)
        backup_target.parent.mkdir(parents=True, exist_ok=True)
        backup_target.write_text(before, encoding="utf-8")
        os.chmod(path, original_mode | 0o200)
        path.write_text(after, encoding="utf-8")
        os.chmod(path, original_mode)

    if dry_run:
        return DisarmResult(
            repo=repo,
            backup_root=None,
            removed_entries=removed_total,
            touched_paths=tuple(touched),
            skipped_paths=tuple(skipped),
        )

    if touched:
        return DisarmResult(
            repo=repo,
            backup_root=backup_root,
            removed_entries=removed_total,
            touched_paths=tuple(touched),
            skipped_paths=tuple(skipped),
        )
    return DisarmResult(
        repo=repo,
        backup_root=None,
        removed_entries=0,
        touched_paths=tuple(),
        skipped_paths=tuple(skipped),
    )
