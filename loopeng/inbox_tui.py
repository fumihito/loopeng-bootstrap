"""Curses-only presentation for the inbox model."""

from __future__ import annotations

import curses
import json
from pathlib import Path
from typing import Any

from .inbox_model import actions_for as model_actions_for, detail, execute, generate_packet, list_items, packet_detail_lines
from .review_request import resolve_packet
from .review_contract import CONTRACT_VERSION, REVIEW_DIMENSIONS, validate_contract


def _short(value: str, width: int) -> str:
    if len(value) <= width:
        return value
    return value[:max(1, width - 1)] + "…"


def actions_for(item: dict[str, Any]) -> tuple[str, ...]:
    options = model_actions_for(item)
    if item.get("kind") == "external-review" and "review" not in options:
        return ("request", "review", *options[1:])
    return options


def _available_label(items: list[dict[str, Any]], marked: set[int]) -> str:
    kinds = {str(items[index].get("kind")) for index in marked if index < len(items)}
    if len(kinds) != 1:
        return "mixed/none"
    actions = {action for index in marked if index < len(items) for action in actions_for(items[index])}
    return ",".join(sorted(actions))


def _prompt(screen: Any, text: str) -> str:
    height, width = screen.getmaxyx()
    screen.move(max(0, height - 2), 0)
    screen.clrtoeol()
    screen.addnstr(max(0, height - 2), 0, text, max(1, width - 1))
    screen.refresh()
    curses.echo()
    try:
        return screen.getstr(max(0, height - 1), 0).decode(errors="replace")
    except KeyboardInterrupt:
        return ""
    finally:
        curses.noecho()


def _next_completion(value: str, options: tuple[str, ...], index: int) -> tuple[str, int]:
    matches = [option for option in options if option.startswith(value)]
    if not matches:
        return value, index
    next_index = (index + 1) % len(matches)
    return matches[next_index], next_index


def _action_prompt(screen: Any, options: tuple[str, ...]) -> str:
    """Read an action, cycling matching actions with Tab."""
    height, width = screen.getmaxyx()
    value = ""
    completion_index = -1
    completion_prefix: str | None = None
    curses.noecho()
    try:
        while True:
            screen.move(max(0, height - 2), 0)
            screen.clrtoeol()
            screen.addnstr(max(0, height - 2), 0, f"action {options}: {value}", max(1, width - 1))
            screen.refresh()
            try:
                key = screen.getch()
            except KeyboardInterrupt:
                return ""
            if key in (curses.KEY_ENTER, 10, 13):
                return value
            if key in (27,):
                return ""
            if key in (curses.KEY_BACKSPACE, 8, 127):
                value = value[:-1]
                completion_index = -1
                completion_prefix = None
            elif key in (9,):
                if completion_index == -1:
                    completion_prefix = value
                value, completion_index = _next_completion(completion_prefix or value, options, completion_index)
            elif 0 <= key < 256:
                value += chr(key)
                completion_index = -1
                completion_prefix = None
    finally:
        curses.noecho()


def _pager(screen: Any, lines: list[str]) -> None:
    offset = 0
    while True:
        screen.erase()
        height, width = screen.getmaxyx()
        page_size = max(1, height - 2)
        screen.addnstr(0, 0, f"Detail  lines {offset + 1}-{min(len(lines), offset + page_size)} / {len(lines)}  [j/k, arrows, Space=page, q=back]", max(1, width - 1))
        for row, line in enumerate(lines[offset:offset + page_size], 1):
            screen.addnstr(row, 0, _short(line, max(1, width - 1)), max(1, width - 1))
        screen.refresh()
        key = screen.getch()
        if key in (ord("q"), 27):
            return
        if key in (curses.KEY_DOWN, ord("j")):
            offset = min(max(0, len(lines) - page_size), offset + 1)
        elif key in (curses.KEY_UP, ord("k")):
            offset = max(0, offset - 1)
        elif key in (ord(" "), curses.KEY_NPAGE):
            offset = min(max(0, len(lines) - page_size), offset + page_size)
        elif key == curses.KEY_PPAGE:
            offset = max(0, offset - page_size)


def _missing_packet(screen: Any, repo: Path, run_id: str) -> None:
    while True:
        screen.erase()
        height, width = screen.getmaxyx()
        screen.addnstr(0, 0, f"Packet unavailable for {run_id}", max(1, width - 1))
        screen.addnstr(2, 0, "[g] generate packet with audit export  [q] back", max(1, width - 1))
        screen.refresh()
        key = screen.getch()
        if key in (ord("q"), 27):
            return
        if key == ord("g"):
            try:
                packet = generate_packet(repo, run_id)
                _pager(screen, packet_detail_lines(packet))
            except (OSError, RuntimeError, ValueError) as exc:
                screen.addnstr(max(4, height - 2), 0, _short(f"export failed: {type(exc).__name__}", max(1, width - 1)), max(1, width - 1))
                screen.refresh()
                screen.getch()
            return


