from __future__ import annotations

from pathlib import Path

from .._paths import agent_root
from ..learning import save_learning_entries
from .checks import collect_context, run_checks


def _summarize_findings(findings):
    blocked = [finding for finding in findings if finding.category == "block"]
    alerts = [finding for finding in findings if finding.category != "block"]
    return blocked, alerts


def _format_findings(findings) -> list[str]:
    lines: list[str] = []
    for finding in findings:
        evidence = "; ".join(finding.evidence) if finding.evidence else "none"
        lines.append(f"- {finding.check_id} [{finding.severity}]: {finding.message} ({evidence})")
    if not lines:
        lines.append("- none")
    return lines


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

    report_lines = [
        f"# Run Report {run_id}",
        "",
        "## What ran",
        f"- run-id: {run_id}",
        "- agent-type: unknown",
        "- duration: unknown",
        "- handoff source: none",
        f"- journal: {context.journal_path.relative_to(repo) if context.journal_path.exists() else 'missing'}",
        f"- changed-paths: {len(context.changed_paths)}",
        "",
        "## Mutations",
    ]
    report_lines.extend(
        _format_findings(
            [
                finding
                for finding in findings
                if finding.check_id in {"protected_path_mutation", "journal_coverage", "out_of_repo_write"}
            ]
        )
    )
    report_lines.extend(
        [
            "",
            "## Memory",
            "- applied OKF report: none",
            "- rejected OKF report: none",
            "",
            "## Learning",
            f"- entries: {len(learning_paths)}",
            f"- backlog: {learning_backlog}",
            "",
            "## Alerts",
        ]
    )
    report_lines.extend(_format_findings(alerts))
    report_lines.extend(
        [
            "",
            "## Blocked",
        ]
    )
    if blocked:
        report_lines.extend(_format_findings(blocked))
    else:
        report_lines.append("- none")
    report_lines.extend(
        [
            "",
            "## Next",
            "- handoff: none",
            "",
        ]
    )
    if any(finding.severity == "critical" for finding in findings):
        report_lines.insert(0, "CRITICAL ALERTS PRESENT: human review required.")
        report_lines.insert(1, "")
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    return report_path
