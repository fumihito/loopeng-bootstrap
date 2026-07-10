from __future__ import annotations

import shutil
from pathlib import Path

from .backup import backup_tree
from .index import reindex_bundle
from .schema import load_report, validate_bundle, validate_report_payload


def _document_text(document: object) -> str:
    if not isinstance(document, str):
        raise ValueError("operation document must be a string")
    return document if document.endswith("\n") else document + "\n"


def _write_operation(bundle: Path, operation: dict[str, object]) -> Path:
    concept_id = str(operation["concept_id"])
    destination = bundle / f"{concept_id}.md"
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