def _confirm_exit(screen: Any) -> bool:
    # Do not let the Ctrl-C that triggered this confirmation immediately
    # cancel the confirmation input itself.
    curses.flushinp()
    height, width = screen.getmaxyx()
    screen.move(max(0, height - 2), 0)
    screen.clrtoeol()
    screen.addnstr(max(0, height - 2), 0, "exit? [y/N] ", max(1, width - 1))
    screen.refresh()
    try:
        curses.noecho()
        key = screen.getch()
        return key in (ord("y"), ord("Y"))
    except KeyboardInterrupt:
        return False
    finally:
        curses.noecho()


def build_human_review(repo: Path, run_id: str, verdicts: tuple[str, ...], overall: str) -> dict[str, Any]:
    packet = resolve_packet(repo, run_id)
    if packet is None:
        raise ValueError(f"packet unavailable for {run_id}")
    manifest = json.loads((packet / "manifest.json").read_text(encoding="utf-8"))
    journal = json.loads((packet / "journal.json").read_text(encoding="utf-8"))
    source_index = json.loads((packet / "source-index.json").read_text(encoding="utf-8"))
    sidecars = [path for path in packet.glob("*.json") if path.name not in {"manifest.json", "journal.json", "source-index.json"}]
    sidecar = json.loads(sidecars[0].read_text(encoding="utf-8")) if sidecars else {}
    critical = sum(1 for alert in sidecar.get("alerts", []) if isinstance(alert, dict) and alert.get("severity") == "critical")
    warn = sum(1 for alert in sidecar.get("alerts", []) if isinstance(alert, dict) and alert.get("severity") == "warn")
    journal_ref = f"journal:{run_id}:1" if journal else ""
    source_ref = next((f"file:{name}:1" for name, lines in sorted(source_index.items()) if int(lines) > 0), "")
    notes = {"D1": "process consistency reviewed", "D2": "outcome reviewed",
             "D3": "memory write reviewed", "D4": f"critical={critical} warn={warn}",
             "D5": "implementation claim reviewed"}
    dimensions = []
    for identifier, verdict in zip(REVIEW_DIMENSIONS, verdicts):
        ref = source_ref if identifier == "D5" else journal_ref
        dimensions.append({"id": identifier, "verdict": verdict,
                           "evidence": ([{"ref": ref, "note": notes[identifier]}] if verdict != "unable" and ref else []),
                           "note": notes[identifier]})
    value = {"contract": CONTRACT_VERSION,
             "reviewer": {"model": "human-tui", "session": f"tui-review-{run_id}", "relation": "external"},
             "packet": {"run_id": run_id, "packet_hash": str(manifest["packet_hash"])},
             "dimensions": dimensions, "overall": overall, "findings": []}
    errors = validate_contract(value)
    if errors:
        raise ValueError("; ".join(errors))
    return value


def human_review_wizard(screen: Any, repo: Path, run_id: str) -> Path | None:
    verdicts: list[str] = []
    for identifier in REVIEW_DIMENSIONS:
        while True:
            screen.erase()
            _, width = screen.getmaxyx()
            screen.addnstr(0, 0, f"Human review {run_id}", max(1, width - 1))
            screen.addnstr(2, 0, f"{identifier}: verdict [p]ass / [f]ail / [u]nable  [q] cancel", max(1, width - 1))
            screen.refresh()
            try:
                key = screen.getch()
            except KeyboardInterrupt:
                return None
            if key in (ord("q"), 27):
                return None
            if key in (ord("p"), ord("f"), ord("u")):
                verdicts.append({ord("p"): "pass", ord("f"): "fail", ord("u"): "unable"}[key])
                break
    allowed = ("blocked-on-info",) if verdicts.count("unable") >= 3 else ("pass", "fail", "blocked-on-info")
    while True:
        screen.erase()
        _, width = screen.getmaxyx()
        screen.addnstr(0, 0, "Overall: [p]ass / [f]ail / [b]locked-on-info  [q] cancel", max(1, width - 1))
        screen.refresh()
        try:
            key = screen.getch()
        except KeyboardInterrupt:
            return None
        if key in (ord("q"), 27):
            return None
        overall = {ord("p"): "pass", ord("f"): "fail", ord("b"): "blocked-on-info"}.get(key)
        if overall in allowed:
            break
    try:
        value = build_human_review(repo, run_id, tuple(verdicts), overall)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return None
    incoming = repo.resolve() / ".agent-loop/state/reviews/incoming"
    incoming.mkdir(parents=True, exist_ok=True)
    target = incoming / f"tui-review-{run_id}.json"
    target.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


