from __future__ import annotations

from pathlib import Path
from typing import Any

from .events import NormalizedEvent, event_kind


def normalize(payload: dict[str, Any], *, repo: Path | None = None) -> NormalizedEvent:
    """Convert current Codex lifecycle hook JSON into the shared event model.

    Source: OpenAI Codex Hooks documentation, current release reference
    (``https://learn.chatgpt.com/docs/hooks``, accessed 2026-07-12).  The
    documented fields used here are ``hook_event_name``, ``cwd``, ``session_id``,
    ``turn_id``, ``tool_name``, ``tool_input`` and ``tool_response``.  This
    adapter deliberately does not infer undocumented event or output fields.
    """
    cwd = Path(str(payload.get("cwd") or repo or Path.cwd())).resolve()
    return NormalizedEvent(event_kind(payload.get("hook_event_name") or payload.get("event")), "codex", cwd, dict(payload))


def render(result: dict[str, Any], event: NormalizedEvent) -> dict[str, Any]:
    output = dict(result.get("response") or {})
    specific = output.setdefault("hookSpecificOutput", {})
    specific.setdefault("hookEventName", event.event_name)
    return output
