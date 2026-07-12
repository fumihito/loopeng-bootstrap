from __future__ import annotations

import json
import hashlib
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
from .review_catalog import CATALOG_BY_ID, REMEDIATION_CATALOG

MODE = "review"
MODE_PREFIX = f"{MODE}:"
COMPONENT = "loopeng/v0.2"
DEFAULT_RUNS = 5
JACCARD_THRESHOLD = 0.5
TRIAGE_ITEM_MAX_LINES = 12
REVIEW_CURSOR_RELATIVE = agent_root("state", "review-cursor.json")

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


def _member_occurrences(repo: Path, runs: list[dict[str, Any]]) -> dict[str, set[str]]:
    occurrences: dict[str, set[str]] = defaultdict(set)
    for run in runs:
        run_id = str(run.get("run_id") or "unknown")
        for alert in run.get("alerts", []) if isinstance(run.get("alerts"), list) else []:
            if isinstance(alert, dict):
                check_id = str(alert.get("check_id") or "unknown")
                if check_id == "protected_path_mutation" and run.get("undeclared_critical"):
                    continue
                occurrences[check_id].add(run_id)
        if run.get("undeclared_critical"):
            occurrences["protected_path_mutation:undeclared"].add(run_id)
    handoff = repo / agent_root("state", "handoff.json")
    try:
        value = json.loads(handoff.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        value = {}
    if isinstance(value, dict) and value and not value.get("consumed_at"):
        for run in runs:
            occurrences["handoff:unconsumed"].add(str(run.get("run_id") or "unknown"))
    # A backlog is a repository-level condition, but it is represented on each
    # selected run so grouping and run counts remain uniform.
    learning = repo / agent_root("state", "learning")
    if learning.is_dir() and any(learning.glob("*.json")):
        for run in runs:
            occurrences["learning_backlog"].add(str(run.get("run_id") or "unknown"))
    return occurrences


def _jaccard(left: set[str], right: set[str]) -> float:
    union = left | right
    return len(left & right) / len(union) if union else 1.0


def _held(repo: Path) -> set[str]:
    result: set[str] = set()
    root = repo / agent_root("state", "journal")
    for path in root.glob("*.jsonl") if root.is_dir() else ():
        try:
            for line in path.read_text(encoding="utf-8").splitlines():
                event = json.loads(line)
                if event.get("kind") == "decision" and event.get("choice") == "hold" and event.get("item"):
                    result.add(str(event["item"]))
        except (OSError, json.JSONDecodeError):
            continue
    return result


def _triage_items(repo: Path, runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    occurrences = _member_occurrences(repo, runs)
    handoff_path = repo / agent_root("state", "handoff.json")
    try:
        handoff_value = json.loads(handoff_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        handoff_value = {}
    learning_root = repo / agent_root("state", "learning")

    def finding_count(member: str) -> int:
        if member == "protected_path_mutation:undeclared":
            return sum(1 for run in runs if run.get("undeclared_critical"))
        if member == "handoff:unconsumed":
            return len(runs) if isinstance(handoff_value, dict) and handoff_value and not handoff_value.get("consumed_at") else 0
        if member == "learning_backlog":
            alert_count = sum(1 for run in runs for alert in run.get("alerts", []) if isinstance(alert, dict) and alert.get("check_id") == member)
            return alert_count or (len(runs) if learning_root.is_dir() and any(learning_root.glob("*.json")) else 0)
        return sum(1 for run in runs for alert in run.get("alerts", []) if isinstance(alert, dict) and alert.get("check_id") == member and not (member == "protected_path_mutation" and run.get("undeclared_critical")))

    consumed: set[str] = set()
    items: list[dict[str, Any]] = []
    for catalog in REMEDIATION_CATALOG:
        active = [member for member in catalog["members"] if occurrences.get(member)]
        if len(active) >= 2 and all(_jaccard(occurrences[a], occurrences[b]) >= JACCARD_THRESHOLD for index, a in enumerate(active) for b in active[index + 1:]):
            members = active
            consumed.update(members)
        elif len(active) == 1 and len(catalog["members"]) == 1:
            members = active
            consumed.update(members)
        else:
            # A known member that does not meet the co-occurrence threshold is
            # still a real item; it must not disappear or be mislabeled as a
            # catalog miss.
            if len(active) > 1:
                for member in active:
                    single = {"id": member, "members": (member,), "cause": "単独発生のため共通根本原因とは判定しない", "standard_fix": "該当 finding の個別確認", "alt_fix": "個別確認を保留", "question": "この finding を個別確認しますか?", "agent_executable": False}
                    run_set = occurrences[member]
                    critical = sum(1 for run in runs for alert in run.get("alerts", []) if isinstance(alert, dict) and alert.get("check_id") == member and alert.get("severity") == "critical")
                    critical += sum(1 for run in runs if run.get("undeclared_critical") and member == "protected_path_mutation:undeclared")
                    items.append({"id": member, "catalog": single, "members": [member], "runs": run_set, "count": finding_count(member), "critical": critical, "undeclared": member == "protected_path_mutation:undeclared", "recurring": len(run_set) >= REVIEW_RECURRENCE_THRESHOLD})
                    consumed.add(member)
                continue
            if len(active) != 1:
                continue
            member = active[0]
            catalog = {"id": member, "members": (member,), "cause": "単独発生のため共通根本原因とは判定しない", "standard_fix": "該当 finding の個別確認", "alt_fix": "個別確認を保留", "question": "この finding を個別確認しますか?", "agent_executable": False}
            members = [member]
            consumed.add(member)
        run_set = set().union(*(occurrences[name] for name in members))
        critical = sum(1 for run in runs for alert in run.get("alerts", []) if isinstance(alert, dict) and alert.get("check_id") in members and alert.get("severity") == "critical")
        critical += sum(1 for run in runs if run.get("undeclared_critical") and "protected_path_mutation:undeclared" in members)
        undeclared = any(name == "protected_path_mutation:undeclared" for name in members)
        items.append({"id": catalog["id"], "catalog": catalog, "members": members, "runs": run_set, "count": sum(finding_count(name) for name in members), "critical": critical, "undeclared": undeclared, "recurring": len(run_set) >= REVIEW_RECURRENCE_THRESHOLD})
    for check_id, run_set in occurrences.items():
        if check_id in consumed or any(check_id in item["members"] for item in items):
            continue
        if check_id.endswith(":undeclared"):
            catalog = {"id": check_id, "members": (check_id,), "cause": "未宣言 critical の単独発生", "standard_fix": "該当 finding の個別確認", "alt_fix": "個別確認を保留", "question": "この未宣言 critical を個別確認しますか?", "agent_executable": False}
            items.append({"id": check_id, "catalog": catalog, "members": [check_id], "runs": run_set, "count": finding_count(check_id), "critical": len(run_set), "undeclared": True, "recurring": len(run_set) >= REVIEW_RECURRENCE_THRESHOLD})
            continue
        catalog = {"id": f"catalog-miss:{check_id}", "members": (check_id,), "cause": "未登録 check_id の発火", "standard_fix": "digest 該当行を提示して個別確認", "alt_fix": "個別確認を保留", "question": "この未登録 check_id を個別確認しますか?", "agent_executable": False}
        critical = sum(1 for run in runs for alert in run.get("alerts", []) if isinstance(alert, dict) and alert.get("check_id") == check_id and alert.get("severity") == "critical")
        items.append({"id": catalog["id"], "catalog": catalog, "members": [check_id], "runs": run_set, "count": finding_count(check_id), "critical": critical, "undeclared": False, "recurring": len(run_set) >= REVIEW_RECURRENCE_THRESHOLD})
    def priority(item: dict[str, Any]) -> tuple[int, int, int, int]:
        if item["undeclared"]: rank = 0
        elif item["recurring"]: rank = 1
        elif item["critical"]: rank = 2
        elif item["catalog"]["members"][0] in {"learning_backlog", "handoff:unconsumed"}: rank = 4
        else: rank = 3
        return (rank, -item["count"], -len(item["runs"]), item["id"])
    return sorted(items, key=priority)


def _digest_hash(runs: list[dict[str, Any]]) -> str:
    payload = json.dumps(runs, sort_keys=True, default=str, ensure_ascii=False).encode()
    return hashlib.sha256(payload).hexdigest()


def _cursor_path(repo: Path) -> Path:
    return repo / REVIEW_CURSOR_RELATIVE


def _load_cursor(repo: Path, digest_hash: str, *, reset: bool = False) -> dict[str, Any]:
    path = _cursor_path(repo)
    try:
        cursor = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        cursor = {}
    if reset or not isinstance(cursor, dict) or cursor.get("digest_hash") != digest_hash:
        cursor = {"digest_hash": digest_hash, "presented": []}
    return cursor


def _save_cursor(repo: Path, cursor: dict[str, Any]) -> None:
    path = _cursor_path(repo)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(cursor, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _render_item(item: dict[str, Any], index: int, total: int, held: bool = False) -> str:
    catalog = item["catalog"]
    recurring = " [RECURRING]" if item["recurring"] else ""
    held_marker = " [HELD]" if held else ""
    lines = [f"#{index} [{item['id']}]" + recurring + held_marker,
             f"   {', '.join(item['members'])}",
             f"   {item['count']} findings across {len(item['runs'])} runs",
             f"   原因: {catalog['cause']}",
             f"   標準対処: {catalog['standard_fix']}",
             f"   代替対処: {catalog['alt_fix']}",
             f"   質問: {catalog['question']} [go {item['id']} / 代替 / 保留]"]
    return "\n".join(lines[:TRIAGE_ITEM_MAX_LINES])


def render_triage(repo: Path, runs: int = DEFAULT_RUNS, *, next_item: bool = False, as_json: bool = False) -> str:
    selected = _reports(repo)[:max(0, runs)]
    items = _triage_items(repo, selected)
    digest_hash = _digest_hash(selected)
    cursor = _load_cursor(repo, digest_hash, reset=not next_item)
    presented = list(cursor.get("presented", []))
    item = next((candidate for candidate in items if candidate["id"] not in presented), None) if next_item else (items[0] if items else None)
    if item and item["id"] not in presented:
        presented.append(item["id"])
    cursor["presented"] = presented
    _save_cursor(repo, cursor)
    if as_json:
        output = {"banner": _banner() + "-triage", "findings": sum(item["count"] for item in items), "items": [{k: v for k, v in candidate.items() if k not in {"catalog", "runs"}} | {"runs": sorted(candidate["runs"])} for candidate in items], "presented": presented, "selected_item": item["id"] if item else None}
        return json.dumps(output, indent=2, ensure_ascii=False) + "\n"
    if not items:
        return f"[{_banner()}-triage]\nfindings: 0 → grouped into 0 items\n"
    critical = sum(candidate["critical"] for candidate in items)
    warns = sum(1 for run in selected for alert in run.get("alerts", []) if isinstance(alert, dict) and alert.get("severity") == "warn")
    lines = [f"[{_banner()}-triage]", f"findings: {sum(candidate['count'] for candidate in items)} (critical {critical}, warn {warns}) → grouped into {len(items)} items", ""]
    if item:
        lines.append(_render_item(item, items.index(item) + 1, len(items), item["id"] in _held(repo)))
        remaining = len(items) - 1
        if remaining:
            lines.extend(["", f"(残り {remaining} 項目 — `review: next` で表示)"])
    return "\n".join(lines) + "\n"


def execute_go(repo: Path, item_id: str, run_id: str | None = None) -> str:
    items = _triage_items(repo, _reports(repo)[:DEFAULT_RUNS])
    item = next((candidate for candidate in items if candidate["id"] == item_id), None)
    run_id = run_id or "review-go-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    append_event(repo, run_id, {"kind": "run-start", "agent": "review", "goal": f"review: go {item_id}"})
    append_event(repo, run_id, {"kind": "decision", "item": item_id, "choice": "go"})
    if item is None:
        result = f"未知 item-id: {item_id}; 実行せず停止します。"
    elif not item["catalog"]["agent_executable"]:
        result = f"[{item_id}] は起票/ユーザー判断が必要です。実行せず停止します。"
    else:
        proposal = repo / agent_root("state", "review-proposals") / f"{item_id.replace(':', '-')}-{run_id}.md"
        proposal.parent.mkdir(parents=True, exist_ok=True)
        proposal.write_text(f"# Review proposal: {item_id}\n\n{item['catalog']['standard_fix']}\n\n対象: {', '.join(item['members'])}\n", encoding="utf-8")
        result = f"[{item_id}] 起案を生成しました: {proposal.relative_to(repo)}。apply はしていません。"
    append_event(repo, run_id, {"kind": "go-result", "item": item_id, "result": result})
    append_event(repo, run_id, {"kind": "run-end", "agent": "review"})
    return result + "\n"


def record_decision(repo: Path, item_id: str, choice: str, run_id: str | None = None) -> str:
    if choice not in {"go", "alt", "hold"}:
        raise ValueError("choice must be go, alt, or hold")
    run_id = run_id or "review-decision-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    append_event(repo, run_id, {"kind": "run-start", "agent": "review", "goal": f"review: {choice} {item_id}"})
    append_event(repo, run_id, {"kind": "decision", "item": item_id, "choice": choice})
    append_event(repo, run_id, {"kind": "run-end", "agent": "review"})
    return f"[{item_id}] choice={choice} を記録しました。停止します。\n"


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
    parser.add_argument("--triage", action="store_true")
    parser.add_argument("--next", dest="next_item", action="store_true")
    parser.add_argument("--full", action="store_true")
    parser.add_argument("--go")
    parser.add_argument("--decision")
    parser.add_argument("--choice", choices=("go", "alt", "hold"))
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args(argv)
    if args.runs < 0:
        parser.error("--runs must be non-negative")
    repo = args.repo.expanduser().resolve()
    if args.go:
        print(execute_go(repo, args.go, args.run), end="")
        return 0
    if args.decision:
        if not args.choice:
            parser.error("--decision requires --choice")
        print(record_decision(repo, args.decision, args.choice, args.run), end="")
        return 0
    if args.triage or args.next_item:
        print(render_triage(repo, args.runs, next_item=args.next_item, as_json=args.format == "json"), end="")
        return 0
    sysout = render_review(repo, args.runs, args.section)
    print(sysout, end="")
    if args.run:
        record_review(repo, args.run, [args.section] if args.section else ["results", "concerns", "premises"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
