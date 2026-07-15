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
from .review_request import build_request, resolve_packet
from .review_intake import ACCEPTED_REL, confirm_incoming, incoming_preview, intake, intake_auto, _move_intake_file
from .run import record_human_outcome
from .audit.report import run_audit_report
from .audit.export import export_packet
from ._paths import agent_root

DETAIL_LINES = 20
ESTABLISH_BATCH = 20
PACKET_DETAIL_MAX_LINES = 20000
_WEB_SERVERS: dict[Path, Any] = {}


def read_one_key_confirmation(input_stream: Any, output_stream: Any, prompt: str) -> str:
    output_stream.write(prompt)
    output_stream.flush()
    if not getattr(input_stream, "isatty", lambda: False)():
        try:
            return input_stream.readline().strip().casefold()
        except KeyboardInterrupt:
            return ""
    try:
        import termios
        import tty
        fd = input_stream.fileno()
        previous = termios.tcgetattr(fd)
        try:
            tty.setcbreak(fd)
            value = input_stream.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, previous)
        output_stream.write("\n")
        output_stream.flush()
        return value.strip().casefold()
    except KeyboardInterrupt:
        try:
            return input_stream.readline().strip().casefold()
        except KeyboardInterrupt:
            return ""
    except Exception:
        try:
            return input_stream.readline().strip().casefold()
        except KeyboardInterrupt:
            return ""

ACTION_TABLE = {
    "provisional": ("establish", "detail", "skip"),
    "draft": ("approve", "reject", "detail", "skip"),
    "external-review": ("request", "packet", "detail", "skip"),
    "incoming-review": ("confirm", "meta-review", "detail", "skip"),
    "held": ("go", "alt", "hold", "detail", "skip"),
    "outcome": ("pass", "fail", "detail", "skip"),
}


def actions_for(item: dict[str, Any]) -> tuple[str, ...]:
    if item.get("kind") == "incoming-review":
        if item.get("relation") == "self-family":
            return ("meta-review", "detail", "skip")
        return ("intake", "detail", "skip") if item.get("human_confirmed") else ("confirm", "detail", "skip")
    if item.get("kind") == "external-review" and item.get("incoming_candidate"):
        return ("request", "packet", "intake", "detail", "skip")
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
        packet = resolve_packet(repo, str(item["target"]))
        if packet is None:
            return (f"packet unavailable for run {item['target']}\n"
                    f"Generate it with: python3 -m loopeng audit export --run {item['target']}")
        return "\n".join(packet_detail_lines(packet))
    if kind == "incoming-review":
        return incoming_preview(_path(repo, item))
    return json.dumps({key: item.get(key) for key in ("kind", "target", "label", "age_days")}, ensure_ascii=False, indent=2)


