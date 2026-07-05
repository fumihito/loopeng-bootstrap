#!/usr/bin/env python3
"""Render deterministic loop-health status views from runtime artifacts."""
from __future__ import annotations

import argparse
import html
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

LIB = Path(__file__).resolve().parents[1] / "lib"
if str(LIB) not in sys.path:
    sys.path.insert(0, str(LIB))

from learning_observer import build_turn_observation, compute_health, safe_dict  # noqa: E402
from loop_gate import active_session_state, agent_registry_entries, artifact_summary, mutation_gate_check, turn_path as gate_turn_path  # noqa: E402


@dataclass
class TurnStatus:
    turn_id: str
    path: Path
    rel_path: str
    started_at: datetime | None
    completed_at: datetime | None
    final_status: str
    routing_mode: str
    validation_ok: bool | None
    scheduler_action: str | None
    scheduler_observed_at: datetime | None
    handoff_ready: bool
    handoff_unconsumed: bool
    next_turn_id: str | None
    brief_goal: str | None
    unverified_claim_count: int


def now() -> datetime:
    return datetime.now(timezone.utc)


def find_root(start: Path | None = None) -> Path:
    path = (start or Path.cwd()).resolve()
    for candidate in (path, *path.parents):
        if (candidate / ".agent-loop/policy.json").is_file():
            return candidate
    raise SystemExit("Cannot find .agent-loop/policy.json")


def load_json(path: Path, default: Any) -> Any:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default
    return value if isinstance(value, type(default)) else default


def parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def format_duration(seconds: float) -> str:
    total = max(0, int(seconds))
    days, rem = divmod(total, 86400)
    hours, rem = divmod(rem, 3600)
    minutes, secs = divmod(rem, 60)
    parts: list[str] = []
    if days:
        parts.append(f"{days}d")
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if secs or not parts:
        parts.append(f"{secs}s")
    return " ".join(parts)


def rel_link(output_path: Path, target: Path) -> str:
    return os.path.relpath(target, output_path.parent)


def scheduler_events(root: Path) -> dict[str, dict[str, Any]]:
    path = root / ".agent-loop/runtime/scheduler/events.jsonl"
    events: dict[str, dict[str, Any]] = {}
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return events
    for line in raw.splitlines():
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        turn_id = str(event.get("turn_id") or "").strip()
        if turn_id:
            events[turn_id] = event
    return events


def turn_dirs(root: Path) -> list[Path]:
    base = root / ".agent-loop/runtime/turns"
    if not base.is_dir():
        return []
    turns: list[Path] = [path for path in base.iterdir() if path.is_dir() and (path / "turn.json").is_file()]
    turns.sort(key=lambda path: (
        str(parse_timestamp(load_json(path / "turn.json", {}).get("started_at")) or ""),
        str(parse_timestamp(load_json(path / "turn.json", {}).get("completed_at")) or ""),
        path.name,
    ))
    return turns


def status_thresholds(policy: dict[str, Any]) -> dict[str, Any]:
    thresholds = policy.get("status_thresholds")
    if not isinstance(thresholds, dict):
        raise SystemExit("Missing .agent-loop/policy.json status_thresholds")
    required = (
        "recent_turn_count",
        "unconsumed_handoff_poll_cycles",
        "pass_statuses",
        "amber_statuses",
        "red_statuses",
        "in_progress_statuses",
    )
    for key in required:
        if key not in thresholds:
            raise SystemExit(f"Missing .agent-loop/policy.json status_thresholds.{key}")
    return thresholds


def classify_status(final_status: str, thresholds: dict[str, Any]) -> str:
    status = final_status.strip().upper()
    if status in {str(item).upper() for item in thresholds["pass_statuses"]}:
        return "pass"
    if status in {str(item).upper() for item in thresholds["amber_statuses"]}:
        return "amber"
    if status in {str(item).upper() for item in thresholds["red_statuses"]}:
        return "red"
    if not status or status in {str(item).upper() for item in thresholds["in_progress_statuses"]}:
        return "gray"
    return "gray"