def run(repo: Path, run_id: str) -> None:
    def main(screen: Any) -> None:
        curses.curs_set(0)
        selected = 0
        marked: set[int] = set()
        messages: list[str] = []
        detail_lines: list[str] = []
        detail_offset = 0
        while True:
            items = list_items(repo)
            if items:
                selected = min(selected, len(items) - 1)
                detail_lines = detail(repo, items[selected]).splitlines() or ["(empty detail)"]
            else:
                selected = 0
                detail_lines = ["(inbox empty)"]
            detail_page_size = 8
            detail_offset = min(detail_offset, max(0, len(detail_lines) - detail_page_size))
            screen.erase()
            height, width = screen.getmaxyx()
            screen.addnstr(0, 0, f"Inbox ({len(items)})  [x]=mark [a]=act [d]=detail [A]=act-all-marked [q]=quit", max(1, width - 1))
            list_limit = max(0, height - detail_page_size - 6)
            for index, item in enumerate(items[:list_limit]):
                prefix = ">" if index == selected else " "
                mark = "x" if index in marked else " "
                target = _short(str(item.get("target", "")), max(10, width - 36))
                line = f"{prefix} [{mark}] {item.get('kind', ''):<16} {target:<{max(10, width - 36)}} {float(item.get('age_days', 0)):.1f}d"
                screen.addnstr(index + 2, 0, line, max(1, width - 1))
            screen.hline(max(2, height - 4), 0, curses.ACS_HLINE, max(1, width - 1))
            available = _available_label(items, marked)
            screen.addnstr(max(0, height - 3), 0, f"marked: {len(marked)}  available: {available}", max(1, width - 1))
            if detail_lines:
                detail_start = max(0, height - detail_page_size - 3)
                screen.addnstr(max(0, detail_start - 1), 0, f"Detail {detail_offset + 1}-{min(len(detail_lines), detail_offset + detail_page_size)}/{len(detail_lines)} ([/]=page, d=full)", max(1, width - 1))
                for offset, line in enumerate(detail_lines[detail_offset:detail_offset + detail_page_size]):
                    screen.addnstr(detail_start + offset, 0, _short(line, max(1, width - 1)), max(1, width - 1))
            if messages:
                screen.addnstr(max(0, height - 2), 0, _short(messages[-1], max(1, width - 1)), max(1, width - 1))
            screen.refresh()
            try:
                key = screen.getch()
            except KeyboardInterrupt:
                if _confirm_exit(screen):
                    return
                messages.append("exit cancelled")
                continue
            if key in (ord("q"), 27):
                if _confirm_exit(screen):
                    return
                messages.append("exit cancelled")
                continue
            if key in (curses.KEY_DOWN, ord("j")):
                selected = min(max(0, len(items) - 1), selected + 1)
                detail_offset = 0
            elif key in (curses.KEY_UP, ord("k")):
                selected = max(0, selected - 1)
                detail_offset = 0
            elif key == ord("]"):
                detail_offset = min(max(0, len(detail_lines) - detail_page_size), detail_offset + detail_page_size)
            elif key == ord("["):
                detail_offset = max(0, detail_offset - detail_page_size)
            elif key == ord("x") and items:
                if selected in marked:
                    marked.remove(selected)
                else:
                    marked.add(selected)
            elif key == ord("d") and items:
                if items[selected].get("kind") == "external-review":
                    packet = resolve_packet(repo, str(items[selected]["target"]))
                    if packet is None:
                        _missing_packet(screen, repo, str(items[selected]["target"]))
                    else:
                        _pager(screen, packet_detail_lines(packet))
                else:
                    _pager(screen, detail_lines)
            elif key in (ord("a"), ord("A")) and items:
                chosen = [items[i] for i in sorted(marked)] if key == ord("A") and marked else [items[selected]]
                if key == ord("A") and len({str(item.get("kind")) for item in chosen}) != 1:
                    messages.append("bulk action requires one kind")
                    continue
                options = actions_for(chosen[0])
                action = _action_prompt(screen, options)
                if not action:
                    messages.append("action input cancelled")
                    continue
                if action not in options:
                    messages.append("action unavailable")
                    continue
                if len(chosen) > 1 and action == "establish":
                    if _prompt(screen, f"establish {len(chosen)} entries? [y/N] ").casefold() != "y":
                        continue
                if action == "review":
                    response = human_review_wizard(screen, repo, str(chosen[0]["target"]))
                    messages.append("review response saved" if response else "review response cancelled")
                    marked.clear()
                    continue
                value = _prompt(screen, "reason/note (empty cancels): ") if action in {"reject", "fail"} else ""
                result = execute(repo, chosen, action, run_id, value)
                if result.get("request"):
                    _pager(screen, str(result["request"]).splitlines() or ["(empty request)"])
                    messages.append("request generated")
                    marked.clear()
                    continue
                messages.append(json_result(result))
                marked.clear()

    curses.wrapper(main)


def json_result(value: dict[str, Any]) -> str:
    if value.get("ok"):
        return "ok: " + (str(value.get("choice") or value.get("outcome") or value.get("action") or "completed"))
    return "failed: " + str(value.get("error") or "unknown error")
