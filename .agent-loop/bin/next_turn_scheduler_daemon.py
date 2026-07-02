#!/usr/bin/env python3
"""Persistent scheduler daemon that replays completed-loop next-turn handoffs."""
from __future__ import annotations

import argparse
import json
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


class _FormatContext(dict[str, str]):
    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def find_root(start: Path | None = None) -> Path:
    path = (start or Path.cwd()).resolve()
    for candidate in (path, *path.parents):
        if (candidate / ".agent-loop/policy.json").is_file():
            return candidate
    raise SystemExit("Cannot find .agent-loop/policy.json")


def load_json(path: Path, default: Any) -> Any:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default
    return value if isinstance(value, type(default)) else default


def atomic_write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    tmp.replace(path)


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False) + "\n")


def runtime_dir(root: Path) -> Path:
    return root / ".agent-loop/runtime/scheduler"


def state_path(root: Path) -> Path:
    return runtime_dir(root) / "state.json"


def event_log_path(root: Path) -> Path:
    return runtime_dir(root) / "events.jsonl"


def last_trigger_path(root: Path) -> Path:
    return runtime_dir(root) / "last-trigger.json"


def turn_root(root: Path) -> Path:
    return root / ".agent-loop/runtime/turns"


def scheduler_policy(root: Path) -> dict[str, Any]:
    data = load_json(root / ".agent-loop/scheduler-policy.json", {})
    return {
        "version": int(data.get("version", 1)),
        "enabled": bool(data.get("enabled", True)),
        "poll_interval_seconds": max(1, int(data.get("poll_interval_seconds", 5))),
        "trigger_command": list(data.get("trigger_command", [])) if isinstance(data.get("trigger_command"), list) else [],
        "notification_command": list(data.get("notification_command", [])) if isinstance(data.get("notification_command"), list) else [],
        "trigger_command_timeout_seconds": max(1, int(data.get("trigger_command_timeout_seconds", 30))),
        "record_events": bool(data.get("record_events", True)),
    }


def load_state(root: Path) -> dict[str, Any]:
    state = load_json(state_path(root), {})
    if not isinstance(state, dict):
        state = {}
    state.setdefault("version", 1)
    state.setdefault("processed_turns", {})
    if not isinstance(state["processed_turns"], dict):
        state["processed_turns"] = {}
    return state


def save_state(root: Path, state: dict[str, Any]) -> None:
    atomic_write(state_path(root), state)


def handoff_signature(handoff: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_turn_id": handoff.get("source_turn_id"),
        "session_id": handoff.get("session_id"),
        "completed_at": handoff.get("completed_at"),
        "final_status": handoff.get("final_status"),
        "ready_for_next_turn": bool(handoff.get("ready_for_next_turn")),
        "next_entry_role": handoff.get("next_entry_role"),
        "trigger_kind": handoff.get("trigger_kind"),
        "trigger_cadence": handoff.get("trigger_cadence"),
    }


def cadence_allows_auto_trigger(cadence: Any) -> bool:
    value = str(cadence or "").strip().lower()
    if not value or value in {"immediate", "external-user-prompt"}:
        return True
    if value == "manual":
        return False
    if value.startswith("on-event:"):
        return False
    return False


def cadence_needs_notification(cadence: Any) -> bool:
    value = str(cadence or "").strip().lower()
    return bool(value) and value not in {"immediate", "external-user-prompt", "manual"} and not value.startswith("on-event:")


def discover_handoffs(root: Path) -> list[tuple[Path, dict[str, Any]]]:
    candidates: list[tuple[str, str, Path, dict[str, Any]]] = []
    root_dir = turn_root(root)
    if not root_dir.is_dir():
        return []
    for turn_dir in root_dir.iterdir():
        if not turn_dir.is_dir():
            continue
        handoff_path = turn_dir / "next-turn.json"
        try:
            handoff = load_json(handoff_path, {})
        except OSError:
            continue
        if not handoff:
            continue
        completed_at = str(handoff.get("completed_at") or "")
        candidates.append((completed_at, turn_dir.name, handoff_path, handoff))
    candidates.sort()
    return [(path, handoff) for _, __, path, handoff in candidates]


