"""Deterministic loop-cycle diagrams for ``loopeng review dag``."""

from __future__ import annotations

import html
import json
from collections import Counter
from pathlib import Path
from typing import Any

from ._paths import agent_root
from .audit.policy import DETAIL_FINDINGS_MAX, DETAIL_MESSAGE_MAX, DETAIL_PATHS_MAX
from .journal import journal_path
from .review import DEFAULT_RUNS, _reports

STAGES = ("intake", "retrieve", "act", "record", "memory", "audit", "handoff", "hooks", "learning")
STAGE_MAP = {
    "intent_overdeclaration": "intake",
    "retrieval_volume": "retrieve",
    "protected_path_mutation": "act",
    "out_of_repo_write": "act",
    "destructive_command": "act",
    "high_risk_command": "act",
    "budget_exceeded": "act",
    "skill_structure_violation": "act",
    "journal_coverage": "record",
    "secret_persistence": "record",
    "okf_invalid_apply": "memory",
    "single_author_memory_change": "memory",
    "unreviewed_claim_persisted": "memory",
    "provisional_stagnation": "memory",
    "memory_commit_divergence": "memory",
    "hook_failure": "hooks",
    "learning_backlog": "learning",
}

CRIT = "✖"
WARN = "⚠"
OK = "✔"
MAX_EVENTS = 60
DETAIL_GUIDE = "details: review dag --stage <intake|retrieve|act|record|memory|audit|handoff|hooks|learning>"

_COLORS = {"crit": "#7f1d1d", "warn": "#78350f", "ok": "#1f2937"}


def _alert_bucket(alert: dict[str, Any]) -> tuple[str, str]:
    """Return (check_id, bucket) using the review DAG alert semantics."""
    check_id = str(alert.get("check_id") or "unknown")
    severity = str(alert.get("severity") or "info")
    declared = bool(alert.get("declared", False))
    if severity == "critical":
        if check_id == "protected_path_mutation" and declared:
            return check_id, "warn"
        return check_id, "critical"
    if severity == "warn":
        return check_id, "warn"
    return check_id, "none"


def _handoff_unconsumed(repo: Path) -> bool:
    path = repo / agent_root("state", "handoff.json")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return False
    return isinstance(value, dict) and bool(value) and not value.get("consumed_at")


def _counts(repo: Path, runs: list[dict[str, Any]]) -> tuple[Counter[str], Counter[str], Counter[str], int]:
    critical: Counter[str] = Counter()
    warns: Counter[str] = Counter()
    unmapped: Counter[str] = Counter()
    for run in runs:
        for alert in run.get("alerts", []) if isinstance(run.get("alerts"), list) else []:
            if not isinstance(alert, dict):
                continue
            check_id, bucket = _alert_bucket(alert)
            stage = STAGE_MAP.get(check_id)
            if stage is None:
                unmapped[check_id] += 1
            elif bucket == "critical":
                critical[stage] += 1
            elif bucket == "warn":
                warns[stage] += 1
    if _handoff_unconsumed(repo):
        warns["handoff"] += 1
    return critical, warns, unmapped, sum(critical.values()) + sum(warns.values()) + sum(unmapped.values())


def _badge(
    stage: str,
    critical: Counter[str],
    warns: Counter[str],
    *,
    handoff_unconsumed: bool = False,
) -> str:
    parts: list[str] = []
    if critical[stage]:
        parts.append(f"{CRIT} {critical[stage]}")
    handoff_count = 1 if stage == "handoff" and handoff_unconsumed else 0
    alert_warns = warns[stage] - handoff_count
    if alert_warns:
        parts.append(f"{WARN} {alert_warns}")
    if handoff_unconsumed:
        parts.append(f"{WARN} unconsumed")
    return " / ".join(parts) if parts else OK


def _class(stage: str, critical: Counter[str], warns: Counter[str]) -> str:
    return "crit" if critical[stage] else "warn" if warns[stage] else "ok"


def _run_label(runs: list[dict[str, Any]]) -> str:
    ids = [str(run.get("run_id")) for run in runs]
    return ", ".join(ids) if ids else "none"


