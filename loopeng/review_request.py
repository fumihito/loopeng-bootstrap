from __future__ import annotations

import json
from pathlib import Path

from ._paths import agent_root
from .review_contract import CONTRACT_VERSION, REVIEW_DIMENSIONS


def build_request(repo: Path, run_id: str) -> str:
    root = repo.resolve() / agent_root("state", "review-packets") / run_id
    manifest = root / "manifest.json"
    packet_hash = "unknown"
    if manifest.is_file():
        try:
            value = json.loads(manifest.read_text(encoding="utf-8"))
            packet_hash = str(value.get("packet_hash", packet_hash))
        except (OSError, json.JSONDecodeError):
            pass
    return (f"Review packet: {root}\n"
            f"Contract: v{CONTRACT_VERSION}; packet_hash={packet_hash}\n"
            "Reviewer skill: frame-loop-audit-review\n"
            f"Required dimensions: {', '.join(REVIEW_DIMENSIONS)}\n"
            "Submit contract JSON only, then return it to loopeng review intake.\n")
