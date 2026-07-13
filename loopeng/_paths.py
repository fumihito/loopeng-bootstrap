from __future__ import annotations

from pathlib import Path


DOT_AGENT = "." + "agent-loop"
WIKI_SPACE_MARKERS = ("loopeng/__main__.py", "install.py", "utils/phase1_gate.py")


def agent_root(*parts: str) -> Path:
    return Path(DOT_AGENT, *parts)


def wiki_space(repo: Path) -> tuple[str, Path]:
    """Return the semantic wiki space and its repository-local bundle."""
    repo = repo.resolve()
    kind = "framework" if all((repo / marker).is_file() for marker in WIKI_SPACE_MARKERS) else "project"
    return kind, repo / "llmwiki"