def _mermaid(repo: Path, runs: list[dict[str, Any]]) -> str:
    critical, warns, unmapped, total = _counts(repo, runs)
    handoff_unconsumed = _handoff_unconsumed(repo)
    label = _run_label(runs)
    lines = ["flowchart LR", f'  subgraph cycle["Loop cycle (runs: {label}, findings: {total})"]']
    lines += [f'    {stage}["{stage}<br/>{_badge(stage, critical, warns, handoff_unconsumed=handoff_unconsumed and stage == "handoff")}"]' for stage in STAGES[:7]]
    lines += [
        "    intake --> retrieve", "    retrieve --> act", "    act --> record", "    record --> memory",
        "    memory --> audit", "    audit --> handoff", "    handoff --> intake", "  end",
        f'  audit -.-> learning["learning<br/>{_badge("learning", critical, warns)}"]',
        f'  hooks["hooks<br/>{_badge("hooks", critical, warns) if (repo / agent_root("hooks")).exists() else "(not installed)"}"] -.-> act',
        "  classDef crit fill:#7f1d1d,color:#fff;", "  classDef warn fill:#78350f,color:#fff;", "  classDef ok fill:#1f2937,color:#9ca3af;",
    ]
    classes = {name: [] for name in ("crit", "warn", "ok")}
    for stage in STAGES:
        classes[_class(stage, critical, warns)].append(stage)
    for name in ("crit", "warn", "ok"):
        if classes[name]:
            lines.append(f"  class {','.join(classes[name])} {name};")
    if unmapped:
        detail = ", ".join(f"{key} {value}" for key, value in sorted(unmapped.items()))
        lines.append(f'  unmapped["unmapped<br/>{WARN} {sum(unmapped.values())}: {detail}"]')
        lines.append("  class unmapped warn;")
    return "\n".join(lines) + "\n"


def _svg(repo: Path, runs: list[dict[str, Any]]) -> str:
    critical, warns, unmapped, total = _counts(repo, runs)
    label = html.escape(_run_label(runs))
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1200" height="620" viewBox="0 0 1200 620">',
        '<style>text{font-family:monospace;fill:#f3f4f6;font-size:16px}.node{stroke:#9ca3af;stroke-width:1}.legend{font-size:14px}</style>',
        '<defs><marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto"><polygon points="0 0, 10 3.5, 0 7" fill="#9ca3af"/></marker></defs>',
        f'<rect width="1200" height="620" fill="#111827"/><text x="30" y="30">Loop cycle (runs: {label}, findings: {total})</text>',
    ]
    positions = {stage: (40 + (index % 7) * 160, 90 if index < 7 else 300) for index, stage in enumerate(STAGES)}
    for left, right in zip(STAGES[:7], STAGES[1:7]):
        x1, y1 = positions[left]; x2, y2 = positions[right]
        parts.append(f'<path d="M{x1 + 130},{y1 + 35} L{x2},{y2 + 35}" stroke="#9ca3af" fill="none" marker-end="url(#arrowhead)"/>')
    handoff_x, handoff_y = positions["handoff"]
    intake_x, intake_y = positions["intake"]
    parts.append(f'<path d="M{handoff_x + 65},{handoff_y} C{handoff_x + 65},250 {handoff_x + 65},55 {intake_x + 65},55 L{intake_x + 65},{intake_y}" stroke="#9ca3af" fill="none" marker-end="url(#arrowhead)"/>')
    learning_x, learning_y = positions["learning"]
    audit_x, audit_y = positions["audit"]
    hooks_x, hooks_y = positions["hooks"]
    act_x, act_y = positions["act"]
    parts.append(f'<path d="M{audit_x + 65},{audit_y + 70} C{audit_x + 65},{audit_y + 120} {learning_x + 65},{learning_y - 20} {learning_x + 65},{learning_y}" stroke="#9ca3af" fill="none" stroke-dasharray="6 4" marker-end="url(#arrowhead)"/>')
    parts.append(f'<path d="M{hooks_x + 130},{hooks_y + 35} C{hooks_x + 180},{hooks_y + 35} {act_x - 30},{act_y + 35} {act_x},{act_y + 35}" stroke="#9ca3af" fill="none" stroke-dasharray="6 4" marker-end="url(#arrowhead)"/>')
    for stage in STAGES:
        x, y = positions[stage]
        color = _COLORS[_class(stage, critical, warns)]
        badge = _badge(stage, critical, warns, handoff_unconsumed=_handoff_unconsumed(repo) and stage == "handoff")
        parts += [f'<rect class="node" x="{x}" y="{y}" width="130" height="70" rx="8" fill="{color}"/>', f'<text x="{x + 10}" y="{y + 27}">{stage}</text>', f'<text x="{x + 10}" y="{y + 52}">{html.escape(badge)}</text>']
    parts += ['<text class="legend" x="40" y="400">Legend: ✖ critical (undeclared)  /  ⚠ warn or declared  /  ✔ no alert</text>']
    if unmapped:
        parts.append(f'<text class="legend" x="40" y="430">unmapped: {html.escape(", ".join(f"{k}={v}" for k, v in sorted(unmapped.items())))}</text>')
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def _events(repo: Path, run_id: str) -> list[dict[str, Any]]:
    path = journal_path(repo, run_id)
    events: list[dict[str, Any]] = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            value = json.loads(line)
            if isinstance(value, dict):
                events.append(value)
    except (OSError, json.JSONDecodeError):
        pass
    return events


