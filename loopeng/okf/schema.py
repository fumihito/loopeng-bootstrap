from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path
from typing import Any


ALLOWED_TYPES = {
    "Concept",
    "Decision",
    "Constraint",
    "Failure Pattern",
    "Evaluation Rule",
    "Recovery Pattern",
    "Runbook",
    "Reference",
}

TYPE_PREFIXES = {
    "Concept": "concepts",
    "Decision": "decisions",
    "Constraint": "constraints",
    "Failure Pattern": "failure-patterns",
    "Evaluation Rule": "evaluation-rules",
    "Recovery Pattern": "recovery-patterns",
    "Runbook": "runbooks",
    "Reference": "references",
}

REQUIRED_FRONTMATTER = {
    "type",
    "title",
    "description",
    "tags",
    "timestamp",
    "status",
    "sensitivity",
    "authority",
    "confidence",
}
VALID_TIERS = {"provisional", "established"}
ALLOWED_STATUSES = {"active", "deprecated"}
ALLOWED_SENSITIVITY = {"public", "internal"}


def _parse_scalar(value: str) -> Any:
    text = value.strip()
    if text in {"true", "false"}:
        return text == "true"
    if re.fullmatch(r"-?\d+", text):
        return int(text)
    if re.fullmatch(r"-?\d+\.\d+", text):
        return float(text)
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        return text[1:-1]
    if text.startswith("[") and text.endswith("]"):
        body = text[1:-1].strip()
        if not body:
            return []
        parts = [part.strip() for part in body.split(",")]
        return [_parse_scalar(part) for part in parts]
    return text


def parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    if not text.startswith("---\n"):
        return {}, text
    lines = text.splitlines()
    body_start = None
    for index, line in enumerate(lines[1:], start=1):
        if line == "---":
            body_start = index + 1
            break
    if body_start is None:
        return {}, text
    frontmatter: dict[str, Any] = {}
    for line in lines[1:body_start - 1]:
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        frontmatter[key.strip()] = _parse_scalar(raw_value)
    body = "\n".join(lines[body_start:])
    if text.endswith("\n") and not body.endswith("\n"):
        body += "\n"
    return frontmatter, body


def parse_document(path: Path) -> tuple[dict[str, Any], str]:
    return parse_frontmatter(path.read_text(encoding="utf-8"))


def validate_document(path: Path) -> list[str]:
    return validate_document_text(path.read_text(encoding="utf-8"))


def validate_document_text(text: str) -> list[str]:
    errors: list[str] = []
    frontmatter, body = parse_frontmatter(text)
    missing = REQUIRED_FRONTMATTER.difference(frontmatter)
    if missing:
        errors.append(f"missing frontmatter fields: {', '.join(sorted(missing))}")
    if frontmatter.get("type") not in ALLOWED_TYPES:
        errors.append(f"unsupported type: {frontmatter.get('type')!r}")
    if frontmatter.get("status") not in ALLOWED_STATUSES:
        errors.append(f"unsupported status: {frontmatter.get('status')!r}")
    if frontmatter.get("sensitivity") not in ALLOWED_SENSITIVITY:
        errors.append(f"unsupported sensitivity: {frontmatter.get('sensitivity')!r}")
    tags = frontmatter.get("tags")
    if not isinstance(tags, list) or not tags:
        errors.append("tags must be a non-empty list")
    if body.strip() == "":
        errors.append("document body must not be empty")
    if "review_after" in frontmatter:
        review_after = frontmatter["review_after"]
        if not isinstance(review_after, str):
            errors.append("review_after must be an ISO date (YYYY-MM-DD)")
        else:
            try:
                date.fromisoformat(review_after)
            except ValueError:
                errors.append("review_after must be an ISO date (YYYY-MM-DD)")
    if "tier" in frontmatter and frontmatter["tier"] not in VALID_TIERS:
        errors.append("tier must be provisional or established")
    return errors


def concept_prefix_for_type(concept_type: str) -> str:
    return TYPE_PREFIXES.get(concept_type, "")


def validate_bundle(bundle: Path) -> dict[str, Any]:
    errors: list[str] = []
    if not bundle.is_dir():
        errors.append(f"bundle is not a directory: {bundle}")
    for rel in ("index.md", "log.md"):
        if not (bundle / rel).exists():
            errors.append(f"missing {rel}")
    json_log = bundle / "log.jsonl"
    if json_log.is_file():
        for index, line in enumerate(json_log.read_text(encoding="utf-8").splitlines(), start=1):
            if not line.strip():
                continue
            try:
                entry = json.loads(line)
            except json.JSONDecodeError as exc:
                errors.append(f"log.jsonl:{index} invalid JSON: {exc.msg}")
                continue
            if not isinstance(entry, dict):
                errors.append(f"log.jsonl:{index} must be a JSON object")
            elif entry.get("v") != 1:
                errors.append(f"log.jsonl:{index} v must be 1")
    return {"ok": not errors, "errors": errors, "bundle": str(bundle)}


def validate_report_payload(payload: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return ["report payload must be an object"]
    operations = payload.get("operations")
    if not isinstance(operations, list):
        errors.append("operations must be a list")
    else:
        if len(operations) > 20:
            errors.append("operations must contain no more than 20 items")
        proposal_ids: set[str] = set()
        for index, op in enumerate(operations):
            if not isinstance(op, dict):
                errors.append(f"operations[{index}] must be an object")
                continue
            if op.get("action") not in {"UPSERT", "DELETE", "DEPRECATE"}:
                errors.append(f"operations[{index}].action must be UPSERT, DEPRECATE, or DELETE")
            proposal_id = op.get("proposal_id")
            if not isinstance(proposal_id, str) or not proposal_id.strip():
                errors.append(f"operations[{index}].proposal_id must be a non-empty string")
            elif proposal_id in proposal_ids:
                errors.append(f"operations[{index}].proposal_id must be unique")
            else:
                proposal_ids.add(proposal_id)
            if not isinstance(op.get("concept_id"), str) or not op["concept_id"]:
                errors.append(f"operations[{index}].concept_id must be a non-empty string")
            if op.get("action") == "UPSERT" and isinstance(op.get("document"), str):
                if len(op["document"].encode("utf-8")) > 65536:
                    errors.append(f"operations[{index}].document exceeds 65536 UTF-8 bytes")
    return errors


def load_report(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            return payload
    except json.JSONDecodeError:
        pass
    frontmatter, body = parse_frontmatter(text)
    if frontmatter:
        payload = dict(frontmatter)
        payload["body"] = body
        return payload
    raise ValueError("unsupported report format")
