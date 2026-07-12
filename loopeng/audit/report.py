from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .._paths import agent_root
from ..learning import save_learning_entries
from .checks import collect_context, run_checks


def _summarize_findings(findings):
    blocked = [finding for finding in findings if finding.category == "block"]
    alerts = [finding for finding in findings if finding.category != "block"]
    return blocked, alerts


def _format_findings(findings) -> list[str]:
    lines = []
    for finding in findings:
        evidence = "; ".join(finding.evidence) if finding.evidence else "none"
        lines.append(f"- {finding.check_id} [{finding.severity}]: {finding.message} ({evidence})")
    return lines or ["- none"]


def run_audit_report(repo: Path, run_id: str) -> Path:
    repo = repo.resolve()
    context = collect_context(repo, run_id)
    findings = run_checks(context)
    blocked, alerts = _summarize_findings(findings)
    report_dir = repo / agent_root("state", "reports")
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{run_id}.md"
    learning_paths = save_learning_entries(repo, run_id)
    learning_backlog = len(list(context.learning_root.glob("*.json"))) if context.learning_root.is_dir() else 0
    starts = [event for event in context.events if event.get("kind") == "run-start"]
    ends = [event for event in context.events if event.get("kind") == "run-end"]
    agent = str(starts[-1].get("agent") or "unknown") if starts else "unknown"
    duration = "unknown"
    if starts and ends:
        try:
            delta = datetime.fromisoformat(str(ends[-1]["timestamp"])) - datetime.fromisoformat(str(starts[-1]["timestamp"]))
            duration = f"{delta.total_seconds():.3f}s"
        except (KeyError, TypeError, ValueError):
            pass
    okf_events = [event for event in context.events if event.get("kind") == "okf-apply"]
    applied = [event for event in okf_events if event.get("ok")]
    rejected = [event for event in okf_events if not event.get("ok")]
    handoff_path = repo / agent_root("state", "handoff.json")
    prior_handoff = json.loads(handoff_path.read_text(encoding="utf-8")) if handoff_path.is_file() else {}
    protected = [finding for finding in findings if finding.check_id == "protected_path_mutation"]
    declared = [finding for finding in protected if finding.severity != "critical"]
    undeclared = [finding for finding in protected if finding.severity == "critical"]
    alert_summary = f"{len(alerts)} alerts; {len(undeclared)} undeclared critical"
    touched = [str(path) for event in okf_events for path in event.get("touched", []) if isinstance(event.get("touched"), list)]
    handoff = {
        "source_turn_id": run_id,
        "goal": str(starts[-1].get("goal") or "") if starts else "",
        "summary": f"Run {run_id} completed: {alert_summary}.",
        "alerts_summary": alert_summary,
        "generated_at": datetime.now().astimezone().isoformat(),
    }
    declared_paths = {finding.evidence[0] for finding in declared if finding.evidence}
    undeclared_paths = {finding.evidence[0] for finding in undeclared if finding.evidence}

    report_lines = [
        f"# Run Report {run_id}", "", "## What ran", f"- run-id: {run_id}",
        f"- agent-type: {agent}", f"- duration: {duration}",
        f"- handoff source: {prior_handoff.get('source_turn_id', 'none')}",
        f"- journal: {context.journal_path.relative_to(repo) if context.journal_path.exists() else 'missing'}",
        f"- changed-paths: {len(context.changed_paths)}", "", "## Mutations", "### Declared",
    ]
    report_lines.extend([f"- changed: {path}" for path in sorted(declared_paths)] or ["- none"])
    report_lines.extend(_format_findings(declared))
    report_lines.extend(["", "### Undeclared"])
    report_lines.extend(f"- changed: {path}" for path in sorted(undeclared_paths))
    report_lines.extend(_format_findings(undeclared or [finding for finding in findings if finding.check_id in {"journal_coverage", "out_of_repo_write"}]))
    report_lines.extend(["", "## Memory", f"- applied OKF reports: {len(applied)}", f"- rejected OKF reports: {len(rejected)}", f"- touched: {', '.join(touched) or 'none'}", "", "## Learning", f"- entries: {len(learning_paths)}", f"- backlog: {learning_backlog}", "", "## Alerts"])
    report_lines.extend(_format_findings(alerts))
    report_lines.extend(["", "## Blocked"])
    report_lines.extend(_format_findings(blocked))
    report_lines.extend([
        "", "## Next",
        f"- source_turn_id: {handoff['source_turn_id']}",
        f"- goal: {handoff['goal'] or 'none'}",
        f"- summary: {handoff['summary']}",
        f"- alerts_summary: {handoff['alerts_summary']}",
        f"- generated_at: {handoff['generated_at']}", "",
    ])
    if any(finding.severity == "critical" for finding in findings):
        report_lines.insert(0, "CRITICAL ALERTS PRESENT: human review required.")
        report_lines.insert(1, "")
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    handoff_path.parent.mkdir(parents=True, exist_ok=True)
    handoff_path.write_text(json.dumps(handoff, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report_path