def load_turn_status(root: Path, output_path: Path, turn_path: Path, scheduler_event: dict[str, Any] | None, thresholds: dict[str, Any], poll_interval_seconds: int, include_brief: bool) -> TurnStatus:
    turn = load_json(turn_path / "turn.json", {})
    if not isinstance(turn, dict):
        turn = {}
    validation = load_json(turn_path / "validation.json", {})
    next_turn = load_json(turn_path / "next-turn.json", {})
    loop_brief = load_json(turn_path / "loop-brief.json", {})
    meta = load_json(turn_path / "meta-evaluator.json", {})

    started_at = parse_timestamp(turn.get("started_at"))
    completed_at = parse_timestamp(turn.get("completed_at"))
    final_status = str(turn.get("final_status") or "")
    scheduler_observed_at = parse_timestamp(scheduler_event.get("observed_at")) if scheduler_event else None
    handoff_ready = bool(next_turn.get("ready_for_next_turn")) if isinstance(next_turn, dict) else False
    handoff_unconsumed = False
    if handoff_ready and completed_at and scheduler_event is None:
        age = (now() - completed_at).total_seconds()
        handoff_unconsumed = age >= poll_interval_seconds * int(thresholds["unconsumed_handoff_poll_cycles"])

    brief_goal: str | None = None
    if include_brief and isinstance(loop_brief, dict):
        brief_goal = str(loop_brief.get("goal") or loop_brief.get("outcome") or loop_brief.get("summary") or "").strip() or None

    return TurnStatus(
        turn_id=turn_path.name,
        path=turn_path,
        rel_path=rel_link(output_path, turn_path),
        started_at=started_at,
        completed_at=completed_at,
        final_status=final_status,
        routing_mode=str(turn.get("routing_mode") or ""),
        validation_ok=bool(validation.get("ok")) if isinstance(validation, dict) and "ok" in validation else None,
        scheduler_action=str(scheduler_event.get("scheduler_action")) if scheduler_event else None,
        scheduler_observed_at=scheduler_observed_at,
        handoff_ready=handoff_ready,
        handoff_unconsumed=handoff_unconsumed,
        next_turn_id=str(next_turn.get("source_turn_id") or "").strip() if isinstance(next_turn, dict) else None,
        brief_goal=brief_goal,
        unverified_claim_count=len(safe_dict(meta).get("unverified", [])) if isinstance(safe_dict(meta).get("unverified"), list) else 0,
    )


def collect_model(root: Path, output_path: Path, include_brief: bool = False) -> dict[str, Any]:
    policy = load_json(root / ".agent-loop/policy.json", {})
    thresholds = status_thresholds(policy)
    scheduler_policy = load_json(root / ".agent-loop/scheduler-policy.json", {})
    learning_policy = load_json(root / ".agent-loop/learning-policy.json", {})
    poll_interval_seconds = int(scheduler_policy.get("poll_interval_seconds", 5))

    turns = turn_dirs(root)
    events = scheduler_events(root)
    turn_views = [load_turn_status(root, output_path, turn_path, events.get(turn_path.name), thresholds, poll_interval_seconds, include_brief) for turn_path in turns]
    recent_turns = turn_views[-int(thresholds["recent_turn_count"]):]
    pass_turns = [turn for turn in turn_views if turn.final_status.upper() == "PASS" and turn.completed_at is not None]
    observations = [build_turn_observation(turn.path) for turn in pass_turns]

    if observations:
        current_health = compute_health(observations, learning_policy, window=int(learning_policy["window_turns"]))
    else:
        current_health = {
            "health": "UNKNOWN",
            "reasons": ["未稼働"],
            "metrics": {"learning_debt_score": 0},
            "window": {"observed_turns": 0, "all_completed_turns": 0},
        }

    min_turns = int(learning_policy["minimum_turns_for_health"])
    trend_available = len(pass_turns) >= min_turns
    trend_points: list[dict[str, Any]] = []
    if trend_available:
        for index in range(1, len(pass_turns) + 1):
            prefix_observations = observations[:index]
            summary = compute_health(prefix_observations, learning_policy, window=int(learning_policy["window_turns"]), include_trend=False)
            validation_successes = sum(1 for turn in pass_turns[:index] if turn.validation_ok)
            trend_points.append({
                "turn_id": pass_turns[index - 1].turn_id,
                "learning_debt_score": int(summary.get("metrics", {}).get("learning_debt_score", 0) or 0),
                "validation_success_rate": round(validation_successes / index, 4),
            })

    unresolved = [turn for turn in turn_views if turn.final_status and turn.final_status.upper() != "PASS"]
    unresolved_counts = {
        "ESCALATE": sum(1 for turn in unresolved if turn.final_status.upper() == "ESCALATE"),
        "WATCHDOG_TRIPPED": sum(1 for turn in unresolved if turn.final_status.upper() == "WATCHDOG_TRIPPED"),
        "PROTECTED_DRIFT": sum(1 for turn in unresolved if turn.final_status.upper() == "PROTECTED_DRIFT"),
    }
    latest_pass = max((turn.completed_at for turn in pass_turns if turn.completed_at is not None), default=None)
    latest_turn = turn_views[-1] if turn_views else None
    unconsumed = [turn for turn in turn_views if turn.handoff_unconsumed]

    return {
        "root": root,
        "output_path": output_path,
        "policy": policy,
        "thresholds": thresholds,
        "scheduler_policy": scheduler_policy,
        "learning_policy": learning_policy,
        "turns": turn_views,
        "recent_turns": recent_turns,
        "pass_turns": pass_turns,
        "current_health": current_health,
        "trend_available": trend_available,
        "trend_points": trend_points,
        "unresolved": unresolved,
        "unresolved_counts": unresolved_counts,
        "latest_pass": latest_pass,
        "latest_turn": latest_turn,
        "unconsumed": unconsumed,
        "minimum_turns_for_health": min_turns,
    }


