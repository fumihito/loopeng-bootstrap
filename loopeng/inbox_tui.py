"""Curses-only presentation for the inbox model."""

from __future__ import annotations

import curses
from pathlib import Path
from typing import Any

from .inbox_model import actions_for, detail, execute, list_items


def _short(value: str, width: int) -> str:
    if len(value) <= width:
        return value
    return value[:max(1, width - 1)] + "…"


def _prompt(screen: Any, text: str) -> str:
    height, width = screen.getmaxyx()
    screen.move(max(0, height - 2), 0)
    screen.clrtoeol()
    screen.addnstr(max(0, height - 2), 0, text, max(1, width - 1))
    curses.echo()
    value = screen.getstr(max(0, height - 1), 0).decode(errors="replace")
    curses.noecho()
    return value


def run(repo: Path, run_id: str) -> None:
    def main(screen: Any) -> None:
        curses.curs_set(0)
        selected = 0
        marked: set[int] = set()
        messages: list[str] = []
        while True:
            items = list_items(repo)
            screen.erase()
            height, width = screen.getmaxyx()
            screen.addnstr(0, 0, f"Inbox ({len(items)})  [space]=mark [a]=act [d]=detail [A]=act-all-marked [q]=quit", max(1, width - 1))
            for index, item in enumerate(items[:max(0, height - 6)]):
                prefix = ">" if index == selected else " "
                mark = "x" if index in marked else " "
                target = _short(str(item.get("target", "")), max(10, width - 36))
                line = f"{prefix} [{mark}] {item.get('kind', ''):<16} {target:<{max(10, width - 36)}} {float(item.get('age_days', 0)):.1f}d"
                screen.addnstr(index + 2, 0, line, max(1, width - 1))
            screen.hline(max(2, height - 4), 0, curses.ACS_HLINE, max(1, width - 1))
            kinds = {str(items[i].get("kind")) for i in marked if i < len(items)}
            available = ",".join(actions_for(items[i]) for i in marked if i < len(items)) if len(kinds) == 1 else "mixed/none"
            screen.addnstr(max(0, height - 3), 0, f"marked: {len(marked)}  available: {available}", max(1, width - 1))
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
            elif key == ord(" ") and items:
                if selected in marked:
                    marked.remove(selected)
                else:
                    marked.add(selected)
            elif key == ord("d") and items:
                messages.append(detail(repo, items[selected]).splitlines()[0] if detail(repo, items[selected]) else "(empty detail)")
            elif key in (ord("a"), ord("A")) and items:
                chosen = [items[i] for i in sorted(marked)] if key == ord("A") and marked else [items[selected]]
                if key == ord("A") and len({str(item.get("kind")) for item in chosen}) != 1:
                    messages.append("bulk action requires one kind")
                    continue
                options = actions_for(chosen[0])
                action = _prompt(screen, f"action {options}: ")
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
