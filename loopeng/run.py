from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from ._paths import agent_root
from .journal import EVENT_OUTCOME, append_event

VERIFY_TIMEOUT_SECONDS = 300
RESULT_TEXT_MAX = 500


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
