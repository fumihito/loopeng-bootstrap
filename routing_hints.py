from __future__ import annotations

import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


ROUTING_HINT_SCHEMA = "routing-hints/v1"
ROUTING_HINT_FENCE = "route-hints-v1"
ROUTING_HINT_FIELDS = ("prefer", "avoid", "good_for", "bad_for", "signals")
ALLOWED_TOP_LEVEL_KEYS = {"schema", "frame", "priority", "summary", *ROUTING_HINT_FIELDS}
ALLOWED_ENTRY_KEYS = {"phrase", "aliases", "weight", "note"}
SECTION_DEFAULT_WEIGHTS = {
    "prefer": 4,
    "good_for": 2,
    "signals": 1,
    "avoid": -4,
    "bad_for": -2,
}
SECTION_WEIGHT_SIGNS = {
    "prefer": 1,
    "good_for": 1,
    "signals": 1,
    "avoid": -1,
    "bad_for": -1,
}


@dataclass(frozen=True)
class RoutingHintEntry:
    phrase: str
    aliases: tuple[str, ...] = ()
    weight: int = 0
    note: str | None = None


@dataclass(frozen=True)
class RoutingHintsDocument:
    schema: str
    frame: str
    priority: int = 0
    summary: str = ""
    sections: dict[str, tuple[RoutingHintEntry, ...]] = field(default_factory=dict)


def tokenize(text: str) -> set[str]:
    return set(re.findall(r"[A-Za-z0-9]+", text.lower()))


def extract_routing_toml(content: str) -> str | None:
    blocks: list[str] = []
    pattern = re.compile(r"```(?P<info>[^\n`]*)\n(?P<body>.*?)\n```", re.S)
    for match in pattern.finditer(content):
        info = match.group("info").strip().lower()
        if not info:
            continue
        labels = set(info.split())
        if ROUTING_HINT_FENCE in labels:
            blocks.append(match.group("body"))
    if len(blocks) != 1:
        return None
    return blocks[0]


def _entry_from_value(value: Any, section: str) -> RoutingHintEntry:
    if not isinstance(value, dict):
        raise ValueError(f"{section} entries must be TOML tables")
    unknown = sorted(set(value) - ALLOWED_ENTRY_KEYS)
    if unknown:
        raise ValueError(f"{section} entry has unknown keys: {', '.join(unknown)}")
    phrase = value.get("phrase")
    if not isinstance(phrase, str) or not phrase.strip():
        raise ValueError(f"{section} entry phrase must be a non-empty string")
    aliases_value = value.get("aliases", [])
    if not isinstance(aliases_value, list) or any(not isinstance(item, str) or not item.strip() for item in aliases_value):
        raise ValueError(f"{section} entry aliases must be an array of non-empty strings")
    weight = value.get("weight")
    if not isinstance(weight, int):
        raise ValueError(f"{section} entry weight must be an integer")
    note = value.get("note")
    if note is not None and not isinstance(note, str):
        raise ValueError(f"{section} entry note must be a string when present")
    return RoutingHintEntry(
        phrase=phrase.strip(),
        aliases=tuple(alias.strip() for alias in aliases_value),
        weight=weight,
        note=note.strip() if isinstance(note, str) and note.strip() else None,
    )


def parse_routing_hints_toml(content: str) -> RoutingHintsDocument:
    toml_body = extract_routing_toml(content)
    if toml_body is None:
        raise ValueError(f"expected exactly one `{ROUTING_HINT_FENCE}` fenced TOML block")
    raw = tomllib.loads(toml_body)
    if not isinstance(raw, dict):
        raise ValueError("routing hints TOML root must be a table")
    unknown_top_level = sorted(set(raw) - ALLOWED_TOP_LEVEL_KEYS)
    if unknown_top_level:
        raise ValueError(f"unknown top-level keys: {', '.join(unknown_top_level)}")
    schema = raw.get("schema")
    frame = raw.get("frame")
    if schema != ROUTING_HINT_SCHEMA:
        raise ValueError(f"schema must be {ROUTING_HINT_SCHEMA}")
    if not isinstance(frame, str) or not frame.strip():
        raise ValueError("frame must be a non-empty string")
    priority = raw.get("priority", 0)
    if not isinstance(priority, int) or not 0 <= priority <= 100:
        raise ValueError("priority must be an integer from 0 to 100")
    summary = raw.get("summary", "")
    if not isinstance(summary, str):
        raise ValueError("summary must be a string when present")

    sections: dict[str, tuple[RoutingHintEntry, ...]] = {}
    for section in ROUTING_HINT_FIELDS:
        entries_value = raw.get(section, [])
        if not isinstance(entries_value, list):
            raise ValueError(f"{section} must be an array of tables")
        entries = tuple(_entry_from_value(item, section) for item in entries_value)
        if any(SECTION_WEIGHT_SIGNS[section] * entry.weight <= 0 for entry in entries):
            raise ValueError(f"{section} entry weights must match the section polarity")
        sections[section] = entries

    return RoutingHintsDocument(
        schema=schema,
        frame=frame.strip(),
        priority=priority,
        summary=summary.strip(),
        sections=sections,
    )


