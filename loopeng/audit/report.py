from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .._paths import agent_root
from ..learning import save_learning_entries
from .checks import collect_context, run_checks
from .policy import DETAIL_MESSAGE_MAX, DETAIL_PATHS_MAX
from ..journal import EVENT_BLOCKED, EVENT_OKF_APPLY, EVENT_RUN_END, EVENT_RUN_START, EVENT_SKILL_USED, GOVERNANCE_EVENT_KINDS, sanitize_event
from ..journal import EVENT_OUTCOME


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


_PATH_FINDINGS = {
    "journal_coverage",
    "protected_path_mutation",
    "out_of_repo_write",
    "skill_structure_violation",
    "unreviewed_claim_persisted",
}


def _finding_paths(finding) -> list[str]:
    paths = list(getattr(finding, "paths", ()) or ())
    if not paths and finding.check_id in _PATH_FINDINGS and finding.evidence:
        paths = [str(finding.evidence[0])]
    return paths


def _sidecar_alert(finding) -> dict:
    message = sanitize_event({"message": str(finding.message)}).get("message", "")
    raw_paths = [str(path) for path in _finding_paths(finding)]
    sanitized_paths = [sanitize_event({"path": path}).get("path", "") for path in raw_paths]
    alert = {
        "check_id": finding.check_id,
        "severity": finding.severity,
        "declared": not (finding.check_id == "protected_path_mutation" and finding.severity == "critical"),
        "message": str(message)[:DETAIL_MESSAGE_MAX],
    }
    if sanitized_paths:
        alert["paths"] = sanitized_paths[:DETAIL_PATHS_MAX]
        alert["paths_total"] = len(sanitized_paths)
    return alert


