from __future__ import annotations

from pathlib import Path
from typing import Any

from .events import NormalizedEvent, event_kind


def normalize(payload: dict[str, Any], *, repo: Path | None = None) -> NormalizedEvent:
    """Convert Claude Code's hook JSON into the shared event model.

    Claude Code lifecycle names intentionally follow the v0.1 contract:
    ``UserPromptSubmit``, ``PreToolUse``, ``PostToolUse`` and ``Stop``.
    """
    cwd = Path(str(payload.get("cwd") or repo or Path.cwd())).resolve()
    return NormalizedEvent(event_kind(payload.get("hook_event_name") or payload.get("event")), "claude-code", cwd, dict(payload))


def render(result: dict[str, Any], event: NormalizedEvent) -> dict[str, Any]:
    output = dict(result.get("response") or {})
    specific = output.setdefault("hookSpecificOutput", {})
    specific.setdefault("hookEventName", event.event_name)
    return output
