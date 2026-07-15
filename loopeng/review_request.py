from __future__ import annotations

import json
import secrets
from pathlib import Path

from ._paths import agent_root
from .journal import EVENT_REVIEW, append_event
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
    d5_target = "unknown"
    if root is not None:
        try:
            value = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
            packet_hash = str(value.get("packet_hash", packet_hash))
            candidates = value.get("implemented_requirements")
            if not isinstance(candidates, list) or not candidates:
                index = json.loads((root / "source-index.json").read_text(encoding="utf-8"))
                candidates = [f"file:{name}:1" for name, lines in sorted(index.items()) if int(lines) > 0]
            if candidates:
                d5_target = str(secrets.choice(candidates))
                value["d5_target"] = d5_target
                (root / "manifest.json").write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
                append_event(repo, run_id, {"kind": EVENT_REVIEW, "run_id": run_id, "d5_target": d5_target, "authorization": "request-generated"})
        except (OSError, json.JSONDecodeError):
            pass
    packet_line = (f"Review packet manifest: {root / 'manifest.json'}\n" if root is not None else
                   f"Review packet: unavailable for run {run_id}\n"
                   f"Generate it with: python3 -m loopeng audit export --run {run_id}\n")
    return (packet_line +
            f"Contract: v{CONTRACT_VERSION}; packet_hash={packet_hash}\n"
            "Reviewer skill: frame-loop-audit-review\n"
            f"Required dimensions: {', '.join(REVIEW_DIMENSIONS)}\n"
            f"D5 target (must be inspected exactly): {d5_target}\n"
            "Use a new session. Do not bring context from the implementation session. Record a new session identifier in reviewer.session.\n"
            "Submit contract JSON only, then return it to loopeng review intake.\n"
            f"Incoming drop-off: {incoming}\n"
            "Save the contract JSON in this directory.\n")