def format_relative_time(start: datetime | None, end: datetime | None = None) -> str:
    if start is None:
        return "unknown"
    moment = end or now()
    delta = moment - start
    if delta.total_seconds() < 0:
        delta = -delta
    return format_duration(delta.total_seconds())


def render_text(model: dict[str, Any]) -> str:
    turns = model["turns"]
    if not turns:
        return "未稼働\n"
    latest = model["latest_turn"]
    health = model["current_health"]
    lines = [
        "Loop Status",
        f"Latest turn: {latest.turn_id if latest else 'unknown'} {latest.final_status or 'IN_PROGRESS'}",
        f"Unconsumed handoffs: {len(model['unconsumed'])}",
        "Unresolved terminals: "
        + ", ".join(f"{status} {count}" for status, count in model["unresolved_counts"].items()),
        f"Learning health: {health.get('health')} (debt {health.get('metrics', {}).get('learning_debt_score', 0)})",
    ]
    if model["latest_pass"] is not None:
        lines.append(f"Cadence: PASS since {format_relative_time(model['latest_pass'])}")
    else:
        lines.append("Cadence: 未稼働")
    if not model["trend_available"]:
        lines.append("Trend: データ不足")
    return "\n".join(lines) + "\n"



def registry_ttl_seconds(policy: dict[str, Any]) -> int | None:
    value = policy.get("agent_registry_ttl_seconds")
    if value is None:
        value = policy.get("registry_ttl_seconds")
    if isinstance(value, (int, float)) and value >= 0:
        return int(value)
    return None


def collect_gate_model(root: Path) -> dict[str, Any]:
    policy = load_json(root / (("." + "agent-loop") + "/policy.json"), {})
    state = active_session_state(root)
    turn_id = str(state.get("turn_id") or "").strip()
    turn_dir = gate_turn_path(root, turn_id) if turn_id else None
    empty = {"present": False, "verdict": None, "recorded_at": None, "trusted_subagent": False, "path": None}
    gatekeeper = artifact_summary(turn_dir / "gatekeeper.json") if turn_dir is not None else empty
    sensemaker = artifact_summary(turn_dir / "sensemaker.json") if turn_dir is not None else empty
    prior_gatekeeper = artifact_summary(turn_dir / "prior-gatekeeper.json") if turn_dir is not None else empty
    registry = agent_registry_entries(root, registry_ttl_seconds(policy))
    gate_check = mutation_gate_check(root, state, policy)
    return {
        "root": root,
        "policy": policy,
        "session": state,
        "active_turn_id": turn_id or None,
        "routing_mode": str(state.get("routing_mode") or ""),
        "entry_role": str(state.get("entry_role") or ""),
        "gatekeeper": gatekeeper,
        "sensemaker": sensemaker,
        "prior_gatekeeper": prior_gatekeeper,
        "registry": [item for item in registry if item.get("status") in {"spawned", "completed", "pruned"}],
        "mutation_gate": gate_check,
    }