def format_args(args: list[str], context: dict[str, str]) -> list[str]:
    fmt = _FormatContext(context)
    return [arg.format_map(fmt) for arg in args]


def run_trigger(command: list[str], context: dict[str, str], timeout_seconds: int) -> dict[str, Any]:
    resolved = format_args(command, context)
    completed = subprocess.run(
        resolved,
        cwd=context["repo"],
        text=True,
        capture_output=True,
        timeout=timeout_seconds,
        check=False,
    )
    action = "triggered" if completed.returncode == 0 else "trigger_failed"
    return {
        "scheduler_action": action,
        "command": resolved,
        "returncode": completed.returncode,
        "stdout_bytes": len(completed.stdout or ""),
        "stderr_bytes": len(completed.stderr or ""),
    }


def emit_event(root: Path, event: dict[str, Any], record_events: bool) -> None:
    if record_events:
        append_jsonl(event_log_path(root), event)
    atomic_write(last_trigger_path(root), event)


def process_once(root: Path) -> dict[str, Any]:
    policy = scheduler_policy(root)
    state = load_state(root)
    state["last_scan_at"] = now()
    processed = state["processed_turns"]
    summary = {
        "scan_at": state["last_scan_at"],
        "disabled": not policy["enabled"],
        "ready_count": 0,
        "skipped_count": 0,
        "triggered_count": 0,
        "failed_count": 0,
        "processed_turns": [],
    }
    if not policy["enabled"]:
        state["last_summary"] = summary
        save_state(root, state)
        return summary
    for handoff_path, handoff in discover_handoffs(root):
        turn_id = str(handoff.get("source_turn_id") or handoff_path.parent.name)
        signature = handoff_signature(handoff)
        current = processed.get(turn_id)
        if current == signature:
            continue
        context = {
            "repo": str(root),
            "turn_id": turn_id,
            "session_id": str(handoff.get("session_id") or ""),
            "handoff_path": str(handoff_path),
            "runtime_dir": str(runtime_dir(root)),
            "scheduler_dir": str(runtime_dir(root)),
            "state_path": str(state_path(root)),
            "event_log_path": str(event_log_path(root)),
            "last_trigger_path": str(last_trigger_path(root)),
            "next_entry_role": str(handoff.get("next_entry_role") or ""),
            "trigger_kind": str(handoff.get("trigger_kind") or ""),
            "trigger_cadence": str(handoff.get("trigger_cadence") or ""),
            "gatekeeper_prompt_path": str(handoff_path.parent / "gatekeeper-prompt.json"),
            "loop_brief_path": str(handoff_path.parent / "loop-brief.json"),
            "state_steward_path": str(handoff_path.parent / "state-steward.json"),
        }
        event = {
            "observed_at": now(),
            "turn_id": turn_id,
            "handoff_path": str(handoff_path),
            "session_id": handoff.get("session_id"),
            "final_status": handoff.get("final_status"),
            "ready_for_next_turn": bool(handoff.get("ready_for_next_turn")),
            "next_entry_role": handoff.get("next_entry_role"),
            "trigger_kind": handoff.get("trigger_kind"),
            "trigger_cadence": handoff.get("trigger_cadence"),
        }
        if not handoff.get("ready_for_next_turn"):
            trigger_info: dict[str, Any] = {"scheduler_action": "skipped_unready"}
            command = policy["notification_command"]
            if command:
                try:
                    notification_context = {**context, "scheduler_action": "notification"}
                    trigger_info = run_trigger(command, notification_context, policy["trigger_command_timeout_seconds"])
                    trigger_info["scheduler_action"] = "notified" if trigger_info["scheduler_action"] == "triggered" else trigger_info["scheduler_action"]
                except subprocess.TimeoutExpired as exc:
                    notification_context = {**context, "scheduler_action": "notification"}
                    trigger_info = {
                        "scheduler_action": "notification_failed",
                        "error": "timeout",
                        "timeout_seconds": policy["trigger_command_timeout_seconds"],
                        "command": format_args(command, notification_context),
                        "command_error": str(exc),
                    }
                except OSError as exc:
                    notification_context = {**context, "scheduler_action": "notification"}
                    trigger_info = {
                        "scheduler_action": "notification_failed",
                        "error": type(exc).__name__,
                        "command": format_args(command, notification_context),
                        "command_error": str(exc),
                    }
            else:
                summary["skipped_count"] += 1
            event.update(trigger_info)
            processed[turn_id] = signature
            emit_event(root, event, policy["record_events"])
            summary["processed_turns"].append(turn_id)
            continue
        summary["ready_count"] += 1
        trigger_info: dict[str, Any] = {"scheduler_action": "recorded"}
        command = policy["trigger_command"]
        cadence = handoff.get("trigger_cadence")
        cadence_kind = "unknown"
        if isinstance(cadence, str):
            normalized = cadence.strip().lower()
            if normalized in {"", "immediate", "external-user-prompt"}:
                cadence_kind = "immediate"
            elif normalized == "manual":
                cadence_kind = "manual"
            elif normalized.startswith("on-event:"):
                cadence_kind = "on-event"
        if command and cadence_allows_auto_trigger(cadence):
            try:
                trigger_info = run_trigger(command, context, policy["trigger_command_timeout_seconds"])
                if trigger_info["scheduler_action"] == "triggered":
                    summary["triggered_count"] += 1
                else:
                    summary["failed_count"] += 1
            except subprocess.TimeoutExpired as exc:
                trigger_info = {
                    "scheduler_action": "trigger_failed",
                    "error": "timeout",
                    "timeout_seconds": policy["trigger_command_timeout_seconds"],
                    "command": format_args(command, context),
                }
                trigger_info["command_error"] = str(exc)
                summary["failed_count"] += 1
            except OSError as exc:
                trigger_info = {
                    "scheduler_action": "trigger_failed",
                    "error": type(exc).__name__,
                    "command": format_args(command, context),
                    "command_error": str(exc),
                }
                summary["failed_count"] += 1
        elif command and cadence_needs_notification(cadence):
            trigger_info = {"scheduler_action": "skipped_unknown_cadence"}
            summary["skipped_count"] += 1
            command = policy["notification_command"]
            if command:
                try:
                    notification_context = {**context, "scheduler_action": "notification"}
                    trigger_info = run_trigger(command, notification_context, policy["trigger_command_timeout_seconds"])
                    trigger_info["scheduler_action"] = "notified" if trigger_info["scheduler_action"] == "triggered" else trigger_info["scheduler_action"]
                except subprocess.TimeoutExpired as exc:
                    trigger_info = {
                        "scheduler_action": "notification_failed",
                        "error": "timeout",
                        "timeout_seconds": policy["trigger_command_timeout_seconds"],
                        "command": format_args(command, context),
                        "command_error": str(exc),
                    }
                except OSError as exc:
                    trigger_info = {
                        "scheduler_action": "notification_failed",
                        "error": type(exc).__name__,
                        "command": format_args(command, context),
                        "command_error": str(exc),
                    }
        elif command:
            trigger_info = {"scheduler_action": "skipped_manual_cadence"}
            summary["skipped_count"] += 1
        event.update(trigger_info)
        processed[turn_id] = signature
        emit_event(root, event, policy["record_events"])
        summary["processed_turns"].append(turn_id)
    active_turn_ids = {str(handoff.get("source_turn_id") or path.parent.name) for path, handoff in discover_handoffs(root)}
    for turn_id in list(processed):
        if turn_id not in active_turn_ids:
            processed.pop(turn_id, None)
    state["processed_turns"] = processed
    state["last_summary"] = summary
    save_state(root, state)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--once", action="store_true", help="Process ready handoffs once and exit.")
    args = parser.parse_args()
    root = find_root(args.repo)

    stop = {"value": False}

    def mark_stop(*_: object) -> None:
        stop["value"] = True

    signal.signal(signal.SIGTERM, mark_stop)
    signal.signal(signal.SIGINT, mark_stop)

    while True:
        summary = process_once(root)
        if args.once:
            print(json.dumps(summary, indent=2, ensure_ascii=False))
            return 0
        if stop["value"]:
            print(json.dumps({"stopped": True, **summary}, indent=2, ensure_ascii=False))
            return 0
        policy = scheduler_policy(root)
        time.sleep(policy["poll_interval_seconds"])


if __name__ == "__main__":
    raise SystemExit(main())