def validate_routing_hints_document(document: RoutingHintsDocument, expected_frame: str | None = None) -> list[str]:
    errors: list[str] = []
    if document.schema != ROUTING_HINT_SCHEMA:
        errors.append(f"schema must be {ROUTING_HINT_SCHEMA}")
    if not document.frame:
        errors.append("frame must be a non-empty string")
    if expected_frame is not None and document.frame != expected_frame:
        errors.append(f"frame must match directory name {expected_frame}")
    if not 0 <= document.priority <= 100:
        errors.append("priority must be an integer from 0 to 100")
    if not isinstance(document.summary, str):
        errors.append("summary must be a string")
    for section in ROUTING_HINT_FIELDS:
        entries = document.sections.get(section, ())
        for index, entry in enumerate(entries):
            if not entry.phrase.strip():
                errors.append(f"{section}[{index}].phrase must be a non-empty string")
            if any(not alias.strip() for alias in entry.aliases):
                errors.append(f"{section}[{index}].aliases must be non-empty strings")
            if not isinstance(entry.weight, int):
                errors.append(f"{section}[{index}].weight must be an integer")
            elif SECTION_WEIGHT_SIGNS[section] * entry.weight <= 0:
                errors.append(f"{section}[{index}].weight must match section polarity")
    return errors


def load_routing_hints(path: Path) -> RoutingHintsDocument:
    return parse_routing_hints_toml(path.read_text(encoding="utf-8"))


def section_entries(document: RoutingHintsDocument) -> list[tuple[str, RoutingHintEntry]]:
    entries: list[tuple[str, RoutingHintEntry]] = []
    for section in ROUTING_HINT_FIELDS:
        entries.extend((section, entry) for entry in document.sections.get(section, ()))
    return entries


def _entry_match_strength(route_text: str, route_terms: set[str], entry: RoutingHintEntry) -> tuple[int, list[str]]:
    route_text_lower = route_text.lower()
    best = 0
    reasons: list[str] = []
    variants = [entry.phrase, *entry.aliases]
    for variant in variants:
        variant_terms = tokenize(variant)
        token_overlap = len(route_terms & variant_terms)
        strength = token_overlap
        if variant.lower() in route_text_lower:
            strength = max(strength, 2 + token_overlap)
        elif token_overlap:
            strength = max(strength, 1 + token_overlap)
        if strength > best:
            best = strength
            reasons = [variant]
    return best, reasons


def score_routing_hints(route_text: str, document: RoutingHintsDocument) -> tuple[int, list[str]]:
    route_terms = tokenize(route_text)
    total = document.priority
    reasons: list[tuple[int, str]] = []
    for section in ROUTING_HINT_FIELDS:
        for entry in document.sections.get(section, ()):
            strength, matched = _entry_match_strength(route_text, route_terms, entry)
            if strength <= 0:
                continue
            delta = entry.weight * strength
            total += delta
            rendered = f"{section}:{entry.phrase}"
            if matched:
                rendered += f" ({matched[0]})"
            rendered += f" [{delta:+d}]"
            reasons.append((abs(delta), rendered))
    reasons.sort(key=lambda item: (-item[0], item[1]))
    return total, [rendered for _, rendered in reasons[:4]]


def summarize_routing_hints(route_text: str, document: RoutingHintsDocument) -> str:
    lines: list[str] = []
    if document.summary:
        lines.append(f"  summary: {document.summary}")
    lines.append(f"  priority: {document.priority}")
    for section in ROUTING_HINT_FIELDS:
        entries = document.sections.get(section, ())
        if not entries:
            continue
        scored: list[tuple[int, RoutingHintEntry, str]] = []
        for entry in entries:
            strength, matched = _entry_match_strength(route_text, tokenize(route_text), entry)
            if strength > 0:
                scored.append((strength * entry.weight, entry, matched[0] if matched else entry.phrase))
        if not scored:
            continue
        scored.sort(key=lambda item: (-abs(item[0]), item[1].phrase))
        lines.append(f"  {section}:")
        for delta, entry, matched in scored[:2]:
            alias_text = f"; aliases={', '.join(entry.aliases[:2])}" if entry.aliases else ""
            note_text = f"; note={entry.note}" if entry.note else ""
            lines.append(f"    - {entry.phrase} [{delta:+d}] match={matched}{alias_text}{note_text}")
    return "\n".join(lines)