def render_gate_text(model: dict[str, Any]) -> str:
    session = model.get("session") if isinstance(model.get("session"), dict) else {}
    lines = ["Loop Gate"]
    lines.append(f"session_id: {session.get('session_id')}")
    lines.append(f"turn_id: {model.get('active_turn_id')}")
    lines.append(f"routing_mode: {model.get('routing_mode')}")
    lines.append(f"entry_role: {model.get('entry_role')}")
    for label in ("gatekeeper", "sensemaker", "prior_gatekeeper"):
        item = model.get(label) if isinstance(model.get(label), dict) else {}
        lines.append(f"{label}: present={item.get('present')} verdict={item.get('verdict')} recorded_at={item.get('recorded_at')}")
    registry = model.get("registry") if isinstance(model.get("registry"), list) else []
    if registry:
        lines.append("registry pending:")
        for item in registry:
            lines.append(f"- {item.get('agent_id')}: role={item.get('role')} status={item.get('status')} spawn_turn_id={item.get('spawn_turn_id')}")
    else:
        lines.append("registry pending: none")
    gate_check = model.get("mutation_gate") if isinstance(model.get("mutation_gate"), dict) else {}
    lines.append(f"mutation gate: {'PASS' if gate_check.get('allowed') else gate_check.get('reason')}")
    return "\n".join(lines) + "\n"

def sparkline(values: list[float], *, label: str, low: str, high: str) -> str:
    if not values:
        return f'<div class="sparkline empty"><span class="sparkline-label">{html.escape(label)}</span><span class="sparkline-note">データ不足</span></div>'
    maximum = max(values)
    minimum = min(values)
    span = maximum - minimum
    bars: list[str] = []
    for value in values:
        if span <= 0:
            height = 70
        else:
            height = 10 + int(((value - minimum) / span) * 90)
        bars.append(f'<span class="sparkbar" title="{html.escape(label)}: {value:.4f}" style="height:{height}%"></span>')
    return (
        f'<div class="sparkline">'
        f'<div class="sparkline-label">{html.escape(label)} <span class="sparkline-range">{html.escape(low)} {minimum:.4f} / {html.escape(high)} {maximum:.4f}</span></div>'
        f'<div class="sparkline-bars">{"".join(bars)}</div>'
        f'</div>'
    )


def render_html(model: dict[str, Any], output_path: Path | None = None) -> Path:
    output = output_path or model["output_path"]
    output.parent.mkdir(parents=True, exist_ok=True)
    turns = model["turns"]
    if not turns:
        html_text = """<!doctype html>
<html lang="ja">
<head>
<meta charset="utf-8">
<title>Loop Status</title>
<style>
body { font-family: system-ui, sans-serif; margin: 0; padding: 2rem; background: #f6f5ef; color: #1e1e1e; }
.empty { padding: 1.5rem; background: #fff; border: 1px solid #ddd; border-radius: 16px; }
</style>
</head>
<body><main class="empty"><h1>未稼働</h1><p>completed loop turn がまだありません。</p></main></body>
</html>
"""
        output.write_text(html_text, encoding="utf-8")
        return output

    current_health = model["current_health"]
    trend_available = model["trend_available"]
    trend_points = model["trend_points"]

    status_class_map = {"pass": "status-pass", "amber": "status-amber", "red": "status-red", "gray": "status-gray"}
    chain_cards: list[str] = []
    for index, turn in enumerate(turns):
        status_kind = classify_status(turn.final_status, model["thresholds"])
        next_turn = turns[index + 1] if index + 1 < len(turns) else None
        chain: list[str] = [f'<span class="chain-step">handoff: {"ready" if turn.handoff_ready else "none"}</span>']
        if turn.handoff_unconsumed:
            chain.append(f'<span class="chain-step handoff-unconsumed">unconsumed after {model["scheduler_policy"].get("poll_interval_seconds", 5) * int(model["thresholds"]["unconsumed_handoff_poll_cycles"])}s</span>')
        elif turn.scheduler_action:
            chain.append(f'<span class="chain-step handoff-consumed">daemon: {html.escape(turn.scheduler_action)}</span>')
        else:
            chain.append('<span class="chain-step handoff-idle">daemon: none</span>')
        if next_turn is not None and turn.completed_at and next_turn.started_at and next_turn.started_at >= turn.completed_at:
            chain.append(f'<span class="chain-step">next turn: <a href="{html.escape(turn.rel_path)}">{html.escape(turn.turn_id)}</a> → {html.escape(next_turn.turn_id)}</span>')
        brief_html = ""
        if turn.brief_goal:
            brief_html = f'<div class="brief brief-visible">Brief goal: {html.escape(turn.brief_goal)}</div>'
        card = f"""
        <article class="turn {status_class_map[status_kind]}">
          <header>
            <h3>{html.escape(turn.turn_id)}</h3>
            <span class="status-pill">{html.escape(turn.final_status or 'IN_PROGRESS')}</span>
          </header>
          <div class="meta">
            <span>route: {html.escape(turn.routing_mode or 'unknown')}</span>
            <span>started: {html.escape(turn.started_at.isoformat() if turn.started_at else 'unknown')}</span>
            <span>completed: {html.escape(turn.completed_at.isoformat() if turn.completed_at else 'open')}</span>
            <span>validation: {html.escape('ok' if turn.validation_ok else 'failed' if turn.validation_ok is not None else 'n/a')}</span>
            <span>unverified claims: {turn.unverified_claim_count}</span>
          </div>
          <div class="chain">{''.join(chain)}</div>
          <div class="paths">
            <a href="{html.escape(turn.rel_path)}">turn dir</a>
            {f'<a href="{html.escape(os.path.relpath(turn.path / "next-turn.json", model["output_path"].parent))}">next-turn.json</a>' if (turn.path / "next-turn.json").is_file() else ''}
          </div>
          {brief_html}
        </article>
        """
        chain_cards.append(card)

    unresolved_cards: list[str] = []
    for turn in model["unresolved"]:
        unresolved_cards.append(
            f"""
            <li class="unresolved-item">
              <span class="turn-id">{html.escape(turn.turn_id)}</span>
              <span class="status">{html.escape(turn.final_status)}</span>
              <span class="age">{html.escape(format_relative_time(turn.completed_at))}</span>
              <span class="unverified">{turn.unverified_claim_count} unverified claims</span>
              <a href="{html.escape(turn.rel_path)}">turn dir</a>
            </li>
            """
        )

    if trend_available:
        debt_series = [point["learning_debt_score"] for point in trend_points]
        validation_series = [point["validation_success_rate"] for point in trend_points]
        trend_html = (
            f'<div class="trend-metric"><h4>Learning debt</h4>{sparkline(debt_series, label="learning debt score", low="low", high="high")}</div>'
            f'<div class="trend-metric"><h4>Validation success</h4>{sparkline(validation_series, label="validation success rate", low="low", high="high")}</div>'
        )
    else:
        trend_html = '<p class="data-insufficient">データ不足</p>'

    latest_pass = model["latest_pass"]
    cadence_text = format_relative_time(latest_pass) if latest_pass is not None else "未稼働"

    html_text = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Loop Status</title>
