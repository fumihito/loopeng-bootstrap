from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ._paths import agent_root
from .journal import EVENT_OUTCOME, append_event

VERIFY_TIMEOUT_SECONDS = 300
RESULT_TEXT_MAX = 500
RESERVED_RUN_SELECTORS = ("latest", "latest-due", "latest-fail")


def _run_start(repo: Path, run_id: str) -> dict[str, Any] | None:
    for event in _events(repo, run_id):
        if event.get("kind") == "run-start":
            return event
    return None


def _run_start_time(repo: Path, run_id: str, event: dict[str, Any]) -> tuple[str, str]:
    value = str(event.get("timestamp") or event.get("ts") or "")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.isoformat(), run_id
    except ValueError:
        path = repo / agent_root("state", "journal") / f"{run_id}.jsonl"
        return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat(), run_id


def _selector_candidates(repo: Path) -> list[tuple[str, dict[str, Any]]]:
    root = repo.resolve() / agent_root("state", "journal")
    candidates: list[tuple[str, dict[str, Any]]] = []
    for path in sorted(root.glob("*.jsonl")) if root.is_dir() else ():
        run_id = path.stem
        event = _run_start(repo, run_id)
        if event is not None:
            candidates.append((run_id, event))
    return candidates


def _is_due(repo: Path, run_id: str) -> bool:
    report = repo.resolve() / agent_root("state", "reports") / f"{run_id}.json"
    try:
        value = json.loads(report.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    alerts = value.get("alerts", []) if isinstance(value, dict) else []
    if not any(isinstance(alert, dict) and alert.get("check_id") == "external_review_due" for alert in alerts):
        return False
    return not any(event.get("kind") == "external-review" and event.get("accepted_by") == "loopeng review intake" for event in _events(repo, run_id))


def _is_fail(repo: Path, run_id: str) -> bool:
    if any(event.get("kind") == EVENT_OUTCOME and event.get("status") == "fail" for event in _events(repo, run_id)):
        return True
    report = repo.resolve() / agent_root("state", "reports") / f"{run_id}.json"
    try:
        value = json.loads(report.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return isinstance(value, dict) and value.get("outcome") == "fail"


def resolve_run_selector(repo: Path, token: str) -> str:
    """Resolve a reserved run selector, or pass through an explicit run id."""
    if token not in RESERVED_RUN_SELECTORS:
        return token
    repo = repo.resolve()
    candidates = _selector_candidates(repo)
    if token == "latest-due":
        candidates = [(run_id, event) for run_id, event in candidates if _is_due(repo, run_id)]
    elif token == "latest-fail":
        candidates = [(run_id, event) for run_id, event in candidates if _is_fail(repo, run_id)]
    if not candidates:
        raise ValueError(f"no run matches selector '{token}'")
    selected = max(candidates, key=lambda item: _run_start_time(repo, item[0], item[1]))[0]
    print(f"selector '{token}' -> {selected}", file=sys.stderr)
    return selected


def _events(repo: Path, run_id: str) -> list[dict[str, Any]]:
    path = repo / agent_root("state", "journal") / f"{run_id}.jsonl"
    if not path.is_file():
        return []
    result = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            value = json.loads(line)
        except (json.JSONDecodeError, OSError):
            continue
        if isinstance(value, dict):
            result.append(value)
    return result


def _acceptance(repo: Path, run_id: str) -> list[dict[str, Any]]:
    for event in _events(repo, run_id):
        if event.get("kind") == "run-start" and isinstance(event.get("acceptance"), list):
            return [item for item in event["acceptance"] if isinstance(item, dict)]
    return []


def verify_run(repo: Path, run_id: str) -> dict[str, Any]:
    """Execute declared command acceptance checks and append an observed outcome."""
    acceptance = _acceptance(repo, run_id)
    results: list[dict[str, Any]] = []
    command_failed = False
    has_text = False
    for item in acceptance:
        kind = str(item.get("kind") or "")
        if kind == "command":
            command = str(item.get("run") or "")
            if not command:
                result = {"kind":"command", "run": command, "status": "fail", "error": "missing command"}
                command_failed = True
            else:
                try:
                    proc = subprocess.run(command, shell=True, cwd=repo, text=True, capture_output=True, timeout=VERIFY_TIMEOUT_SECONDS, check=False)
                    result = {"kind":"command", "run": command, "status": "pass" if proc.returncode == 0 else "fail", "exit": proc.returncode,
                              "stdout": proc.stdout[-RESULT_TEXT_MAX:], "stderr": proc.stderr[-RESULT_TEXT_MAX:]}
                    command_failed |= proc.returncode != 0
                except subprocess.TimeoutExpired:
                    result = {"kind":"command", "run": command, "status": "fail", "error": "timeout"}
                    command_failed = True
                except OSError as exc:
                    result = {"kind":"command", "run": command, "status": "fail", "error": type(exc).__name__}
                    command_failed = True
            results.append(result)
        elif kind == "text":
            has_text = True
            results.append({"kind":"text", "statement": str(item.get("statement") or ""), "status": "unverified"})
    status = "fail" if command_failed else "unverified" if has_text else "pass"
    event = {"kind": EVENT_OUTCOME, "status": status, "results": results, "source": "verify"}
    append_event(repo, run_id, event)
    return event


def record_human_outcome(repo: Path, run_id: str, status: str, note: str) -> Path:
    if status not in {"pass", "fail"}:
        raise ValueError("status must be pass or fail")
    return append_event(repo, run_id, {"kind": EVENT_OUTCOME, "status": status, "note": note, "source": "human"})