def _run_mermaid(repo: Path, run_id: str) -> str:
    events = _events(repo, run_id)
    report = next((item for item in _reports(repo) if str(item.get("run_id")) == run_id), {"run_id": run_id, "alerts": []})
    critical, warns, unmapped, total = _counts(repo, [report])
    shown = events[:MAX_EVENTS]
    labels = [str(event.get("kind") or "event").replace('"', "'") for event in shown]
    lines = ["flowchart LR", f'  subgraph run["Run {run_id} (events: {len(events)}, findings: {total})"]']
    ids = []
    for index, label in enumerate(labels):
        node = f"event{index}"
        ids.append(node)
        lines.append(f'    {node}["{index + 1}: {label}"]')
    lines.extend(f"    {left} --> {right}" for left, right in zip(ids, ids[1:]))
    if len(events) > MAX_EVENTS:
        lines.append(f'    truncated["… truncated after {MAX_EVENTS} events"]')
        if ids:
            lines.append(f"    {ids[-1]} --> truncated")
    lines.append("  end")
    lines.append(f'  findings["findings<br/>{_badge("act", critical, warns)}"] -.-> {ids[-1] if ids else "run"}')
    if unmapped:
        lines.append(f'  unmapped["unmapped<br/>{WARN} {sum(unmapped.values())}"] -.-> findings')
    return "\n".join(lines) + "\n"


def render_dag(repo: Path, runs: int = DEFAULT_RUNS, *, run_id: str | None = None, fmt: str = "mermaid") -> str:
    repo = repo.resolve()
    if run_id:
        mermaid = _run_mermaid(repo, run_id)
        svg = _svg(repo, [next((item for item in _reports(repo) if str(item.get("run_id")) == run_id), {"run_id": run_id, "alerts": []})])
        return mermaid if fmt == "mermaid" else _dag_html(svg) if fmt == "html" else svg
    selected = _reports(repo)[:max(0, runs)]
    mermaid = _mermaid(repo, selected)
    svg = _svg(repo, selected)
    return mermaid if fmt == "mermaid" else _dag_html(svg) if fmt == "html" else svg


def _dag_html(svg: str) -> str:
    return (
        "<!doctype html>\n"
        '<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        "<title>Loop DAG</title>\n"
        "<style>body{margin:0;background:#111827}svg{display:block;margin:auto;max-width:100%;height:auto}</style>\n"
        f"</head>\n<body>{svg}</body>\n</html>\n"
    )


def write_dag(repo: Path, content: str, fmt: str, out: str | Path | None = None) -> Path:
    report_dir = (repo / agent_root("state", "reports")).resolve()
    path = (report_dir / (f"loop-dag.{fmt}" if out is None else str(out))).resolve()
    if report_dir not in path.parents and path != report_dir:
        raise ValueError("--out must remain under .agent-loop/state/reports")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def render_summary(repo: Path, runs: int = DEFAULT_RUNS) -> str:
    selected = _reports(repo)[:max(0, runs)]
    critical, warns, _, _ = _counts(repo.resolve(), selected)
    joined = ", ".join(f"{stage} {CRIT} {critical[stage]} / {WARN} {warns[stage]}" for stage in STAGES if critical[stage] or warns[stage])
    return f"DAG alerts: {joined}" if joined else "DAG alerts: none"


def _detail_entry(run: dict[str, Any], alert: dict[str, Any]) -> dict[str, Any]:
    check_id, bucket = _alert_bucket(alert)
    message = str(alert.get("message") or "")
    paths = [str(path) for path in alert.get("paths", []) if isinstance(path, str)]
    paths_total = int(alert.get("paths_total", len(paths)) or len(paths))
    return {
        "run_id": str(run.get("run_id") or "unknown"),
        "check_id": check_id,
        "bucket": bucket,
        "severity": "critical" if bucket == "critical" else "warn" if bucket == "warn" else "none",
        "message": message,
        "paths": paths,
        "paths_total": max(paths_total, len(paths)),
        "schema": int(run.get("schema", 1) or 1),
        "detail_available": int(run.get("schema", 1) or 1) >= 2,
    }


