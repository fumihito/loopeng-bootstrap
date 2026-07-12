from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from ..._paths import agent_root


@dataclass(frozen=True)
class AuditFinding:
    check_id: str
    severity: str
    message: str
    evidence: tuple[str, ...] = ()
    category: str = "alert"


@dataclass(frozen=True)
class AuditContext:
    repo: Path
    run_id: str
    journal_path: Path
    events: tuple[dict[str, Any], ...]
    changed_paths: tuple[str, ...]
    bundle_root: Path
    learning_root: Path
    report_path: Path


SECRET_RE = re.compile(r"(?i)(password|token|secret|api[_-]?key)\s*[:=]\s*[^\s,;]+")
SELF_EVIDENCE_RE = re.compile(r"(?i)^(self|self[- ]?reported|own claim|unreviewed)$")


def _parse_json_lines(path: Path) -> tuple[dict[str, Any], ...]:
    if not path.is_file():
        return ()
    events: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        try:
            payload = json.loads(raw_line)
        except json.JSONDecodeError:
            continue
        if isinstance(payload, dict):
            events.append(payload)
    return tuple(events)


def _git_status_paths(repo: Path) -> tuple[str, ...]:
    proc = subprocess.run(
        ["git", "-C", str(repo), "status", "--porcelain=v1", "--untracked-files=all"],
        text=True,
        capture_output=True,
        check=False,
    )
    paths: list[str] = []
    for line in proc.stdout.splitlines():
        if len(line) < 4:
            continue
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        paths.append(path)
    return tuple(paths)


def collect_context(repo: Path, run_id: str) -> AuditContext:
    repo = repo.resolve()
    journal_path = repo / agent_root("state", "journal") / f"{run_id}.jsonl"
    bundle_root = repo / "llmwiki"
    learning_root = repo / agent_root("state", "learning")
    report_path = repo / agent_root("state", "reports") / f"{run_id}.md"
    report_rel = report_path.relative_to(repo).as_posix()
    baseline_paths: set[str] = set()
    for event in _parse_json_lines(journal_path):
        if str(event.get("kind") or "").strip().lower() == "run-start":
            baseline = event.get("baseline_changed_paths")
            if isinstance(baseline, list):
                baseline_paths.update(str(item) for item in baseline if isinstance(item, str))
            break
    status_paths = tuple(
        path
        for path in _git_status_paths(repo)
        if path != report_rel
        and path != journal_path.relative_to(repo).as_posix()
        and not path.startswith(agent_root("state", "reports").as_posix())
        and path not in baseline_paths
    )
    return AuditContext(
        repo=repo,
        run_id=run_id,
        journal_path=journal_path,
        events=_parse_json_lines(journal_path),
        changed_paths=status_paths,
        bundle_root=bundle_root,
        learning_root=learning_root,
        report_path=report_path,
    )


def iter_event_texts(event: Any) -> Iterable[str]:
    if isinstance(event, str):
        yield event
        return
    if isinstance(event, dict):
        for value in event.values():
            if isinstance(value, str):
                yield value
            else:
                yield from iter_event_texts(value)
        return
    if isinstance(event, list):
        for item in event:
            yield from iter_event_texts(item)


def event_paths(event: dict[str, Any]) -> set[str]:
    paths: set[str] = set()
    for key, value in event.items():
        key_name = str(key).lower()
        if isinstance(value, str) and any(token in key_name for token in ("path", "file", "target")):
            paths.add(value)
        elif isinstance(value, list) and any(token in key_name for token in ("path", "file", "target")):
            for item in value:
                if isinstance(item, str):
                    paths.add(item)
        elif isinstance(value, dict):
            paths.update(event_paths(value))
    return paths


def event_strings(event: dict[str, Any]) -> tuple[str, ...]:
    return tuple(str(item) for item in iter_event_texts(event))


def event_actor(event: dict[str, Any]) -> str:
    for key in ("actor", "agent", "author", "role"):
        value = event.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""
