from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ._paths import agent_root


SECRET_PATTERNS = [
    re.compile(r"(?i)\b(password|token|secret|api[_-]?key)\s*=\s*[^ \n\r\t]+"),
    re.compile(r"(?i)\b(password|token|secret|api[_-]?key)\b"),
]

SECRET_KEYS = {"password", "token", "secret", "api_key", "api-key", "api key"}


def _sanitize_text(text: str) -> str:
    home = str(Path.home())
    sanitized = text.replace(home, "~")
    for pattern in SECRET_PATTERNS:
        sanitized = pattern.sub(r"\1=<redacted>", sanitized)
    return sanitized


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
            result[key] = [sanitize_event(item) if isinstance(item, dict) else item for item in value]
        else:
            result[key] = value
    return result


def journal_path(repo: Path, run_id: str) -> Path:
    return repo / agent_root("state", "journal") / f"{run_id}.jsonl"


def append_event(repo: Path, run_id: str, event: dict[str, Any]) -> Path:
    path = journal_path(repo, run_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(sanitize_event(event))
    payload.setdefault("timestamp", datetime.now(timezone.utc).isoformat())
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(payload, sort_keys=True) + "\n")
    return path
