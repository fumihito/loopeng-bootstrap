#!/usr/bin/env python3
"""Deterministically check documentation parity with the executable surface.

This lint intentionally checks mechanically extracted names and paths only. It
does not compare the meaning of prose with the implementation.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


MODE_WORD_RE = re.compile(r"(?<![\w-])([a-z][a-z0-9-]*:)(?![/\w-])")
PATH_RE = re.compile(r"`((?:docs|utils|loopeng)/[^`\s]+)`")
ONGOING_RE = re.compile(r"<!-- ongoing-start -->\s*(.*?)\s*<!-- ongoing-end -->", re.S | re.I)

# Historical documents preserve the paths that existed at the time they were
# written. They are evidence, not current documentation parity targets.
HISTORICAL_DOC_ROOT = "docs/v0.2-phase1"
RETIRED_PATHS = (
    ".agent-loop/hooks",
    ".agent-loop/lib",
    ".agent-loop/bin",
    ".agent-loop/cmd",
    ".agent-loop/systemd",
    ".agent-loop/otel.json",
    ".agent-loop/otel-collector.yaml",
    ".agent-loop/policy.json",
    ".agent-loop/*-policy.json",
    "routing_hints.py",
    "TELEMETRY_SCHEMA.md",
    "systemd",
    "templates/LOOP_BRIEF.md",
    "templates/OKF_LOOP_BRIEF_PATTERN.md",
    "skills/gatekeeper",
    "skills/sensemaker",
    "skills/command-route",
    "adapters/shared/skills/gatekeeper",
)


def _parser_surface() -> tuple[list[str], list[str]]:
    from loopeng.cli import build_parser

    parser = build_parser()
    actions = next(action for action in parser._actions if action.dest == "command")
    commands = sorted(str(name) for name in actions.choices)
    review = actions.choices["review"]
    view_action = next(action for action in review._actions if action.dest == "review_view")
    views = sorted(str(name) for name in (view_action.choices or {}))
    return commands, views


def _mode_words(root: Path) -> list[str]:
    words: set[str] = set()
    for name in ("AGENTS.md", "CLAUDE.md"):
        text = (root / name).read_text(encoding="utf-8")
        words.update(MODE_WORD_RE.findall(text))
    return sorted(words)


def _hook_platforms(root: Path) -> list[str]:
    platforms: list[str] = []
    if (root / "loopeng/hooks/claude_code.py").is_file():
        platforms.append("Claude Code")
    if (root / "loopeng/hooks/codex.py").is_file():
        platforms.append("Codex")
    return platforms


def _docs(root: Path, paths: list[str]) -> dict[str, str]:
    result: dict[str, str] = {}
    for rel in paths:
        path = root / rel
        if not path.is_file():
            result[rel] = ""
        else:
            result[rel] = path.read_text(encoding="utf-8")
    return result


def _record(errors: list[str], check: str, rel: str, token: str) -> None:
    errors.append(f"{check}: {rel}: missing {token!r}")


def _implemented_features(root: Path, commands: list[str]) -> list[str]:
    """Return command forms that can be named as an implemented feature."""
    from loopeng.cli import build_parser

    parser = build_parser()
    action = next(item for item in parser._actions if item.dest == "command")
    features: list[str] = []
    for command in commands:
        subparser = action.choices[command]
        nested = next((item for item in subparser._actions if item.dest.endswith("_command")), None)
        if nested is None:
            features.append(command)
        else:
            features.extend(f"{command} {child}" for child in sorted(nested.choices))
    return features


def _path_exists(root: Path, reference: str) -> bool:
    reference = re.sub(r":\d+(?:-\d+)?$", "", reference.rstrip(".,:;)"))
    path = root / reference
    if "*" in reference or "?" in reference or "[" in reference:
        return any(root.glob(reference))
    return path.exists()


def lint(root: Path) -> list[str]:
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    errors: list[str] = []
    map_path = root / "docs/doc-map.json"
    if not map_path.is_file():
        return ["1 cli surface: docs/doc-map.json: missing mapping"]
    try:
        doc_map = json.loads(map_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"1 cli surface: docs/doc-map.json: invalid mapping ({exc})"]

    commands, views = _parser_surface()
    # 1. CLI surface and review views.
    cli_docs = _docs(root, list(doc_map.get("cli_subcommands", [])))
    for rel, body in cli_docs.items():
        for command in commands:
            if command not in body:
                _record(errors, "1 cli surface", rel, command)
    view_docs = _docs(root, list(doc_map.get("review_views", [])))
    for rel, body in view_docs.items():
        for view in views:
            if view not in body:
                _record(errors, "1 review view", rel, view)
    hook_docs = _docs(root, list(doc_map.get("hook_platforms", [])))
    for rel, body in hook_docs.items():
        for platform in _hook_platforms(root):
            if platform not in body:
                _record(errors, "1 hook platform", rel, platform)

    # 2. Event contract.
    from loopeng.journal import EVENT_KINDS

    for rel, body in _docs(root, list(doc_map.get("event_kinds", []))).items():
        for kind in EVENT_KINDS:
            if kind not in body:
                _record(errors, "2 event contract", rel, kind)

    # 3. Ongoing status must not list an already implemented CLI feature.
    implemented = _implemented_features(root, commands)
    for rel in ("README.md", "README.ja.md"):
        body = (root / rel).read_text(encoding="utf-8") if (root / rel).is_file() else ""
        matches = ONGOING_RE.findall(body)
        if not matches:
            errors.append(f"3 ongoing status: {rel}: missing ongoing markers")
            continue
        ongoing = "\n".join(matches)
        for command in sorted(implemented):
            if re.search(rf"(?<![\w-]){re.escape(command)}(?::|\b)", ongoing, re.I):
                _record(errors, "3 ongoing status", rel, command)

    # 4. Every explicit repository path in the documented surfaces exists.
    doc_paths = ["README.md", "README.ja.md"] + sorted(
        path.relative_to(root).as_posix()
        for path in (root / "docs").glob("*.md")
        if HISTORICAL_DOC_ROOT not in path.relative_to(root).as_posix()
        and path.name != "audit-log.md"
    )
    for rel in doc_paths:
        path = root / rel
        if not path.is_file():
            continue
        for referenced in PATH_RE.findall(path.read_text(encoding="utf-8")):
            if not _path_exists(root, referenced):
                _record(errors, "4 reference path", rel, referenced)

    # 6. Retired v0.1 material must not silently reappear in a merge.
    for retired in RETIRED_PATHS:
        if _path_exists(root, retired):
            errors.append(f"6 retired path: <tree>: present {retired!r}")

    # 5. Executable tokens and mode words are present in both README bodies.
    readmes = _docs(root, ["README.md", "README.ja.md"])
    tokens = commands + views + _mode_words(root)
    for rel, body in readmes.items():
        for token in tokens:
            if token not in body:
                _record(errors, "5 en-ja parity", rel, token)
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check executable/documentation parity.")
    parser.add_argument("--root", type=Path, default=Path.cwd())
    args = parser.parse_args(argv)
    errors = lint(args.root.resolve())
    if errors:
        print("doc parity lint: FAIL")
        print("\n".join(errors))
        return 1
    print("doc parity lint: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
