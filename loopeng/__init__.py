from __future__ import annotations

from pathlib import Path


def version() -> str:
    root = Path(__file__).resolve().parents[1]
    return root.joinpath("VERSION").read_text(encoding="utf-8").strip()

