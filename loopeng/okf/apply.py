from __future__ import annotations

import shutil
from pathlib import Path

from .backup import backup_tree
from .index import reindex_bundle
from .schema import concept_prefix_for_type, load_report, parse_frontmatter, validate_bundle, validate_document_text, validate_report_payload


def _document_text(document: object) -> str:
    if not isinstance(document, str):
        raise ValueError("operation document must be a string")
    return document if document.endswith("\n") else document + "\n"


def _bundle_destination(bundle: Path, concept_id: str) -> Path:
    destination = (bundle / f"{concept_id}.md").resolve()
    try:
        destination.relative_to(bundle.resolve())
    except ValueError as exc:
        raise ValueError("concept path escapes bundle") from exc
    return destination


def _validate_operation(bundle: Path, role: str, operation: dict[str, object]) -> None:
    concept_id = str(operation["concept_id"])
    destination = _bundle_destination(bundle, concept_id)
    prefix = concept_id.split("/", 1)[0]
    if operation["action"] == "DELETE":
        allowed_prefixes = set(concept_prefix_for_type(name) for name in (
            "Concept",
            "Decision",
            "Constraint",
            "Failure Pattern",
            "Evaluation Rule",
            "Recovery Pattern",
            "Runbook",
            "Reference",
            "Loop Brief Pattern",
        ))
        if prefix not in allowed_prefixes:
            raise ValueError(f"concept_id namespace is not allowed: {concept_id!r}")
        return

    document = _document_text(operation.get("document"))
    if role == "memory-curator":
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
    else:
        if prefix != "loop-brief-patterns":
            raise ValueError("brief pattern concept_id must be under loop-brief-patterns/")
    _ = destination


def _write_operation(bundle: Path, operation: dict[str, object]) -> Path:
    concept_id = str(operation["concept_id"])
    destination = _bundle_destination(bundle, concept_id)
    destination.parent.mkdir(parents=True, exist_ok=True)
    if operation["action"] == "DELETE":
        if destination.exists():
            destination.unlink()
        return destination
    document = operation.get("document")
    destination.write_text(_document_text(document), encoding="utf-8")
    return destination


def apply_report(bundle: Path, report_path: Path, backup_dir: Path) -> dict[str, object]:
    bundle = bundle.resolve()
    backup_dir = backup_dir.resolve()
    bundle_validation = validate_bundle(bundle)
    if not bundle_validation["ok"]:
        return {"ok": False, "errors": bundle_validation["errors"]}
    report = load_report(report_path)
    errors = validate_report_payload(report)
    if errors:
        return {"ok": False, "errors": errors}
    role = str(report.get("role") or "memory-curator")
    if role == "brief-pattern-curator":
        brief_errors: list[str] = []
        for index, operation in enumerate(report.get("operations", [])):
            if not isinstance(operation, dict):
                brief_errors.append(f"operations[{index}] must be an object")
                continue
            try:
                _validate_operation(bundle, role, operation)
            except Exception as exc:
                brief_errors.append(f"operations[{index}]: {exc}")
        if brief_errors:
            return {"ok": False, "errors": brief_errors}
    else:
        role_errors: list[str] = []
        for index, operation in enumerate(report.get("operations", [])):
            if not isinstance(operation, dict):
                role_errors.append(f"operations[{index}] must be an object")
                continue
            try:
                _validate_operation(bundle, role, operation)
            except Exception as exc:
                role_errors.append(f"operations[{index}]: {exc}")
        if role_errors:
            return {"ok": False, "errors": role_errors}
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
            handle.write(f"- applied {report_path.name}\n")
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
    return {"ok": True, "touched": touched, "backup": str(backup_root)}
