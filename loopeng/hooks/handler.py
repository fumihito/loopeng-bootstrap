from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .._paths import agent_root
from ..audit.policy import AUDIT_TIMEOUT_SECONDS, LEARNING_CAPTURE_LIMIT, pre_tool_hard_block
from ..journal import append_event
from ..review import MODE_PREFIX
from ..journal import EVENT_COMMAND, EVENT_HOOK_FAILURE, EVENT_LEARNING_CANDIDATE, EVENT_MUTATION, EVENT_REVIEW_FAILURE, EVENT_RUN_END, EVENT_RUN_START
from .events import EventKind, NormalizedEvent

HANDOFF_CONTEXT_LIMIT = 2000
VERSION = "unknown"
try:
    VERSION = (Path(__file__).resolve().parents[2] / "VERSION").read_text(encoding="utf-8").strip()
except OSError:
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _banner(event: NormalizedEvent) -> str:
    return f"[loopeng-bootstrap v{VERSION} | loopeng/v0.2 | {event.event_name}] "


def _state_path(repo: Path) -> Path:
    return repo / agent_root("state", "active-run.json")


def _run_id(event: NormalizedEvent) -> str:
    explicit = event.run_id
    if explicit:
        return explicit
    session = str(event.payload.get("session_id") or "")
    if session:
        return "run-" + hashlib.sha256(session.encode()).hexdigest()[:20]
    return "run-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")


def _load_active(repo: Path) -> dict[str, Any] | None:
    path = _state_path(repo)
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) and value.get("run_id") else None
    except (FileNotFoundError, json.JSONDecodeError, OSError, TypeError):
        return None


def _save_active(repo: Path, value: dict[str, Any]) -> None:
    path = _state_path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _consume_handoff(repo: Path, event: NormalizedEvent) -> str | None:
    path = repo / agent_root("state", "handoff.json")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or value.get("consumed_at"):
            return None
        summary = str(value.get("summary") or "")
        if len(summary) > HANDOFF_CONTEXT_LIMIT:
            summary = summary[:HANDOFF_CONTEXT_LIMIT] + " (see Run Report)"
        value["consumed_at"] = _now()
        value["consumed_by"] = event.platform
        path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return summary or None
    except (FileNotFoundError, json.JSONDecodeError, OSError, TypeError):
        return None


def _start_if_needed(event: NormalizedEvent) -> tuple[str, str | None]:
    active = _load_active(event.repo)
    if active:
        return str(active["run_id"]), None
    run_id = _run_id(event)
    append_event(event.repo, run_id, {
        "kind": EVENT_RUN_START, "agent": event.platform,
        "goal": str(event.payload.get("prompt") or event.payload.get("goal") or ""),
        "session_id": event.payload.get("session_id"),
    })
    _save_active(event.repo, {"run_id": run_id, "session_id": event.payload.get("session_id"), "started_at": _now()})
    return run_id, _consume_handoff(event.repo, event)


def _audit(repo: Path, run_id: str) -> str | None:
    env = os.environ.copy()
    root = str(Path(__file__).resolve().parents[2])
    env["PYTHONPATH"] = root + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "loopeng", "audit", "run", "--run", run_id, "--repo", str(repo)],
            cwd=repo, env=env, text=True, capture_output=True, timeout=AUDIT_TIMEOUT_SECONDS, check=False,
        )
        if proc.returncode == 0:
            return proc.stdout.strip() or None
        return f"audit exited {proc.returncode}: {proc.stderr.strip()[:500]}"
    except (OSError, subprocess.TimeoutExpired) as exc:
        return f"audit failure: {type(exc).__name__}"


def _review_context(event: NormalizedEvent, run_id: str) -> tuple[str | None, str | None]:
    prompt = event.payload.get("prompt") or event.payload.get("prompt_text") or event.payload.get("user_prompt")
    if not isinstance(prompt, str) or not prompt.startswith(MODE_PREFIX):
        return None, None
    remainder = prompt[len(MODE_PREFIX):].strip()
    args = ["--triage"]
    if remainder == "dag":
        args = ["dag"]
    elif remainder.startswith("dag "):
        args = ["dag", "--stage", remainder[4:].strip()]
    elif remainder == "next":
        args = ["--triage", "--next"]
    elif remainder == "full":
        args = []
    elif remainder.startswith("go "):
        args = ["--go", remainder[3:].strip()]
    elif remainder and remainder not in {"next", "full"}:
        # Focus text is preserved for the agent, while triage remains the
        # deterministic injected context.
        remainder = remainder
    env = os.environ.copy()
    root = str(Path(__file__).resolve().parents[2])
    env["PYTHONPATH"] = root + (os.pathsep + env["PYTHONPATH"] if env.get("PYTHONPATH") else "")
    try:
        proc = subprocess.run(
            [sys.executable, "-m", "loopeng", "review", "--repo", str(event.repo), *args],
            cwd=event.repo, env=env, text=True, capture_output=True, timeout=AUDIT_TIMEOUT_SECONDS, check=False,
        )
        if proc.returncode == 0:
            instruction = ("生成された Mermaid コードブロックをそのまま提示し、応答を終える"
                           if remainder == "dag" else "生成された dag 明細をそのまま提示し、応答を終える"
                           if remainder.startswith("dag ") else remainder or "出力末尾の質問を提示したら応答を終え、ユーザーの指示を待つ")
            return proc.stdout.strip(), instruction
        return None, f"review exited {proc.returncode}: {proc.stderr.strip()[:500]}"
    except (OSError, subprocess.TimeoutExpired) as exc:
        return None, f"review failure: {type(exc).__name__}"


