#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass
from pathlib import Path


REQUIRED_FRONTMATTER_KEYS = ("name", "description", "user-invocable")
REQUIRED_SECTIONS = ("Purpose", "When to use", "Workflow", "Output", "Exit", "Adjacent frames")
FRONTMATTER_RE = re.compile(r"^---\n(?P<body>.*?)\n---\n", re.S)
SECTION_RE = re.compile(r"^##\s+(?P<title>.+?)\s*$", re.M)
WORD_RE = re.compile(r"[A-Za-z0-9]+(?:[-'][A-Za-z0-9]+)*")
FRAME_REF_RE = re.compile(r"\bframe-[A-Za-z0-9-]+\b")
SKILL_MD_REF_RE = re.compile(r"(?<![A-Za-z0-9_/.-])(?P<path>(?:\./)?(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.md)\b")
IGNORED_MD_NAMES = {"SKILL.md", "routing.md"}


@dataclass(frozen=True)
class SkillFinding:
    path: Path
    message: str


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lint frame skill structure under adapters/shared/skills.")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root to scan.")
    return parser.parse_args(argv)


def iter_frame_skill_paths(root: Path) -> list[Path]:
    base = root / "adapters/shared/skills"
    if not base.exists():
        return []
    return [
        path
        for path in sorted(base.glob("frame-*/SKILL.md"))
        if path.is_file() and not path.is_symlink()
    ]


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    match = FRONTMATTER_RE.match(text)
    if not match:
        raise ValueError("missing or malformed frontmatter block")
    frontmatter: dict[str, str] = {}
    for raw_line in match.group("body").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if ":" not in line:
            raise ValueError(f"invalid frontmatter line: {raw_line}")
        key, value = line.split(":", 1)
        frontmatter[key.strip()] = value.strip().strip('"\'')
    return frontmatter, text[match.end():]


def section_titles(text: str) -> list[str]:
    return [match.group("title").strip() for match in SECTION_RE.finditer(text)]


def description_word_count(description: str) -> int:
    return len(WORD_RE.findall(description))


def iter_skill_markdown_files(skill_dir: Path) -> list[Path]:
    return [
        path
        for path in sorted(skill_dir.rglob("*.md"))
        if path.is_file() and path.name not in IGNORED_MD_NAMES and not path.is_symlink()
    ]


def referenced_skill_markdown_paths(skill_dir: Path, body: str) -> set[Path]:
    refs: set[Path] = set()
    for match in SKILL_MD_REF_RE.finditer(body):
        rel_text = match.group("path")
        candidate = (skill_dir / rel_text).resolve()
        try:
            rel = candidate.relative_to(skill_dir.resolve())
        except ValueError:
            continue
        if rel.name in IGNORED_MD_NAMES:
            continue
        refs.add(skill_dir / rel)
    return refs


def validate_bundle_markdown(skill_dir: Path, body: str) -> list[str]:
    """直後により深い階層の見出し(### 以下)が続く親見出しは空とみなさない。"""
    errors: list[str] = []
    bundled_files = iter_skill_markdown_files(skill_dir)
    referenced_files = referenced_skill_markdown_paths(skill_dir, body)

    for path in bundled_files:
        if path not in referenced_files:
            errors.append(f"unreferenced bundled markdown: {path.relative_to(skill_dir)}")

    for path in sorted(referenced_files):
        if not path.exists():
            errors.append(f"broken bundled markdown reference: {path.relative_to(skill_dir)}")

    return errors


def validate_skill(path: Path) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    try:
        frontmatter, body = parse_frontmatter(text)
    except ValueError as exc:
        return [str(exc)]

    missing_keys = [key for key in REQUIRED_FRONTMATTER_KEYS if key not in frontmatter]
    if missing_keys:
        errors.append(f"missing frontmatter key(s): {', '.join(missing_keys)}")

    name = frontmatter.get("name", "")
    expected_name = path.parent.name
    if name != expected_name:
        errors.append(f"frontmatter name must match directory name {expected_name}")

    user_invocable = frontmatter.get("user-invocable")
    if user_invocable != "true":
        errors.append("frontmatter user-invocable must be true")

    description = frontmatter.get("description", "")
    if description_word_count(description) > 40:
        errors.append("description must not exceed 40 words")
    if FRAME_REF_RE.search(description):
        errors.append("description must not reference frame-* names")

    titles = section_titles(body)
    for section in REQUIRED_SECTIONS:
        if section not in titles:
            errors.append(f"missing required section: {section}")

    errors.extend(validate_bundle_markdown(path.parent, body))

    return errors


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    if not root.exists() or not root.is_dir():
        print(f"ERROR: root does not exist or is not a directory: {root}", file=sys.stderr)
        return 2

    findings: list[SkillFinding] = []
    for path in iter_frame_skill_paths(root):
        for message in validate_skill(path):
            findings.append(SkillFinding(path.relative_to(root), message))

    if findings:
        print(f"Found {len(findings)} skill structure issue(s) under {root}:")
        for finding in findings:
            print(f"ERROR: {finding.path}: {finding.message}")
        return 1

    print(f"OK: all frame skill files passed structure lint under {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