def packet_detail_lines(packet: Path) -> list[str]:
    """Read the exported packet files for the read-only TUI pager."""
    manifest = packet / "manifest.json"
    try:
        value = json.loads(manifest.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return [f"manifest unavailable: {manifest}"]
    listed = value.get("files") if isinstance(value, dict) else []
    names = [str(name) for name in listed if isinstance(name, str)]
    if "manifest.json" not in names:
        names.insert(0, "manifest.json")
    expanded: list[tuple[int, str]] = []
    for index, name in enumerate(names):
        candidate = (packet / name).resolve()
        try:
            candidate.relative_to(packet.resolve())
        except ValueError:
            expanded.append((index, name))
            continue
        if candidate.is_dir():
            expanded.extend((index, path.relative_to(packet).as_posix()) for path in sorted(candidate.rglob("*")) if path.is_file())
        else:
            expanded.append((index, name))
    names = [name for _, name in sorted(expanded, key=lambda entry: (not entry[1].casefold().endswith(".md"), entry[0], entry[1]))]
    lines = [f"Packet: {packet}", "Read-only packet contents", ""]
    for name in names:
        path = (packet / name).resolve()
        try:
            path.relative_to(packet.resolve())
        except ValueError:
            lines.extend([f"===== {name} (blocked path) =====", ""])
            continue
        lines.extend([f"===== {name} ====="])
        try:
            content = path.read_text(encoding="utf-8")
            lines.extend(content.splitlines() or ["(empty)"])
        except (OSError, UnicodeError) as exc:
            lines.append(f"unreadable: {type(exc).__name__}")
        lines.append("")
        if len(lines) >= PACKET_DETAIL_MAX_LINES:
            lines.append("(packet detail truncated)")
            break
    return lines[:PACKET_DETAIL_MAX_LINES]


def generate_packet(repo: Path, run_id: str) -> Path:
    """Delegate packet creation to the existing deterministic audit export."""
    return export_packet(repo.resolve(), run_id)


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
    if action == "intake" and all(item.get("kind") == "incoming-review" for item in items):
        if len(items) > 1:
            return {"ok": True, "action": action, **intake_auto(repo)}
        result = intake(repo, _path(repo, items[0]))
        if result.get("accepted"):
            result["path"] = _move_intake_file(_path(repo, items[0]), repo / ACCEPTED_REL)
        return {"ok": bool(result.get("accepted")), **result}
    if action == "confirm" and all(item.get("kind") == "incoming-review" for item in items):
        results = [confirm_incoming(_path(repo, current)) for current in items]
        return {"ok": all(result.get("confirmed") for result in results), "confirmed": results}
    if action == "web" and all(item.get("kind") in {"external-review", "incoming-review"} for item in items):
        if len(items) != 1:
            return {"ok": False, "error": "web view requires one review"}
        from .htmlview import render_index, render_review
        from .webserve import serve
        current = items[0]
        target = str(current.get("target") or current.get("run_id") or "")
        if not target:
            return {"ok": False, "error": "review run id unavailable"}
        path = render_review(repo.resolve(), target)
        render_index(repo.resolve())
        key = repo.resolve()
        server = _WEB_SERVERS.get(key)
        if server is None or server.httpd is None:
            server = serve(key)
            _WEB_SERVERS[key] = server
        return {"ok": True, "action": "web", "path": str(path), "url": f"{server.url}review/{target}/", "note": "self-signed certificate: browser trust warning"}
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
    if action == "intake" and kind == "external-review" and current.get("incoming_candidate"):
        candidates = [candidate for candidate in list_items(repo)
                      if candidate.get("kind") == "incoming-review" and candidate.get("run_id") == current.get("target")]
        if not candidates:
            return {"ok": False, "error": "incoming review no longer exists"}
        return execute(repo, candidates[0], action, run_id, value)
    if action == "packet" and kind == "external-review":
        packet = resolve_packet(repo, str(current["target"]))
        if packet is None:
            return {"ok": False, "error": f"packet unavailable for run {current['target']}; run audit export first"}
        return {"ok": True, "packet": str(packet / "manifest.json")}
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


def stop_web_server(repo: Path) -> None:
    server = _WEB_SERVERS.pop(repo.resolve(), None)
    if server is not None:
        server.stop()


def interactive(repo: Path, input_stream: Any, output_stream: Any) -> int:
    """Line-oriented driver; all mutations still go through ``execute``."""
    repo = repo.resolve()
    run_id = start_session(repo)
    interrupted = False
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
    except KeyboardInterrupt:
        interrupted = True
        output_stream.write("\nInbox interactive session interrupted; session closed.\n")
    finally:
        end_session(repo, run_id)
    if interrupted:
        return 0
    answer = read_one_key_confirmation(input_stream, output_stream, "Run audit now? [Y/n] ")
    if answer not in {"n", "no"}:
        try:
            output_stream.write(f"audit: {run_audit_report(repo, run_id)}\n")
        except KeyboardInterrupt:
            output_stream.write("\nInbox interactive session interrupted during audit; session closed.\n")
    return 0