def _detail_entries(repo: Path, stage: str, runs: int, check: str | None) -> list[dict[str, Any]]:
    selected = _reports(repo)[:max(0, runs)]
    entries: list[dict[str, Any]] = []
    for run in selected:
        alerts = run.get("alerts") if isinstance(run.get("alerts"), list) else []
        for alert in alerts:
            if not isinstance(alert, dict):
                continue
            check_id = str(alert.get("check_id") or "unknown")
            if check and check_id != check:
                continue
            if STAGE_MAP.get(check_id) == stage and _alert_bucket(alert)[1] != "none":
                entries.append(_detail_entry(run, alert))
    if stage == "handoff" and _handoff_unconsumed(repo) and (not check or check == "handoff:unconsumed"):
        path = repo / agent_root("state", "handoff.json")
        try:
            handoff = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            handoff = {}
        if isinstance(handoff, dict):
            entries.append({
                "run_id": str(handoff.get("source_turn_id") or "unknown"),
                "check_id": "handoff:unconsumed",
                "bucket": "warn",
                "severity": "warn",
                "message": f"unconsumed handoff generated_at {handoff.get('generated_at', 'unknown')}",
                "paths": [],
                "paths_total": 0,
                "schema": 2,
                "detail_available": True,
            })
    return sorted(entries, key=lambda item: (-1 if item["run_id"] else 0, item["run_id"], item["check_id"]), reverse=True)


def _truncate_detail_message(message: str) -> str:
    if len(message) <= DETAIL_MESSAGE_MAX:
        return message
    return f"{message[:DETAIL_MESSAGE_MAX]} (+{len(message) - DETAIL_MESSAGE_MAX} more)"


def _detail_item_lines(item: dict[str, Any]) -> list[str]:
    item = _normalized_detail_item(item)
    bucket = item["bucket"]
    symbol = CRIT if bucket == "critical" else WARN
    severity = "critical" if bucket == "critical" else "warn"
    lines = [f"run {item['run_id']}  {item['check_id']}  {symbol} {severity}"]
    if item["schema"] == 1:
        lines.append("  (schema 1 sidecar — detail unavailable)")
        return lines
    lines.append(f"  message: {item['message'] or '(empty)'}")
    paths = item["paths"][:DETAIL_PATHS_MAX]
    if paths:
        extra = max(0, item["paths_total"] - len(paths))
        suffix = f" (+{extra} more)" if extra else ""
        lines.append(f"  paths: {', '.join(paths)}{suffix}")
    return lines


def _normalized_detail_item(item: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(item)
    normalized["message"] = _truncate_detail_message(str(item.get("message") or ""))
    normalized["paths"] = list(item.get("paths", []))[:DETAIL_PATHS_MAX]
    normalized["paths_total"] = max(int(item.get("paths_total", len(item.get("paths", []))) or 0), len(item.get("paths", [])))
    if not normalized.get("detail_available", True):
        normalized["detail"] = "schema 1 sidecar — detail unavailable"
    return normalized


def render_detail(repo: Path, stage: str, runs: int = DEFAULT_RUNS, *, check: str | None = None, as_json: bool = False) -> str:
    if stage not in STAGES:
        valid = "|".join(STAGES)
        raise ValueError(f"invalid stage {stage!r}; valid stages: {valid}")
    entries = _detail_entries(repo.resolve(), stage, runs, check)
    total = len(entries)
    visible = entries[:DETAIL_FINDINGS_MAX]
    critical = sum(item["bucket"] == "critical" for item in entries)
    warns = sum(item["bucket"] == "warn" for item in entries)
    run_count = len({item["run_id"] for item in entries})
    if as_json:
        payload = {
            "banner": "[loopeng-bootstrap v0.2.0 | loopeng/v0.2 | review-dag-detail]",
            "stage": stage,
            "check": check,
            "findings": total,
            "critical": critical,
            "warn": warns,
            "runs": run_count,
            "items": [_normalized_detail_item(item) for item in visible],
            "truncated": total > DETAIL_FINDINGS_MAX,
        }
        return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    lines = [
        "[loopeng-bootstrap v0.2.0 | loopeng/v0.2 | review-dag-detail]",
        f"stage: {stage} — findings: {total} ({CRIT} {critical})" + (f" / {WARN} {warns}" if warns else "") + f" across {run_count} runs",
        "",
    ]
    if not visible:
        lines.append("(no findings)")
    else:
        for index, item in enumerate(visible):
            if index:
                lines.append("")
            lines.extend(_detail_item_lines(item))
    if total > DETAIL_FINDINGS_MAX:
        lines.extend(["", f"(showing first {DETAIL_FINDINGS_MAX} of {total}; use --check or --runs to narrow the result)"])
    return "\n".join(lines) + "\n"
