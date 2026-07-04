#!/usr/bin/env python3
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from routing_hints import load_routing_hints, validate_routing_hints_document

JAPANESE_RE = re.compile(r"[ぁ-んァ-ヶ一-龯]")
CLUSTERS: dict[str, tuple[str, ...]] = {
    "incident": (
        "frame-distributed-incident-analysis",
        "frame-diag",
        "frame-waiwad-grill",
    ),
    "research": (
        "frame-research",
        "frame-research-tactics",
        "frame-experiments",
        "frame-research-arch",
    ),
    "planning": (
        "frame-plandev",
        "frame-plantask",
        "frame-smeac",
    ),
    "thinking-check": (
        "frame-first-principles",
        "frame-critical-review",
        "frame-blind-spot",
        "frame-inertia",
    ),
    "independent": (
        "frame-cynefin",
        "frame-proofread-ja",
    ),
}
PAIR_RULES: dict[str, tuple[tuple[str, str], ...]] = {
    "incident": (
        ("frame-distributed-incident-analysis", "frame-diag"),
        ("frame-diag", "frame-waiwad-grill"),
    ),
    "research": (
        ("frame-research", "frame-research-tactics"),
        ("frame-research-tactics", "frame-experiments"),
        ("frame-research", "frame-research-arch"),
    ),
    "planning": (
        ("frame-plandev", "frame-plantask"),
        ("frame-plandev", "frame-smeac"),
        ("frame-plantask", "frame-smeac"),
    ),
    "thinking-check": (
        ("frame-first-principles", "frame-critical-review"),
        ("frame-critical-review", "frame-blind-spot"),
        ("frame-blind-spot", "frame-inertia"),
    ),
    "independent": (),
}
FRAME_TO_CLUSTER: dict[str, str] = {
    frame: cluster
    for cluster, frames in CLUSTERS.items()
    for frame in frames
}


def normalize(text: str) -> str:
    return " ".join(text.strip().lower().split())


def entry_terms(entry) -> set[str]:
    return {normalize(entry.phrase), *(normalize(alias) for alias in entry.aliases)}


def document_terms(document, sections: tuple[str, ...]) -> set[str]:
    terms: set[str] = set()
    for section in sections:
        for entry in document.sections.get(section, ()):
            terms.update(entry_terms(entry))
    return terms


def contains_japanese(text: str) -> bool:
    return bool(JAPANESE_RE.search(text))


def iter_routing_files(root: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(root.rglob("routing.md")):
        if not path.is_file():
            continue
        if ".git" in path.relative_to(root).parts:
            continue
        files.append(path)
    return files


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lint routing.md files using the routing-hints/v1 format.")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Repository root to scan.")
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    root = args.root.resolve()
    if not root.exists() or not root.is_dir():
        print(f"ERROR: root does not exist or is not a directory: {root}", file=sys.stderr)
        return 2

    findings: list[str] = []
    warnings: list[str] = []
    docs_by_frame: dict[str, tuple[Path, object]] = {}
    for path in iter_routing_files(root):
        rel = path.relative_to(root)
        try:
            doc = load_routing_hints(path)
            errors = validate_routing_hints_document(doc, expected_frame=path.parent.name)
        except Exception as exc:
            findings.append(f"ERROR: {rel}: {type(exc).__name__}: {exc}")
            continue
        if errors:
            findings.extend(f"ERROR: {rel}: {message}" for message in errors)
        docs_by_frame[doc.frame] = (path, doc)

    for cluster_name, frames in CLUSTERS.items():
        cluster_docs = {
            frame: docs_by_frame[frame]
            for frame in frames
            if frame in docs_by_frame
        }
        if not cluster_docs:
            continue

        prefer_terms: dict[str, set[str]] = {
            frame: document_terms(doc, ("prefer",))
            for frame, (_, doc) in cluster_docs.items()
        }
        avoid_terms: dict[str, set[str]] = {
            frame: document_terms(doc, ("avoid", "bad_for"))
            for frame, (_, doc) in cluster_docs.items()
        }

        seen_terms: dict[str, str] = {}
        for frame, (_, doc) in cluster_docs.items():
            for term in prefer_terms[frame]:
                if term in seen_terms and seen_terms[term] != frame:
                    findings.append(
                        f"ERROR: cluster {cluster_name}: prefer term '{term}' collides between {seen_terms[term]} and {frame}"
                    )
                else:
                    seen_terms[term] = frame

        for left, right in PAIR_RULES[cluster_name]:
            left_doc = cluster_docs.get(left)
            right_doc = cluster_docs.get(right)
            if left_doc is None or right_doc is None:
                continue
            left_prefer = prefer_terms[left]
            right_prefer = prefer_terms[right]
            left_avoid = avoid_terms[left]
            right_avoid = avoid_terms[right]
            if not left_prefer & right_avoid:
                findings.append(
                    f"ERROR: cluster {cluster_name}: {left} must avoid one of {right}'s preferred terms"
                )
            if not right_prefer & left_avoid:
                findings.append(
                    f"ERROR: cluster {cluster_name}: {right} must avoid one of {left}'s preferred terms"
                )

        for frame, (path, doc) in cluster_docs.items():
            rel = path.relative_to(root)
            has_japanese = any(
                contains_japanese(text)
                for entry in (*doc.sections.get("prefer", ()), *doc.sections.get("signals", ()))
                for text in (entry.phrase, *entry.aliases)
            )
            if not has_japanese:
                findings.append(f"ERROR: {rel}: prefer or signals must include at least one Japanese term")

        priorities: dict[int, list[str]] = defaultdict(list)
        for frame, (_, doc) in cluster_docs.items():
            priorities[doc.priority].append(frame)
        for priority, frames_for_priority in sorted(priorities.items()):
            if len(frames_for_priority) > 1:
                warnings.append(
                    f"WARNING: cluster {cluster_name}: priority {priority} is shared by {', '.join(sorted(frames_for_priority))}"
                )

    if findings:
        print(f"Found {len(findings)} routing hint issue(s) under {root}:")
        for finding in findings:
            print(finding)
        return 1

    print(f"OK: all routing hint files passed lint under {root}")
    for warning in warnings:
        print(warning)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
