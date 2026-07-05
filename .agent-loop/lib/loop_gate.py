"""Shared gate observability and agent registry helpers."""
from __future__ import annotations

import json
import re
import time
from pathlib import Path
from typing import Any

DOT_AGENT_LOOP = "." + "agent-loop"
LOOP_STATUS_CMD = "python3 " + DOT_AGENT_LOOP + "/bin/loop_status.py --gate"
RUNTIME_ROOT = DOT_AGENT_LOOP + "/runtime"
SAFE_COMPONENT = re.compile(r"[^A-Za-z0-9_.-]")


def safe_component(value: Any) -> str:
    return SAFE_COMPONENT.sub("_", str(value or "unknown"))[:120]


def load_json(path: Path, default: Any) -> Any:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default
    return value if isinstance(value, type(default)) else default


def agent_registry_path(root: Path, agent_id: Any) -> Path:
    return root / (RUNTIME_ROOT + "/agents") / f"{safe_component(agent_id)}.json"


def turn_path(root: Path, turn_id: Any) -> Path:
    return root / (RUNTIME_ROOT + "/turns") / safe_component(turn_id)


def artifact_summary(path: Path) -> dict[str, Any]:
    payload = load_json(path, {})
    return {
        "present": path.is_file(),
        "verdict": payload.get("verdict") if isinstance(payload, dict) else None,
        "recorded_at": payload.get("_recorded_at") if isinstance(payload, dict) else None,
        "trusted_subagent": bool(payload.get("_trusted_subagent")) if isinstance(payload, dict) else False,
        "path": path,
    }


def active_session_state(root: Path) -> dict[str, Any]:
    sessions_dir = root / (RUNTIME_ROOT + "/sessions")
    if not sessions_dir.is_dir():
        return {}
    candidates = [path for path in sessions_dir.iterdir() if path.is_file() and path.suffix == ".json"]
    if not candidates:
        return {}
    candidates.sort(key=lambda path: (path.stat().st_mtime_ns, path.name))
    return load_json(candidates[-1], {})


def agent_registry_entries(root: Path, ttl_seconds: int | None = None) -> list[dict[str, Any]]:
    base = root / (RUNTIME_ROOT + "/agents")
    if not base.is_dir():
        return []
    now = time.time()
    entries: list[dict[str, Any]] = []
    for path in sorted(base.glob("*.json")):
        payload = load_json(path, {})
        if not isinstance(payload, dict) or not payload:
            continue
        status = str(payload.get("status") or "").strip().lower()
        if status not in {"spawned", "completed", "persisted", "rejected"}:
            continue
        age_seconds: float | None = None
        pruned = False
        if ttl_seconds is not None:
            try:
                age_seconds = max(0.0, now - path.stat().st_mtime)
            except OSError:
                age_seconds = None
            if age_seconds is not None and status in {"spawned", "completed"} and age_seconds > ttl_seconds:
                pruned = True
        entries.append({
            "agent_id": path.stem,
            "role": payload.get("role"),
            "spawn_turn_id": payload.get("spawn_turn_id"),
            "session_id": payload.get("session_id"),
            "status": "pruned" if pruned else status,
            "lifecycle_status": status,
            "persisted_into_turn_id": payload.get("persisted_into_turn_id"),
            "completed_at": payload.get("completed_at"),
            "recorded_at": payload.get("spawned_at"),
            "age_seconds": age_seconds,
            "path": path,
        })
    return entries


def mutation_gate_check(root: Path, state: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    turn_id = str(state.get("turn_id") or "").strip() or "unknown"
    target = turn_path(root, turn_id)
    gate_path = target / "gatekeeper.json"
    gate = load_json(gate_path, {})
    require_gatekeeper = bool(policy.get("require_gatekeeper_before_mutation", True))
    if not require_gatekeeper:
        return {
            "allowed": True,
            "reason": "PASS",
            "turn_id": turn_id,
            "artifact": "gatekeeper.json",
            "artifact_present": gate_path.is_file(),
            "verdict": gate.get("verdict") if isinstance(gate, dict) else None,
            "recorded_at": gate.get("_recorded_at") if isinstance(gate, dict) else None,
            "trusted_subagent": bool(gate.get("_trusted_subagent")) if isinstance(gate, dict) else False,
        }
    if not gate_path.is_file():
        return {
            "allowed": False,
            "reason": f"No trusted READY Gatekeeper report exists for turn {turn_id}: gatekeeper.json is missing. Run: {LOOP_STATUS_CMD}",
            "turn_id": turn_id,
            "artifact": "gatekeeper.json",
            "artifact_present": False,
            "verdict": None,
            "recorded_at": None,
            "trusted_subagent": False,
        }
    verdict = gate.get("verdict") if isinstance(gate, dict) else None
    trusted = bool(gate.get("_trusted_subagent")) if isinstance(gate, dict) else False
    if trusted and verdict == "READY":
        return {
            "allowed": True,
            "reason": "PASS",
            "turn_id": turn_id,
            "artifact": "gatekeeper.json",
            "artifact_present": True,
            "verdict": verdict,
            "recorded_at": gate.get("_recorded_at") if isinstance(gate, dict) else None,
            "trusted_subagent": trusted,
        }
    state_bits: list[str] = []
    if not trusted:
        state_bits.append("not trusted")
    if verdict != "READY":
        state_bits.append(f"verdict={verdict or 'missing'}")
    detail = " and ".join(state_bits) if state_bits else "not READY"
    return {
        "allowed": False,
        "reason": f"No trusted READY Gatekeeper report exists for turn {turn_id}: gatekeeper.json is {detail}. Run: {LOOP_STATUS_CMD}",
        "turn_id": turn_id,
        "artifact": "gatekeeper.json",
        "artifact_present": True,
        "verdict": verdict,
        "recorded_at": gate.get("_recorded_at") if isinstance(gate, dict) else None,
        "trusted_subagent": trusted,
    }
