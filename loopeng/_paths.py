from __future__ import annotations

from pathlib import Path


DOT_AGENT = "." + "agent-loop"


def agent_root(*parts: str) -> Path:
    return Path(DOT_AGENT, *parts)

