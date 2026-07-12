from __future__ import annotations

import json
from pathlib import Path

from ._paths import agent_root


def render_status(repo: Path) -> str:
    reports = sorted((repo / agent_root("state", "reports")).glob("*.md"), key=lambda p: p.stat().st_mtime, reverse=True)
    report = reports[0] if reports else None
    run_id = report.stem if report else "none"
    text = report.read_text(encoding="utf-8") if report else ""
    lines = text.splitlines()
    try:
        start = lines.index("## Alerts") + 1
        end = lines.index("## Blocked", start)
        alert_lines = [line for line in lines[start:end] if line.startswith("- ") and line != "- none"]
    except ValueError:
        alert_lines = []
    alerts = len(alert_lines)
    critical = any("undeclared" in line.lower() and "critical" in line.lower() for line in lines)
    learning = repo / agent_root("state", "learning")
    backlog = len(list(learning.glob("*.json"))) if learning.is_dir() else 0
    return f"run-id: {run_id}\nalerts: {alerts}\nundeclared critical: {'yes' if critical else 'no'}\nlearning backlog: {backlog}"
