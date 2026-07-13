from __future__ import annotations

import shutil
from pathlib import Path
import json
import re

from .backup import backup_tree
from .index import reindex_bundle
from .schema import concept_prefix_for_type, load_report, parse_frontmatter, validate_bundle, validate_document_text, validate_report_payload
from ..audit.policy import AUTONOMOUS_NAMESPACES
from ..locking import repo_lock
from ..audit.policy import INSTRUCTION_SMELL_PATTERNS
from datetime import datetime, timezone


def _document_text(document: object) -> str:
    if not isinstance(document, str):
        raise ValueError("operation document must be a string")
    return document if document.endswith("\n") else document + "\n"


def _instruction_smells(text: str) -> list[str]:
    """Coarse false-positive-prone injection net; patterns live in policy.py."""
    lowered = text.casefold()
    return [pattern for pattern in INSTRUCTION_SMELL_PATTERNS if re.search(pattern, lowered)]


def _bundle_destination(bundle: Path, concept_id: str) -> Path:
    destination = (bundle / f"{concept_id}.md").resolve()
    try:
        destination.relative_to(bundle.resolve())
    except ValueError as exc:
        raise ValueError("concept path escapes bundle") from exc
    return destination


ALLOWED_PREFIXES = {
    "concepts", "decisions", "constraints", "failure-patterns",
    "evaluation-rules", "recovery-patterns", "runbooks", "references",
}


def _validate_operation(bundle: Path, operation: dict[str, object], autonomous: bool = False) -> None:
    concept_id = str(operation["concept_id"])
    destination = _bundle_destination(bundle, concept_id)
    prefix = concept_id.split("/", 1)[0]
    if operation["action"] == "DELETE":
        raise ValueError("DELETE is forbidden; use DEPRECATE to preserve audit history")
    if operation["action"] == "DEPRECATE":
        if prefix not in ALLOWED_PREFIXES:
            raise ValueError(f"concept_id namespace is not allowed: {concept_id!r}")
        if not destination.is_file():
            raise ValueError(f"cannot deprecate missing document: {concept_id!r}")
        return

    document = _document_text(operation.get("document"))
    errors = validate_document_text(document)
    if errors:
        raise ValueError("; ".join(errors))
    frontmatter, _ = parse_frontmatter(document)
    type_name = str(frontmatter.get("type") or "")
    expected_prefix = concept_prefix_for_type(type_name)
    if not expected_prefix:
        raise ValueError(f"unsupported type: {type_name!r}")
    if prefix != expected_prefix:
        raise ValueError(f"concept_id must be under {expected_prefix}/ for type {type_name!r}")
    if autonomous:
        if operation["action"] != "UPSERT" or prefix not in AUTONOMOUS_NAMESPACES:
            raise ValueError("autonomous apply is limited to UPSERT in an autonomous namespace")
        tier = frontmatter.get("tier")
        if tier != "provisional":
            raise ValueError("autonomous UPSERT must have tier: provisional")
        if destination.is_file():
            existing, _ = parse_frontmatter(destination.read_text(encoding="utf-8"))
            if str(existing.get("tier") or "established") == "established":
                raise ValueError("autonomous apply cannot overwrite established knowledge")
    _ = destination


def _write_operation(bundle: Path, operation: dict[str, object]) -> Path:
    concept_id = str(operation["concept_id"])
    destination = _bundle_destination(bundle, concept_id)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if operation["action"] == "DEPRECATE":
        text = destination.read_text(encoding="utf-8")
        frontmatter, body = parse_frontmatter(text)
        if not frontmatter:
            raise ValueError("cannot deprecate document without frontmatter")
        frontmatter["status"] = "deprecated"
        lines = ["---"]
        for key, value in frontmatter.items():
            if isinstance(value, list):
                rendered = "[" + ", ".join(json.dumps(item, ensure_ascii=False) for item in value) + "]"
            elif isinstance(value, str):
                rendered = json.dumps(value, ensure_ascii=False)
            else:
                rendered = str(value).lower() if isinstance(value, bool) else str(value)
            lines.append(f"{key}: {rendered}")
        lines.extend(["---", "", body.rstrip("\n"), ""])
        destination.write_text("\n".join(lines), encoding="utf-8")
        return destination
    document = operation.get("document")
    destination.write_text(_document_text(document), encoding="utf-8")
    return destination