def run_audit_report(repo: Path, run_id: str) -> Path:
    repo = repo.resolve()
    context = collect_context(repo, run_id)
    findings = run_checks(context)
    blocked, alerts = _summarize_findings(findings)
    report_dir = repo / agent_root("state", "reports")
    report_dir.mkdir(parents=True, exist_ok=True)
    report_path = report_dir / f"{run_id}.md"
    learning_paths = save_learning_entries(repo, run_id)
    learning_files = list(context.learning_root.glob("*.json")) if context.learning_root.is_dir() else []
    learning_backlog = 0
    drafted_unapplied = 0
    for learning_file in learning_files:
        try:
            value = json.loads(learning_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            value = {}
        if isinstance(value, dict) and value.get("drafted") and not value.get("applied"):
            drafted_unapplied += 1
        elif learning_file.name not in {"learning-health.json", "learning-index.json"}:
            learning_backlog += 1
    starts = [event for event in context.events if event.get("kind") == EVENT_RUN_START]
    ends = [event for event in context.events if event.get("kind") == EVENT_RUN_END]
    agent = str(starts[-1].get("agent") or "unknown") if starts else "unknown"
    duration = "unknown"
    if starts and ends:
        try:
            delta = datetime.fromisoformat(str(ends[-1]["timestamp"])) - datetime.fromisoformat(str(starts[-1]["timestamp"]))
            duration = f"{delta.total_seconds():.3f}s"
        except (KeyError, TypeError, ValueError):
            pass
    okf_events = [event for event in context.events if event.get("kind") == EVENT_OKF_APPLY]
    applied = [event for event in okf_events if event.get("ok")]
    provisional_applied = [event for event in applied if event.get("tier") == "provisional"]
    curate_path = repo / agent_root("state", "last-curate.json")
    curate = {}
    if curate_path.is_file():
        try:
            curate = json.loads(curate_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            curate = {}
    rejected = [event for event in okf_events if not event.get("ok")]
    skill_events = [event for event in context.events if event.get("kind") == EVENT_SKILL_USED]
    blocked_events = [event for event in context.events if event.get("kind") == EVENT_BLOCKED]
    outcome_events = [event for event in context.events if event.get("kind") == EVENT_OUTCOME]
    human_outcomes = [event for event in outcome_events if event.get("source") == "human"]
    selected_outcome = (human_outcomes or outcome_events)[-1] if (human_outcomes or outcome_events) else None
    outcome_status = str(selected_outcome.get("status")) if selected_outcome else "none"
    skill_counts: dict[str, int] = {}
    skill_sources: dict[str, dict[str, int]] = {}
    for event in skill_events:
        skill = str(event.get("skill") or "unknown")
        source = str(event.get("source") or "unknown")
        skill_counts[skill] = skill_counts.get(skill, 0) + 1
        skill_sources.setdefault(skill, {})[source] = skill_sources.setdefault(skill, {}).get(source, 0) + 1
    blocked_counts: dict[str, int] = {}
    for event in blocked_events:
        check_id = str(event.get("check_id") or "unknown")
        blocked_counts[check_id] = blocked_counts.get(check_id, 0) + 1
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
    captured = sum(1 for event in context.events if event.get("kind") == "learning-candidate")
    if captured:
        unpromoted = sum(1 for path in context.learning_root.glob("*.json") if path.is_file()) if context.learning_root.is_dir() else 0
        handoff["notes"] = f"learning: +{captured} captured, {unpromoted} unpromoted"
    declared_paths = {finding.evidence[0] for finding in declared if finding.evidence}
    undeclared_paths = {finding.evidence[0] for finding in undeclared if finding.evidence}

    started_at = starts[-1].get("timestamp") if starts else None
    ended_at = ends[-1].get("timestamp") if ends else None
    sidecar = {
        "run_id": run_id,
        "agent": agent,
        "goal": str(starts[-1].get("goal") or "") if starts else "",
        "started_at": started_at,
        "ended_at": ended_at,
        "alerts": [
            _sidecar_alert(finding)
            for finding in findings
        ],
        "undeclared_critical": bool(undeclared),
        "memory": {"applied": len(applied), "provisional": len(provisional_applied), "pending": len(curate.get("pending", [])), "rejected": len(rejected)},
        "behavior": {"skills": skill_counts, "blocked": blocked_counts},
        "outcome": outcome_status,
        "overhead": {"governance_events": sum(1 for event in context.events if event.get("kind") in GOVERNANCE_EVENT_KINDS), "total_events": len(context.events)},
        "handoff_written": True,
        "schema": 2,
    }

    report_lines = [
        f"# Run Report {run_id}", "", "## What ran", f"- run-id: {run_id}",
        f"- agent-type: {agent}", f"- duration: {duration}",
        f"- handoff source: {prior_handoff.get('source_turn_id', 'none')}",
        f"- journal: {context.journal_path.relative_to(repo) if context.journal_path.exists() else 'missing'}",
        f"- changed-paths: {len(context.changed_paths)}", "", "## Outcome", f"- status: {outcome_status}",
    ]
    if selected_outcome and isinstance(selected_outcome.get("results"), list):
        for result in selected_outcome["results"]:
            if isinstance(result, dict):
                report_lines.append(f"- {result.get('kind', 'result')}: {result.get('status', 'unknown')}" + (f" — {result.get('run')}" if result.get("run") else ""))
    report_lines.extend(["", "## Mutations", "### Declared"])
    report_lines.extend([f"- changed: {path}" for path in sorted(declared_paths)] or ["- none"])
    report_lines.extend(_format_findings(declared))
    report_lines.extend(["", "### Undeclared"])
    report_lines.extend(f"- changed: {path}" for path in sorted(undeclared_paths))
    report_lines.extend(_format_findings(undeclared or [finding for finding in findings if finding.check_id in {"journal_coverage", "out_of_repo_write"}]))
    report_lines.extend(["", "## Memory", f"- applied OKF reports: {len(applied)}", f"- provisional applied: {len(provisional_applied)}", f"- pending approval: {len(curate.get('pending', []))}", f"- rejected OKF reports: {len(rejected)}", f"- touched: {', '.join(touched) or 'none'}", "", "## Learning", f"- entries: {len(learning_paths)}", f"- backlog: {learning_backlog}", f"- drafted-unapplied: {drafted_unapplied}", "", "## Behavior"])
    if skill_counts:
        for skill in sorted(skill_counts):
            sources = ", ".join(f"{source}={count}" for source, count in sorted(skill_sources[skill].items()))
            report_lines.append(f"- skills used: {skill} ({skill_counts[skill]}; {sources})")
    else:
        report_lines.append("- skills used: none")
    if blocked_events:
        for event in blocked_events:
            report_lines.append(f"- blocked operations: {event.get('check_id', 'unknown')} / {event.get('summary', 'unknown')} (1)")
    else:
        report_lines.append("- blocked operations: none")
    report_lines.extend(["", "## Alerts"])
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
    if handoff.get("notes"):
        report_lines.insert(-1, f"- notes: {handoff['notes']}")
    if any(finding.severity == "critical" for finding in findings):
        report_lines.insert(0, "CRITICAL ALERTS PRESENT: human review required.")
        report_lines.insert(1, "")
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    (report_dir / f"{run_id}.json").write_text(
        json.dumps(sidecar, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    handoff_path.parent.mkdir(parents=True, exist_ok=True)
    handoff_path.write_text(json.dumps(handoff, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return report_path
