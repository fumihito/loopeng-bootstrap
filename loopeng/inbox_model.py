"""Decision-free inbox model used by both interactive frontends."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .inbox import collect_inbox
from .journal import EVENT_DECISION, EVENT_EXTERNAL_REVIEW, EVENT_OKF_APPLY, EVENT_RUN_END, EVENT_RUN_START, append_event
from .okf.approval import approve, reject
from .okf.apply import apply_report
from .okf.promote import establish
from .review import record_decision
from .review_request import build_request
from .run import record_human_outcome
from .audit.report import run_audit_report
from ._paths import agent_root

DETAIL_LINES = 20
ESTABLISH_BATCH = 20

ACTION_TABLE = {
    "provisional": ("establish", "detail", "skip"),
    "draft": ("approve", "reject", "detail", "skip"),
    "external-review": ("request", "packet", "detail", "skip"),
    "held": ("go", "alt", "hold", "detail", "skip"),
    "outcome": ("pass", "fail", "detail", "skip"),
}


def actions_for(item: dict[str, Any]) -> tuple[str, ...]:
    return ACTION_TABLE.get(str(item.get("kind")), ("skip",))


def list_items(repo: Path) -> list[dict[str, Any]]:
    return collect_inbox(repo)


def _path(repo: Path, item: dict[str, Any]) -> Path:
    return repo / str(item["path"])


def detail(repo: Path, item: dict[str, Any]) -> str:
    kind = str(item.get("kind"))
    if kind in {"provisional", "draft"}:
        path = _path(repo, item)
        if kind == "draft":
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
                document = str(value.get("operations", [{}])[0].get("document") or "")
            except (OSError, json.JSONDecodeError, IndexError, TypeError):
                document = "unreadable draft"
            return "\n".join(document.splitlines()[:DETAIL_LINES])
        try:
            return "\n".join(path.read_text(encoding="utf-8").splitlines()[:DETAIL_LINES])
        except OSError:
            return "unreadable entry"
    if kind == "external-review":
        manifest = repo / agent_root("state", "review-packets") / str(item["target"]) / "manifest.json"
        try:
            value = json.loads(manifest.read_text(encoding="utf-8"))
            return json.dumps({key: value.get(key) for key in ("run_id", "packet_hash", "sanitized", "files") if key in value}, indent=2, ensure_ascii=False)
        except (OSError, json.JSONDecodeError):
            return f"packet: {manifest}\nmanifest unavailable"
    return json.dumps({key: item.get(key) for key in ("kind", "target", "label", "age_days")}, ensure_ascii=False, indent=2)


def _establish(repo: Path, items: list[dict[str, Any]], run_id: str) -> dict[str, Any]:
    if not items or any(item.get("kind") != "provisional" for item in items):
        return {"ok": False, "error": "establish requires provisional entries only"}
    ids = [str(item["target"]).removesuffix(".md").removeprefix("llmwiki/") for item in items]
    generated = establish(repo.resolve(), ids)
    results = []
    for batch in generated.get("drafts", []):
        report = Path(batch["draft"])
        result = apply_report(repo / "llmwiki", report, repo / agent_root("runtime", "okf-backups"))
        append_event(repo, run_id, {"kind": EVENT_OKF_APPLY, "report": str(report), "ok": bool(result.get("ok")), "touched": result.get("touched", []), "tier": "established", "actor": "tui-interactive"})
        if result.get("ok"):
            results.extend(batch.get("concept_ids", []))
            applied = repo / agent_root("state", "memory-drafts", "applied")
            applied.mkdir(parents=True, exist_ok=True)
            report.rename(applied / report.name)
        else:
            results.append({"error": "; ".join(map(str, result.get("errors", [])))})
    return {"ok": not any(isinstance(item, dict) for item in results), "applied": results}


def execute(repo: Path, item: dict[str, Any] | list[dict[str, Any]], action: str, run_id: str, value: str = "") -> dict[str, Any]:
    items = item if isinstance(item, list) else [item]
    if action == "skip" or action == "detail":
        return {"ok": True, "action": action, "detail": detail(repo, items[0]) if action == "detail" else ""}
    if action == "establish":
        return _establish(repo, items, run_id)
    if len(items) != 1:
        return {"ok": False, "error": "bulk actions require one kind and a supported bulk action"}
    current = items[0]
    kind = str(current.get("kind"))
    if action == "approve" and kind == "draft":
        return approve(repo, [str(current["target"])], "", run_id, authorization="tui-interactive")
    if action == "reject" and kind == "draft":
        if not value.strip():
            return {"ok": False, "cancelled": True, "error": "reject reason required"}
        return reject(repo, str(current["target"]), value, run_id)
    if action == "request" and kind == "external-review":
        request = build_request(repo, str(current["target"]))
        append_event(repo, run_id, {"kind": EVENT_EXTERNAL_REVIEW, "run_id": str(current["target"]), "status": "request-generated", "authorization": "tui-interactive"})
        return {"ok": True, "request": request}
    if action == "packet" and kind == "external-review":
        return {"ok": True, "packet": str(repo / agent_root("state", "review-packets") / str(current["target"]))}
    if action in {"go", "alt", "hold"} and kind == "held":
        record_decision(repo, str(current["target"]), action, run_id, authorization="tui-interactive")
        return {"ok": True, "choice": action}
    if action in {"pass", "fail"} and kind == "outcome":
        if action == "fail" and not value.strip():
            return {"ok": False, "cancelled": True, "error": "fail note required"}
        record_human_outcome(repo, str(current["target"]), action, value or "tui-interactive")
        return {"ok": True, "outcome": action}
    return {"ok": False, "error": f"action {action} is not available for {kind}"}


def start_session(repo: Path) -> str:
    run_id = "tui-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    append_event(repo, run_id, {"kind": EVENT_RUN_START, "agent": "human", "goal": "inbox interactive session", "mode": "standard"})
    return run_id


def end_session(repo: Path, run_id: str) -> None:
    append_event(repo, run_id, {"kind": EVENT_RUN_END, "agent": "human", "mode": "standard"})


def interactive(repo: Path, input_stream: Any, output_stream: Any) -> int:
    """Line-oriented driver; all mutations still go through ``execute``."""
    repo = repo.resolve()
    run_id = start_session(repo)
    try:
        while True:
            items = list_items(repo)
            output_stream.write(f"Inbox ({len(items)})\n")
            for index, item in enumerate(items, 1):
                output_stream.write(f"{index}) {item.get('kind')} {item.get('target')} {float(item.get('age_days', 0)):.1f}d\n")
            output_stream.write("Select number(s), or q: ")
            output_stream.flush()
            raw = input_stream.readline()
            if not raw or raw.strip().casefold() == "q":
                break
            try:
                indexes = [int(value) - 1 for value in raw.replace(",", " ").split()]
                chosen = [items[index] for index in indexes if 0 <= index < len(items)]
                if not chosen or len(chosen) != len(indexes):
                    raise ValueError
            except ValueError:
                output_stream.write("Invalid selection; try again.\n")
                continue
            kinds = {str(item.get("kind")) for item in chosen}
            if len(kinds) != 1:
                output_stream.write("Bulk selection must use one kind.\n")
                continue
            output_stream.write(f"Action {actions_for(chosen[0])}: ")
            action = input_stream.readline().strip().casefold()
            if action not in actions_for(chosen[0]):
                output_stream.write("Action unavailable; try again.\n")
                continue
            if len(chosen) > 1 and action == "establish":
                output_stream.write(f"establish {len(chosen)} entries? [y/N] ")
                if input_stream.readline().strip().casefold() != "y":
                    continue
            value = ""
            if action in {"reject", "fail"}:
                output_stream.write("Reason/note (empty cancels): ")
                value = input_stream.readline().rstrip("\n")
                if not value.strip():
                    output_stream.write("Cancelled.\n")
                    continue
            result = execute(repo, chosen, action, run_id, value)
            output_stream.write(json.dumps(result, ensure_ascii=False) + "\n")
    finally:
        end_session(repo, run_id)
    output_stream.write("Run audit now? [Y/n] ")
    output_stream.flush()
    answer = input_stream.readline().strip().casefold()
    if answer not in {"n", "no"}:
        output_stream.write(f"audit: {run_audit_report(repo, run_id)}\n")
    return 0
