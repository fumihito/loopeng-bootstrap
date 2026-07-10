from __future__ import annotations

from pathlib import Path


def reindex_bundle(bundle: Path) -> None:
    bundle.mkdir(parents=True, exist_ok=True)
    for directory in sorted([path for path in bundle.rglob("*") if path.is_dir()]):
        index = directory / "index.md"
        entries = sorted(
            [path for path in directory.iterdir() if path.name != "index.md"],
            key=lambda path: (path.is_file(), path.name),
        )
        lines = [f"# {directory.relative_to(bundle).as_posix() or 'llmwiki'}", ""]
        for entry in entries:
            if entry.is_dir():
                lines.append(f"- [{entry.name}]({entry.name}/index.md)")
            elif entry.suffix == ".md":
                lines.append(f"- [{entry.stem}]({entry.name})")
            else:
                lines.append(f"- {entry.relative_to(bundle).as_posix()}")
        index.write_text("\n".join(lines).rstrip() + "\n", encoding="utf-8")
    root_index = bundle / "index.md"
    if not root_index.exists():
        root_index.write_text("# llmwiki\n\n- [log](log.md)\n", encoding="utf-8")
    log = bundle / "log.md"
    if not log.exists():
        log.write_text("# log\n\n", encoding="utf-8")

