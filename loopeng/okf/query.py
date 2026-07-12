from __future__ import annotations

from pathlib import Path
from typing import Any

from .schema import parse_document


def query_bundle(bundle: Path, type_name: str | None = None, tags: list[str] | None = None,
                 grep: str | None = None, status: str = "active", limit: int = 10) -> list[dict[str, Any]]:
    tags = tags or []
    needle = grep.casefold() if grep else None
    results: list[dict[str, Any]] = []
    for path in sorted(bundle.rglob("*.md")):
        if path.name == "index.md" or path.name == "log.md":
            continue
        try:
            frontmatter, body = parse_document(path)
        except (OSError, UnicodeError):
            continue
        if not frontmatter:
            continue
        actual_status = str(frontmatter.get("status") or "active")
        if status != "all" and actual_status != status:
            continue
        if type_name is not None and frontmatter.get("type") != type_name:
            continue
        actual_tags = frontmatter.get("tags") if isinstance(frontmatter.get("tags"), list) else []
        if any(tag not in actual_tags for tag in tags):
            continue
        if needle and needle not in (" ".join(f"{key} {value}" for key, value in frontmatter.items()) + "\n" + body).casefold():
            continue
        results.append({
            "concept_id": path.relative_to(bundle).with_suffix("").as_posix(),
            "type": frontmatter.get("type"),
            "title": frontmatter.get("title", ""),
            "description": frontmatter.get("description", ""),
            "tags": actual_tags,
        })
    return results