def _post_tool(event: NormalizedEvent, run_id: str) -> None:
    payload = event.payload
    tool = str(payload.get("tool_name") or payload.get("tool") or "unknown")
    tool_input = payload.get("tool_input")
    command = tool_input.get("command") if isinstance(tool_input, dict) else None
    kind = EVENT_COMMAND if command or tool.lower() in {"bash", "shell"} else EVENT_MUTATION if tool.lower() in {"apply_patch", "edit", "write"} else EVENT_MUTATION
    success = payload.get("tool_success", payload.get("success", True))
    if "exit_code" in payload:
        success = payload.get("exit_code") == 0
    record: dict[str, Any] = {"kind": kind, "tool_name": tool, "tool_success": bool(success)}
    if command:
        record["command"] = command
    if isinstance(tool_input, dict):
        record["path"] = tool_input.get("path") or tool_input.get("file_path")
    append_event(event.repo, run_id, record)
    if command:
        _capture_recovery(event.repo, run_id, str(command), bool(success))


def _capture_recovery(repo: Path, run_id: str, command: str, success: bool) -> None:
    """Capture only a same-token failure followed by recovery."""
    path = repo / agent_root("state", "journal") / f"{run_id}.jsonl"
    try:
        events = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    except (OSError, json.JSONDecodeError):
        return
    candidates = [event for event in events if event.get("kind") == EVENT_LEARNING_CANDIDATE]
    if len(candidates) >= LEARNING_CAPTURE_LIMIT:
        return
    token = command.strip().split(None, 1)[0] if command.strip() else "unknown"
    previous = None
    for event in reversed(events[:-1]):
        if event.get("kind") == EVENT_COMMAND and not event.get("tool_success", True):
            prior = str(event.get("command") or "").strip().split(None, 1)
            if prior and prior[0] == token:
                previous = str(event.get("command")); break
    if success and previous:
        summary = {"source": "hook-capture", "command_token": token,
                   "failed": previous, "recovered": command}
        candidate = {"kind": EVENT_LEARNING_CANDIDATE, **summary}
        append_event(repo, run_id, candidate)
        learning = repo / agent_root("state", "learning")
        learning.mkdir(parents=True, exist_ok=True)
        target = learning / f"{run_id}-hook-{len(candidates)+1}.json"
        target.write_text(json.dumps({"source": "hook-capture", "source_run_id": run_id,
                                      "summary": f"{token}: failure recovered by subsequent command",
                                      "failed_command": previous, "recovery_command": command},
                                     indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def handle(event: NormalizedEvent) -> dict[str, Any]:
    """Apply the shared lifecycle policy and return a platform-neutral result.

    Exceptions are deliberately fail-open.  The only deny path is the
    imported HARD_BLOCK classifier during PRE_TOOL.
    """
    result: dict[str, Any] = {"run_id": None, "response": {}}
    try:
        if event.kind in {EventKind.SESSION_START, EventKind.PROMPT_SUBMIT}:
            run_id, handoff = _start_if_needed(event)
            result["run_id"] = run_id
            review, review_instruction = _review_context(event, run_id)
            review_error = review_instruction if review is None and review_instruction and review_instruction.startswith(("review exited", "review failure")) else None
            if review_error:
                append_event(event.repo, run_id, {"kind": EVENT_REVIEW_FAILURE, "error": review_error})
            contexts = []
            if handoff:
                contexts.append(handoff)
            if review:
                contexts.append(review)
            if contexts:
                result["response"] = {"hookSpecificOutput": {"additionalContext": _banner(event) + "\n\n".join(contexts)}}
            if review is not None and review_instruction:
                result["response"]["hookSpecificOutput"]["additionalContext"] += "\n\n" + review_instruction
            return result
        active = _load_active(event.repo)
        run_id = str(active.get("run_id")) if active else _run_id(event)
        result["run_id"] = run_id
        if event.kind is EventKind.PRE_TOOL:
            reason = pre_tool_hard_block(event.payload, event.repo)
            if reason:
                result["response"] = {"hookSpecificOutput": {"permissionDecision": "deny", "permissionDecisionReason": _banner(event) + reason}}
            else:
                result["response"] = {"hookSpecificOutput": {"permissionDecision": "allow"}}
            return result
        if event.kind is EventKind.POST_TOOL:
            _post_tool(event, run_id)
            return result
        if event.kind is EventKind.RUN_STOP:
            append_event(event.repo, run_id, {"kind": EVENT_RUN_END, "agent": event.platform})
            audit_error = _audit(event.repo, run_id)
            if audit_error:
                append_event(event.repo, run_id, {"kind": EVENT_HOOK_FAILURE, "error": audit_error})
            try:
                _state_path(event.repo).unlink()
            except FileNotFoundError:
                pass
            # Stop is observation/generation only: never return a block/deny.
            result["response"] = {"continue": True}
            return result
        return result
    except Exception as exc:  # fail-open, including corrupt state files
        result["error"] = f"{type(exc).__name__}: {exc}"
        if event.kind is EventKind.RUN_STOP:
            result["response"] = {"continue": True}
        elif event.kind is EventKind.PRE_TOOL:
            result["response"] = {"hookSpecificOutput": {"permissionDecision": "allow"}}
        return result
