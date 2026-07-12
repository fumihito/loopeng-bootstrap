from __future__ import annotations

import json
import os
import subprocess
from collections import Counter, defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from ._paths import agent_root
from .journal import append_event
from .okf.schema import parse_document
from .audit.policy import REVIEW_OLDEST_COUNT, REVIEW_RECURRENCE_THRESHOLD

MODE = "review"
MODE_PREFIX = f"{MODE}:"
COMPONENT = "loopeng/v0.2"
DEFAULT_RUNS = 5

try:
    VERSION = (Path(__file__).resolve().parents[1] / "VERSION").read_text(encoding="utf-8").strip()
except OSError:
    VERSION = "unknown"


def _reports(repo: Path) -> list[dict[str, Any]]:
    root = repo / agent_root("state", "reports")
    values: list[dict[str, Any]] = []
    for path in root.glob("*.json") if root.is_dir() else ():
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(value, dict) and value.get("schema") == 1 and value.get("run_id"):
            value["_path"] = path
            values.append(value)
    values.sort(key=lambda item: str(item.get("ended_at") or item.get("started_at") or item["_path"].stat().st_mtime), reverse=True)
    return values


def _parse_time(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _duration(run: dict[str, Any]) -> str:
    start, end = _parse_time(run.get("started_at")), _parse_time(run.get("ended_at"))
    if not start or not end:
        return "unknown"
    seconds = max(0.0, (end - start).total_seconds())
    if seconds >= 60:
        return f"{seconds / 60:.1f}m"
    return f"{seconds:.1f}s"


def _clean(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ").strip() or "unknown"


def _results(runs: list[dict[str, Any]]) -> list[str]:
    lines = ["## Results", "| run | agent | goal | duration | critical | warn | memory |", "|---|---|---|---:|---:|---:|---|"]
    for run in runs:
        alerts = run.get("alerts") if isinstance(run.get("alerts"), list) else []
        critical = sum(1 for item in alerts if isinstance(item, dict) and item.get("severity") == "critical")
        warn = sum(1 for item in alerts if isinstance(item, dict) and item.get("severity") == "warn")
        memory = run.get("memory") if isinstance(run.get("memory"), dict) else {}
        applied, rejected = int(memory.get("applied", 0) or 0), int(memory.get("rejected", 0) or 0)
        memory_text = f"+{applied} applied" + (f", {rejected} rejected" if rejected else "")
        lines.append(f"| {_clean(run.get('run_id'))} | {_clean(run.get('agent'))} | {_clean(run.get('goal'))} | {_duration(run)} | {critical} | {warn} | {memory_text} |")
    if not runs:
        lines.append("| none | - | - | - | 0 | 0 | - |")
    return lines


def _learning_summary(repo: Path) -> str:
    root = repo / agent_root("state", "learning")
    paths = sorted(root.glob("*.json"), key=lambda item: item.stat().st_mtime) if root.is_dir() else []
    if not paths:
        return "learning backlog: 0 entries"
    oldest = paths[0].stat().st_mtime
    return f"learning backlog: {len(paths)} entries (oldest {datetime.fromtimestamp(oldest).date().isoformat()})"


def _concerns(repo: Path, runs: list[dict[str, Any]]) -> list[str]:
    lines = ["## Concerns"]
    occurrences: defaultdict[str, dict[str, str]] = defaultdict(dict)
    info_count = 0
    for run in runs:
        for alert in run.get("alerts", []) if isinstance(run.get("alerts"), list) else []:
            if not isinstance(alert, dict):
                continue
            check_id, severity = str(alert.get("check_id") or "unknown"), str(alert.get("severity") or "info")
            if severity in {"warn", "critical"}:
                run_id = str(run.get("run_id"))
                prior = occurrences[check_id].get(run_id)
                if prior != "critical":
                    occurrences[check_id][run_id] = "critical" if severity == "critical" else severity
            else:
                info_count += 1
    recurring = {key for key, values in occurrences.items() if len(values) >= REVIEW_RECURRENCE_THRESHOLD}
    for check_id in sorted(recurring):
        values = occurrences[check_id]
        severity = next(iter(values.values()))
        lines.append(f"- [RECURRING] {check_id} ({severity}) — {len(values)}/{len(runs)} runs")
    for run in runs:
        for alert in run.get("alerts", []) if isinstance(run.get("alerts"), list) else []:
            if not isinstance(alert, dict) or str(alert.get("severity")) not in {"warn", "critical"}:
                continue
            check_id = str(alert.get("check_id") or "unknown")
            if check_id not in recurring:
                lines.append(f"- {check_id} ({alert.get('severity')}) — run {run.get('run_id')}")
    lines.append(f"- info alerts: {info_count}")
    lines.append(f"- {_learning_summary(repo)}")
    handoff = repo / agent_root("state", "handoff.json")
    try:
        value = json.loads(handoff.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        value = {}
    lines.append(f"- unconsumed handoff: {'yes' if isinstance(value, dict) and not value.get('consumed_at') and value else 'no'}")
    lines.append(f"- undeclared critical: {'yes' if any(run.get('undeclared_critical') for run in runs) else 'none in selected runs'}")
    return lines


def _invalidation(body: str) -> str:
    lines = body.splitlines()
    for index, line in enumerate(lines):
        if line.strip().lower() == "# invalidation":
            for candidate in lines[index + 1:]:
                if candidate.strip():
                    return candidate.strip().lstrip("- ")
            break
    return "(未記載)"


def _premises(repo: Path) -> list[str]:
    today = date.today()
    entries: list[dict[str, Any]] = []
    for kind in ("decisions", "constraints"):
        root = repo / "llmwiki" / kind
        for path in root.rglob("*.md") if root.is_dir() else ():
            try:
                frontmatter, body = parse_document(path)
            except OSError:
                continue
            if frontmatter.get("status") != "active":
                continue
            review_after = frontmatter.get("review_after")
            due = False
            if isinstance(review_after, str):
                try:
                    due = date.fromisoformat(review_after) <= today
                except ValueError:
                    pass
            tags = frontmatter.get("tags") if isinstance(frontmatter.get("tags"), list) else []
            pending = "pending-decision" in tags
            timestamp = str(frontmatter.get("timestamp") or "9999-12-31")
            entries.append({"path": path, "frontmatter": frontmatter, "body": body, "due": due, "pending": pending, "timestamp": timestamp})
    lines = ["## Premises to revisit"]
    marked: set[Path] = set()
    for entry in sorted((item for item in entries if item["due"]), key=lambda item: item["timestamp"]):
        marked.add(entry["path"])
        lines.append(f"- [DUE] {entry['path'].relative_to(repo).with_suffix('')} — review_after {entry['frontmatter'].get('review_after')}; invalidation: {_invalidation(entry['body'])}")
    for entry in sorted((item for item in entries if item["pending"] and item["path"] not in marked), key=lambda item: item["timestamp"]):
        marked.add(entry["path"])
        tags = ", ".join(str(tag) for tag in entry["frontmatter"].get("tags", []))
        lines.append(f"- [PENDING] {entry['path'].relative_to(repo).with_suffix('')} (tag: {tags}) — invalidation: {_invalidation(entry['body'])}")
    oldest = sorted((item for item in entries if item["path"] not in marked), key=lambda item: item["timestamp"])[:REVIEW_OLDEST_COUNT]
    for entry in oldest:
        lines.append(f"- [OLDEST] {entry['path'].relative_to(repo).with_suffix('')} — active since {entry['frontmatter'].get('timestamp', 'unknown')}; invalidation: {_invalidation(entry['body'])}")
    if len(lines) == 1:
        lines.append("- none")
    return lines


def render_review(repo: Path, runs: int = DEFAULT_RUNS, section: str | None = None) -> str:
    selected = _reports(repo)[:max(0, runs)]
    sections = {"results": _results(selected), "concerns": _concerns(repo, selected), "premises": _premises(repo)}
    chosen = [sections[section]] if section else [sections["results"], _scope(selected, runs), sections["concerns"], sections["premises"]]
    return f"[{_banner()}]\n# Loop Review (last {runs} runs)\n\n" + "\n\n".join("\n".join(part) for part in chosen) + "\n"


def _banner() -> str:
    return f"loopeng-bootstrap v{VERSION} | {COMPONENT} | {MODE}"


def _scope(runs: list[dict[str, Any]], requested: int) -> list[str]:
    return [f"Scope: last {len(runs)} of {requested} runs with sidecar"]


def record_review(repo: Path, run_id: str, sections: list[str]) -> None:
    append_event(repo, run_id, {"kind": MODE, "sections": sections})


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(prog="loopeng review")
    parser.add_argument("--runs", type=int, default=DEFAULT_RUNS)
    parser.add_argument("--repo", type=Path, default=Path("."))
    parser.add_argument("--section", choices=("results", "concerns", "premises"))
    parser.add_argument("--run")
    args = parser.parse_args(argv)
    if args.runs < 0:
        parser.error("--runs must be non-negative")
    repo = args.repo.expanduser().resolve()
    sysout = render_review(repo, args.runs, args.section)
    print(sysout, end="")
    if args.run:
        record_review(repo, args.run, [args.section] if args.section else ["results", "concerns", "premises"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