<style>
:root {{
  color-scheme: light;
  --bg: #f4f1e8;
  --panel: #fffdf7;
  --ink: #23201d;
  --muted: #6b6259;
  --green: #1f7a4d;
  --amber: #a77700;
  --red: #b23a2f;
  --gray: #778089;
  --line: #d6cec1;
  --accent: #0e4b78;
}}
body {{
  margin: 0;
  background: linear-gradient(180deg, #fbfaf6 0%, var(--bg) 100%);
  color: var(--ink);
  font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
main {{ max-width: 1180px; margin: 0 auto; padding: 24px; }}
h1 {{ margin: 0 0 8px; font-size: 2rem; }}
h2 {{ margin: 0 0 12px; font-size: 1.25rem; }}
.summary {{ color: var(--muted); margin-bottom: 24px; }}
.section {{ margin-top: 24px; padding: 20px; background: rgba(255,255,255,0.86); border: 1px solid var(--line); border-radius: 20px; box-shadow: 0 10px 30px rgba(16, 12, 8, 0.05); }}
.chain-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 14px; }}
.turn {{ border: 1px solid var(--line); border-radius: 18px; padding: 14px; background: var(--panel); }}
.turn header {{ display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 10px; }}
.turn h3 {{ margin: 0; font-size: 1rem; }}
.status-pill {{ display: inline-flex; align-items: center; padding: 4px 10px; border-radius: 999px; font-size: .75rem; letter-spacing: .04em; text-transform: uppercase; background: #f0ede7; }}
.status-pass {{ border-color: rgba(31,122,77,.35); box-shadow: inset 0 0 0 1px rgba(31,122,77,.12); }}
.status-pass .status-pill {{ color: var(--green); background: rgba(31,122,77,.1); }}
.status-amber {{ border-color: rgba(167,119,0,.35); box-shadow: inset 0 0 0 1px rgba(167,119,0,.12); }}
.status-amber .status-pill {{ color: var(--amber); background: rgba(167,119,0,.1); }}
.status-red {{ border-color: rgba(178,58,47,.35); box-shadow: inset 0 0 0 1px rgba(178,58,47,.12); }}
.status-red .status-pill {{ color: var(--red); background: rgba(178,58,47,.1); }}
.status-gray {{ border-color: rgba(119,128,137,.35); box-shadow: inset 0 0 0 1px rgba(119,128,137,.12); }}
.status-gray .status-pill {{ color: var(--gray); background: rgba(119,128,137,.1); }}
.meta, .paths, .chain {{ display: flex; flex-wrap: wrap; gap: 8px 10px; font-size: .88rem; color: var(--muted); }}
.chain {{ margin: 10px 0; }}
.chain-step {{ display: inline-flex; align-items: center; padding: 4px 8px; border-radius: 999px; background: #f4efe3; }}
.handoff-unconsumed {{ background: rgba(167,119,0,.12); color: var(--amber); font-weight: 600; }}
.brief {{ margin-top: 10px; padding: 10px 12px; border-radius: 12px; background: rgba(14,75,120,.08); color: var(--accent); }}
.sparkline {{ margin-top: 12px; }}
.sparkline-label {{ font-weight: 600; margin-bottom: 8px; }}
.sparkline-note {{ color: var(--muted); margin-left: 8px; }}
.sparkline-bars {{ display: flex; align-items: end; gap: 6px; min-height: 96px; padding: 6px 0; }}
.sparkbar {{ width: 16px; border-radius: 8px 8px 0 0; background: linear-gradient(180deg, #6aa7ff 0%, #2a5eb8 100%); display: inline-block; }}
.trend-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 14px; }}
.trend-metric {{ border: 1px solid var(--line); border-radius: 18px; padding: 14px; background: var(--panel); }}
.trend-metric h4 {{ margin: 0 0 10px; }}
.unresolved-list {{ list-style: none; padding: 0; margin: 0; display: grid; gap: 10px; }}
.unresolved-item {{ display: flex; flex-wrap: wrap; gap: 10px 12px; align-items: center; padding: 12px 14px; background: var(--panel); border: 1px solid var(--line); border-radius: 14px; }}
.unresolved-item .turn-id {{ font-weight: 700; }}
.data-insufficient {{ color: var(--muted); }}
.section-note {{ color: var(--muted); margin-top: 8px; }}
a {{ color: var(--accent); text-decoration: none; }}
a:hover {{ text-decoration: underline; }}
@media (max-width: 720px) {{
  main {{ padding: 16px; }}
  .sparkbar {{ width: 12px; }}
}}
</style>
</head>
<body>
<main>
  <h1>Loop Status</h1>
  <div class="summary">Latest PASS cadence: {html.escape(cadence_text)} | Learning health: {html.escape(str(current_health.get('health')))} | Debt score: {html.escape(str(current_health.get('metrics', {}).get('learning_debt_score', 0)))}</div>

  <section class="section">
    <h2>Loop Closure Chain</h2>
    <div class="chain-grid">
      {''.join(chain_cards)}
    </div>
    <div class="section-note">Yellow handoffs indicate a ready handoff older than the configured poll threshold with no scheduler action.</div>
  </section>

  <section class="section">
    <h2>Trend</h2>
    <div class="trend-grid">
      {trend_html}
    </div>
    <div class="section-note">Trend charts are deterministic and are hidden until the learning-policy minimum has been met.</div>
  </section>

  <section class="section">
    <h2>Need Attention</h2>
    <ul class="unresolved-list">
      {''.join(unresolved_cards) if unresolved_cards else '<li class="data-insufficient">No unresolved terminals.</li>'}
    </ul>
  </section>
</main>
</body>
</html>
"""
    output.write_text(html_text, encoding="utf-8")
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path)
    parser.add_argument("--text", action="store_true", help="Render a one-screen text summary.")
    parser.add_argument("--html", nargs="?", const=".agent-loop/runtime/status.html", metavar="OUTPUT", help="Render the HTML status page.")
    parser.add_argument("--include-brief", action="store_true", help="Include brief goal text in the HTML output.")
    parser.add_argument("--gate", action="store_true", help="Render the mutation-gate status view.")
    args = parser.parse_args()
    root = find_root(args.repo)
    html_output = root / Path(args.html) if args.html else root / Path(("." + "agent-loop") + "/runtime/status.html")
    if args.gate:
        sys.stdout.write(render_gate_text(collect_gate_model(root)))
        return 0
    model = collect_model(root, html_output, include_brief=args.include_brief)
    render_text_requested = args.text or not args.html
    if render_text_requested:
        sys.stdout.write(render_text(model))
    if args.html is not None:
        render_html(model, html_output)
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