def _memory_log_entry(bundle: Path, report: dict[str, object], operation: dict[str, object]) -> dict[str, object]:
    action = str(operation["action"])
    if action == "DEPRECATE":
        frontmatter, _ = parse_frontmatter((bundle / f"{operation['concept_id']}.md").read_text(encoding="utf-8"))
    else:
        frontmatter, _ = parse_frontmatter(_document_text(operation.get("document")))
    concept_id = str(operation["concept_id"])
    namespace = concept_id.split("/", 1)[0]
    return {
        "ts": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "action": action,
        "concept_id": concept_id,
        "type": str(frontmatter.get("type") or ""),
        "namespace": namespace,
        "tier": str(frontmatter.get("tier") or "established"),
        "author": str(report.get("author") or report.get("role") or "unspecified"),
        "run_id": str(report.get("run_id") or ""),
        "proposal_id": str(operation.get("proposal_id") or ""),
        "report": str(report.get("report") or ""),
        "v": 1,
    }


def apply_report(bundle: Path, report_path: Path, backup_dir: Path, autonomous: bool = False) -> dict[str, object]:
    bundle = bundle.resolve()
    repo = bundle.parent.resolve()
    backup_dir = backup_dir.resolve()
    with repo_lock(repo, str(report_path)):
        return _apply_report_locked(bundle, report_path, backup_dir, autonomous)


def _apply_report_locked(bundle: Path, report_path: Path, backup_dir: Path, autonomous: bool = False) -> dict[str, object]:
    bundle_validation = validate_bundle(bundle)
    if not bundle_validation["ok"]:
        return {"ok": False, "errors": bundle_validation["errors"]}
    report = load_report(report_path)
    errors = validate_report_payload(report)
    if errors:
        return {"ok": False, "errors": errors}
    operation_errors: list[str] = []
    smell_warnings: list[str] = []
    for index, operation in enumerate(report.get("operations", [])):
        if not isinstance(operation, dict):
            operation_errors.append(f"operations[{index}] must be an object")
            continue
        try:
            if isinstance(operation, dict) and operation.get("action") == "UPSERT":
                matches = _instruction_smells(_document_text(operation.get("document")))
                if autonomous and matches:
                    raise ValueError("autonomous apply deferred: memory instruction smell matched: " + ", ".join(matches))
                smell_warnings.extend(matches)
            _validate_operation(bundle, operation, autonomous=autonomous)
        except Exception as exc:
            operation_errors.append(f"operations[{index}]: {exc}")
    if operation_errors:
        return {"ok": False, "errors": operation_errors}
    operations = report.get("operations", [])
    backup_root = backup_dir / report_path.stem
    backup_tree(bundle, backup_root)
    touched: list[str] = []
    try:
        for operation in operations:
            if not isinstance(operation, dict):
                raise ValueError("invalid operation")
            destination = _write_operation(bundle, operation)
            touched.append(str(destination.relative_to(bundle)))
        reindex_bundle(bundle)
        log_path = bundle / "log.md"
        with log_path.open("a", encoding="utf-8") as handle:
            proposals = ",".join(str(op["proposal_id"]) for op in operations)
            author = str(report.get("role") or report.get("author") or "unspecified")
            for operation in operations:
                if operation["action"] == "DEPRECATE":
                    handle.write(f"- deprecated {operation['concept_id']} by {author}\n")
            handle.write(f"- applied {report_path.name} author={author} proposals={proposals}\n")
        json_log = bundle / "log.jsonl"
        with json_log.open("a", encoding="utf-8") as handle:
            for operation in operations:
                entry = _memory_log_entry(bundle, report, operation)
                entry["report"] = str(report_path)
                handle.write(json.dumps(entry, ensure_ascii=False, sort_keys=True) + "\n")
    except Exception as exc:
        if backup_root.exists():
            for path in sorted(bundle.rglob("*"), reverse=True):
                if path.is_file():
                    path.unlink()
            for path in sorted(backup_root.rglob("*")):
                relative = path.relative_to(backup_root)
                target = bundle / relative
                if path.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                elif path.is_file():
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(path, target)
        return {"ok": False, "errors": [str(exc)], "touched": touched}
    source_learning = report.get("source_learning")
    if isinstance(source_learning, str):
        source_path = Path(source_learning)
        if not source_path.is_absolute():
            source_path = (bundle.parent / source_path).resolve()
        try:
            value = json.loads(source_path.read_text(encoding="utf-8"))
            if isinstance(value, dict):
                value["applied"] = datetime.now(timezone.utc).isoformat()
                source_path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        except (OSError, json.JSONDecodeError):
            pass
    result = {"ok": True, "touched": touched, "backup": str(backup_root)}
    if smell_warnings:
        result["warnings"] = {"memory_instruction_smell": sorted(set(smell_warnings))}
    return result
