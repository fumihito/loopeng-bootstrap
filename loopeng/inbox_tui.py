"""Curses-only presentation for the inbox model."""

from __future__ import annotations

import curses
from pathlib import Path
from typing import Any

from .inbox_model import actions_for, detail, execute, generate_packet, list_items, packet_detail_lines
from .review_request import resolve_packet


def _short(value: str, width: int) -> str:
    if len(value) <= width:
        return value
    return value[:max(1, width - 1)] + "…"


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
    curses.echo()
    value = screen.getstr(max(0, height - 1), 0).decode(errors="replace")
    curses.noecho()
    return value


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
    curses.noecho()
    try:
        while True:
            screen.move(max(0, height - 2), 0)
            screen.clrtoeol()
            screen.addnstr(max(0, height - 2), 0, f"action {options}: {value}", max(1, width - 1))
            screen.refresh()
            key = screen.getch()
            if key in (curses.KEY_ENTER, 10, 13):
                return value
            if key in (27,):
                return ""
            if key in (curses.KEY_BACKSPACE, 8, 127):
                value = value[:-1]
                completion_index = -1
            elif key in (9,):
                value, completion_index = _next_completion(value, options, completion_index)
            elif 0 <= key < 256:
                value += chr(key)
                completion_index = -1
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
        screen.addnstr(2, 0, "[e] generate packet with audit export  [q] back", max(1, width - 1))
        screen.refresh()
        key = screen.getch()
        if key in (ord("q"), 27):
            return
        if key == ord("e"):
            try:
                packet = generate_packet(repo, run_id)
                _pager(screen, packet_detail_lines(packet))
            except (OSError, RuntimeError, ValueError) as exc:
                screen.addnstr(max(4, height - 2), 0, _short(f"export failed: {type(exc).__name__}", max(1, width - 1)), max(1, width - 1))
                screen.refresh()
                screen.getch()
            return


def run(repo: Path, run_id: str) -> None:
    def main(screen: Any) -> None:
        curses.curs_set(0)
        selected = 0
        marked: set[int] = set()
        messages: list[str] = []
        detail_lines: list[str] = []
        while True:
            items = list_items(repo)
            screen.erase()
            height, width = screen.getmaxyx()
            screen.addnstr(0, 0, f"Inbox ({len(items)})  [x]=mark [a]=act [d]=detail [A]=act-all-marked [q]=quit", max(1, width - 1))
            list_limit = max(0, height - 6) if not detail_lines else max(0, height - min(len(detail_lines), 8) - 6)
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
                detail_start = max(0, height - min(len(detail_lines), 8) - 3)
                screen.addnstr(max(0, detail_start - 1), 0, "Detail (d to refresh):", max(1, width - 1))
                for offset, line in enumerate(detail_lines[-8:]):
                    screen.addnstr(detail_start + offset, 0, _short(line, max(1, width - 1)), max(1, width - 1))
            if messages:
                screen.addnstr(max(0, height - 2), 0, _short(messages[-1], max(1, width - 1)), max(1, width - 1))
            screen.refresh()
            key = screen.getch()
            if key in (ord("q"), 27):
                return
            if key in (curses.KEY_DOWN, ord("j")):
                selected = min(max(0, len(items) - 1), selected + 1)
            elif key in (curses.KEY_UP, ord("k")):
                selected = max(0, selected - 1)
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
                    detail_lines = detail(repo, items[selected]).splitlines()[:20] or ["(empty detail)"]
                    messages.append(f"showing {len(detail_lines)} detail lines")
            elif key in (ord("a"), ord("A")) and items:
                chosen = [items[i] for i in sorted(marked)] if key == ord("A") and marked else [items[selected]]
                if key == ord("A") and len({str(item.get("kind")) for item in chosen}) != 1:
                    messages.append("bulk action requires one kind")
                    continue
                options = actions_for(chosen[0])
                action = _action_prompt(screen, options)
                if action not in options:
                    messages.append("action unavailable")
                    continue
                if len(chosen) > 1 and action == "establish":
                    if _prompt(screen, f"establish {len(chosen)} entries? [y/N] ").casefold() != "y":
                        continue
                value = _prompt(screen, "reason/note (empty cancels): ") if action in {"reject", "fail"} else ""
                result = execute(repo, chosen, action, run_id, value)
                messages.append(json_result(result))
                marked.clear()

    curses.wrapper(main)


def json_result(value: dict[str, Any]) -> str:
    if value.get("ok"):
        return "ok: " + (str(value.get("choice") or value.get("outcome") or value.get("action") or "completed"))
    return "failed: " + str(value.get("error") or "unknown error")
