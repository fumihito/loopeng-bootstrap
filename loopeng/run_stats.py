from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ._paths import agent_root
from .journal import GOVERNANCE_EVENT_KINDS
from .memory_stats import STATS_WINDOWS


def _time(value: Any) -> datetime | None:
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def collect_run_stats(repo: Path, windows: tuple[str, ...] = ("7d", "28d"), now: str | None = None) -> dict[str, Any]:
    as_of = _time(now) or datetime.now(timezone.utc)
    runs: list[dict[str, Any]] = []
    root = repo / agent_root("state", "journal")
    for path in root.glob("*.jsonl") if root.is_dir() else ():
        events = []
        for line in path.read_text(encoding="utf-8").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict):
                events.append(event)
        starts = [event for event in events if event.get("kind") == "run-start"]
        if not starts:
            continue
        start = starts[0]
        outcomes = [event for event in events if event.get("kind") == "outcome"]
        human = [event for event in outcomes if event.get("source") == "human"]
        selected = (human or outcomes)[-1] if (human or outcomes) else None
        runs.append({"run_id": path.stem, "started": _time(start.get("timestamp")), "outcome": str(selected.get("status")) if selected else "none", "discipline": str(start.get("discipline") or "unspecified"), "total": len(events), "governance": sum(1 for event in events if event.get("kind") in GOVERNANCE_EVENT_KINDS)})
    output = {"windows": {}}
    for label in windows:
        days = int(label[:-1])
        cutoff = as_of - timedelta(days=days)
        chosen = [run for run in runs if run["started"] and cutoff <= run["started"] <= as_of]
        total = sum(run["total"] for run in chosen)
        governance = sum(run["governance"] for run in chosen)
        by_discipline: dict[str, Counter[str]] = {}
        for run in chosen:
            by_discipline.setdefault(run["discipline"], Counter())[run["outcome"]] += 1
        output["windows"][label] = {"runs": len(chosen), "outcomes": dict(Counter(run["outcome"] for run in chosen)), "governance_events": governance, "total_events": total, "overhead_ratio": governance / total if total else 0.0, "discipline": {key: dict(value) for key, value in sorted(by_discipline.items())}}
    return output


def render_run_stats(value: dict[str, Any]) -> str:
    lines = ["window  runs  outcomes  governance/total  overhead"]
    for window, item in value["windows"].items():
        lines.append(f"{window:<7} {item['runs']:>4}  {item['outcomes']}  {item['governance_events']}/{item['total_events']}  {item['overhead_ratio']:.1%}")
        if item["discipline"]:
            lines.append(f"        discipline: {item['discipline']}")
    return "\n".join(lines) + "\n"
