from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path
from typing import Any


def input_paths(tool_input: Any) -> list[str]:
    """Extract platform-neutral path fields without making policy decisions."""
    if not isinstance(tool_input, dict):
        return []
    paths: list[str] = []
    for key in ("path", "file_path", "filename", "target", "destination"):
        value = tool_input.get(key)
        if isinstance(value, str):
            paths.append(value)
    return paths


class EventKind(StrEnum):
    SESSION_START = "SESSION_START"
    PROMPT_SUBMIT = "PROMPT_SUBMIT"
    PRE_TOOL = "PRE_TOOL"
    POST_TOOL = "POST_TOOL"
    RUN_STOP = "RUN_STOP"
    OTHER = "OTHER"


@dataclass(frozen=True)
class NormalizedEvent:
    """Platform-neutral lifecycle event.

    ``payload`` is retained only as adapter input.  Policy decisions belong to
    ``handler.py``; platform modules only construct this value and render the
    resulting response.
    """

    kind: EventKind
    platform: str
    repo: Path
    payload: dict[str, Any] = field(default_factory=dict)

    @property
    def run_id(self) -> str | None:
        value = self.payload.get("run_id") or self.payload.get("turn_id")
        return str(value) if value else None

    @property
    def event_name(self) -> str:
        return str(self.payload.get("hook_event_name") or self.payload.get("event") or self.kind.value)


def event_kind(name: str | None) -> EventKind:
    normalized = str(name or "").strip().lower()
    return {
        "sessionstart": EventKind.SESSION_START,
        "session_start": EventKind.SESSION_START,
        "userpromptsubmit": EventKind.PROMPT_SUBMIT,
        "prompt_submit": EventKind.PROMPT_SUBMIT,
        "pretooluse": EventKind.PRE_TOOL,
        "pre_tool": EventKind.PRE_TOOL,
        "posttooluse": EventKind.POST_TOOL,
        "post_tool": EventKind.POST_TOOL,
        "stop": EventKind.RUN_STOP,
        "run_stop": EventKind.RUN_STOP,
    }.get(normalized, EventKind.OTHER)
