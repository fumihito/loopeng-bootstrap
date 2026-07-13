from __future__ import annotations

import json
from pathlib import Path

from ._paths import agent_root
from .review_contract import CONTRACT_VERSION, REVIEW_DIMENSIONS


def resolve_packet(repo: Path, run_id: str) -> Path | None:
    root = repo.resolve() / agent_root("state", "review-packets")
    exact = root / run_id
    if (exact / "manifest.json").is_file():
        return exact
    if not root.is_dir():
        return None
    for candidate in sorted(path for path in root.iterdir() if path.is_dir()):
        manifest = candidate / "manifest.json"
        try:
            value = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(value, dict) and str(value.get("run_id")) == run_id:
            return candidate
    return None


def build_request(repo: Path, run_id: str) -> str:
    incoming = repo.resolve() / agent_root("state", "reviews", "incoming")
    incoming.mkdir(parents=True, exist_ok=True)
    root = resolve_packet(repo, run_id)
    packet_hash = "unknown"
    if root is not None:
        try:
            value = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
            packet_hash = str(value.get("packet_hash", packet_hash))
        except (OSError, json.JSONDecodeError):
            pass
    packet_line = (f"Review packet manifest: {root / 'manifest.json'}\n" if root is not None else
                   f"Review packet: unavailable for run {run_id}\n"
                   f"Generate it with: python3 -m loopeng audit export --run {run_id}\n")
    return (packet_line +
            f"Contract: v{CONTRACT_VERSION}; packet_hash={packet_hash}\n"
            "Reviewer skill: frame-loop-audit-review\n"
            f"Required dimensions: {', '.join(REVIEW_DIMENSIONS)}\n"
            "Submit contract JSON only, then return it to loopeng review intake.\n"
            f"Incoming drop-off: {incoming}\n"
            "Save the contract JSON in this directory.\n")
