from __future__ import annotations

import json
from pathlib import Path

from ._paths import agent_root


def build_next_turn_prompt(repo: Path) -> str:
    handoff = repo / agent_root("state", "handoff.json")
    if not handoff.is_file():
        return "No handoff available.\n"
    data = json.loads(handoff.read_text(encoding="utf-8"))
    lines = ["Next turn handoff", ""]
    for key in ("source_turn_id", "goal", "summary", "notes"):
        value = data.get(key)
        if value:
            lines.append(f"{key}: {value}")
    lines.append("")
    return "\n".join(lines)

