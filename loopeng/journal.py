from __future__ import annotations

import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ._paths import agent_root


SECRET_PATTERNS = [
    re.compile(r"(?i)\b(password|token|secret|api[_-]?key)\s*=\s*[^ \n\r\t]+"),
    # Do not rewrite attribute names such as ``token.casefold()`` in source
    # snapshots; they are not credential values and the rewrite can create a
    # false sensitive-assignment finding in the publish safety scan.
    re.compile(r"(?i)\b(password|token|secret|api[_-]?key)\b(?!\s*\.)"),
]

SECRET_KEYS = {"password", "token", "secret", "api_key", "api-key", "api key"}

# The journal event vocabulary has one declaration point.  Producers may still
# accept extension events from headless callers, but events emitted by this
# repository must use one of these names.
EVENT_KINDS = (
    "run-start",
    "run-end",
    "intent",
    "mutation",
    "okf-apply",
    "decision",
    "go-result",
    "review",
    "command",
    "review_failure",
    "hook_failure",
    "retrieval",
    "memory-draft",
    "learning-candidate",
    "skill-used",
    "blocked",
    "outcome",
    "recurrence",
    "external-review",
)

EVENT_RUN_START, EVENT_RUN_END, EVENT_INTENT, EVENT_MUTATION, EVENT_OKF_APPLY, EVENT_DECISION, EVENT_GO_RESULT, EVENT_REVIEW, EVENT_COMMAND, EVENT_REVIEW_FAILURE, EVENT_HOOK_FAILURE, EVENT_RETRIEVAL, EVENT_MEMORY_DRAFT, EVENT_LEARNING_CANDIDATE, EVENT_SKILL_USED, EVENT_BLOCKED, EVENT_OUTCOME, EVENT_RECURRENCE, EVENT_EXTERNAL_REVIEW = EVENT_KINDS
BLOCKED_SUMMARY_MAX = 200
GOVERNANCE_EVENT_KINDS = frozenset({EVENT_RUN_START, EVENT_RUN_END, EVENT_INTENT, EVENT_OKF_APPLY, EVENT_DECISION, EVENT_GO_RESULT, EVENT_REVIEW, EVENT_REVIEW_FAILURE, EVENT_HOOK_FAILURE, EVENT_RETRIEVAL, EVENT_MEMORY_DRAFT, EVENT_OUTCOME, EVENT_RECURRENCE, EVENT_EXTERNAL_REVIEW})


def _sanitize_text(text: str) -> str:
    home = str(Path.home())
    sanitized = text.replace(home, "~")
    for pattern in SECRET_PATTERNS:
        sanitized = pattern.sub(r"\1=<redacted>", sanitized)
    return sanitized


def _git_status_paths(repo: Path) -> list[str]:
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
    return paths


def sanitize_event(event: dict[str, Any]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in event.items():
        key_name = str(key).strip().lower()
        if key_name in SECRET_KEYS or any(token in key_name for token in ("password", "token", "secret", "api_key")):
            result[key] = "<redacted>"
            continue
        if isinstance(value, str):
            result[key] = _sanitize_text(value)
        elif isinstance(value, dict):
            result[key] = sanitize_event(value)
        elif isinstance(value, list):
            result[key] = [sanitize_event(item) if isinstance(item, dict) else _sanitize_text(item) if isinstance(item, str) else item for item in value]
        else:
            result[key] = value
    return result


def journal_path(repo: Path, run_id: str) -> Path:
    return repo / agent_root("state", "journal") / f"{run_id}.jsonl"


def append_event(repo: Path, run_id: str, event: dict[str, Any]) -> Path:
    path = journal_path(repo, run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(sanitize_event(event))
    if str(payload.get("kind") or "").strip().lower() == EVENT_RUN_START:
        payload.setdefault("baseline_changed_paths", _git_status_paths(repo))
    payload.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")
    return path
