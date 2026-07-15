from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ._paths import agent_root
from .journal import EVENT_COMMAND, append_event
from .run import RESERVED_RUN_SELECTORS
from .locking import _stale
from .okf.schema import validate_bundle


def _install_integrity(repo: Path, against: Path | None = None) -> dict[str, Any]:
    path = repo / agent_root("runtime", "install-manifest.json")
    if not path.is_file():
        return {"ok": False, "error": "install manifest missing"}
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"ok": False, "error": f"invalid install manifest: {type(exc).__name__}"}
    if not isinstance(manifest, dict):
        return {"ok": False, "error": "install manifest root is not an object"}
    listed = manifest.get("distributed")
    entries = manifest.get("entries")
    if not isinstance(listed, list):
        listed = [item.get("relative_path") for item in entries or [] if isinstance(item, dict)]
    listed = sorted({str(item) for item in listed if item})
    missing = [rel for rel in listed if not (repo / rel).is_file()]
    entry_paths = sorted({str(item.get("relative_path")) for item in entries or [] if isinstance(item, dict) and item.get("relative_path")})
    unlisted_entries = sorted(set(entry_paths) - set(listed))
    version_path = repo / "VERSION"
    version = version_path.read_text(encoding="utf-8").strip() if version_path.is_file() else None
    recorded_version = manifest.get("version", manifest.get("source_version"))
    errors = list(missing)
    if unlisted_entries:
        errors.append("manifest entries absent from distributed")
    if version != recorded_version:
        errors.append("VERSION does not match install manifest")
    comparison = None
    if against is not None:
        kit_version = (against / "VERSION").read_text(encoding="utf-8").strip() if (against / "VERSION").is_file() else None
        comparison = {"kit": str(against), "kit_version": kit_version, "installed_version": version,
                      "kit_commit": manifest.get("kit_commit", manifest.get("source_commit")),
                      "version_match": kit_version == version}
    return {"ok": not errors, "missing": missing, "unlisted_entries": unlisted_entries,
            "version": version, "manifest_version": recorded_version, "comparison": comparison}


def _json_files(repo: Path) -> list[Path]:
    root = repo / agent_root("state")
    return sorted([*root.glob("**/*.json"), *root.glob("**/*.jsonl")]) if root.is_dir() else []


def _parse_health(path: Path) -> list[str]:
    errors: list[str] = []
    if path.suffix == ".json":
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
            return [] if isinstance(value, (dict, list)) else [f"{path}: not an object or list"]
        except (json.JSONDecodeError, OSError) as exc:
            return [f"{path}: {type(exc).__name__}"]
    for index, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
            if not isinstance(value, dict):
                errors.append(f"{path}:{index}: not an object")
        except (json.JSONDecodeError, OSError) as exc:
            errors.append(f"{path}:{index}: {type(exc).__name__}")
    return errors


def inspect(repo: Path, against: Path | None = None) -> dict[str, Any]:
    repo = repo.resolve()
    parse_errors = [error for path in _json_files(repo) for error in _parse_health(path)]
    lock = repo / agent_root("state", "lock")
    stale_lock = lock.is_file() and _stale(lock)
    active_path = repo / agent_root("state", "active-runs.json")
    try:
        active = json.loads(active_path.read_text(encoding="utf-8")) if active_path.is_file() else {}
    except (OSError, json.JSONDecodeError):
        active = {}
    orphaned = []
    if isinstance(active, dict):
        for run_id in active:
            if not (repo / agent_root("state", "journal") / f"{run_id}.jsonl").is_file():
                orphaned.append(str(run_id))
    bundle = validate_bundle(repo / "llmwiki")
    hook_files = [repo / ".codex" / "hooks.json", repo / ".claude" / "settings.json"]
    hook_registration = {str(path.relative_to(repo)): path.is_file() for path in hook_files}
    version_path = repo / "VERSION"
    installed_versions = []
    for path in hook_files:
        if path.is_file():
            try:
                text = path.read_text(encoding="utf-8")
                if version_path.is_file() and version_path.read_text(encoding="utf-8").strip() in text:
                    installed_versions.append(str(path.relative_to(repo)))
            except OSError:
                pass
    draft_root = repo / agent_root("state", "memory-drafts")
    drafts = sorted(str(path.relative_to(repo)) for path in draft_root.glob("*.json")) if draft_root.is_dir() else []
    mismatches: list[str] = []
    reports = repo / agent_root("state", "reports")
    journals = repo / agent_root("state", "journal")
    for sidecar in reports.glob("*.json") if reports.is_dir() else ():
        run_id = sidecar.stem
        if not (journals / f"{run_id}.jsonl").is_file():
            mismatches.append(run_id)
    reserved_run_ids = [path.stem for path in (journals.glob("*.jsonl") if journals.is_dir() else ()) if path.stem in RESERVED_RUN_SELECTORS]
    install_integrity = _install_integrity(repo, against)
    return {"ok": not (parse_errors or orphaned or mismatches or reserved_run_ids or not bundle.get("ok") or not install_integrity.get("ok")),
            "json_errors": parse_errors, "stale_lock": stale_lock, "orphaned_active_runs": orphaned,
            "bundle": bundle, "drafts": drafts, "sidecar_journal_mismatches": mismatches,
            "reserved_run_ids": reserved_run_ids, "install_integrity": install_integrity}


def doctor(repo: Path, fix: bool = False, against: Path | None = None) -> dict[str, Any]:
    repo = repo.resolve()
    result = inspect(repo, against)
    repaired: list[str] = []
    if fix:
        lock = repo / agent_root("state", "lock")
        if result["stale_lock"]:
            lock.unlink(missing_ok=True)
            repaired.append("stale lock removed")
        if result["orphaned_active_runs"]:
            path = repo / agent_root("state", "active-runs.json")
            value = json.loads(path.read_text(encoding="utf-8"))
            for run_id in result["orphaned_active_runs"]:
                value.pop(run_id, None)
            path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
            repaired.append("orphaned active runs removed")
        for error in result["json_errors"]:
            raw_path = Path(error.split(":", 1)[0])
            if raw_path.suffix != ".jsonl" or not raw_path.is_file():
                continue
            quarantine = raw_path.parent / ".quarantine"
            quarantine.mkdir(exist_ok=True)
            target = quarantine / f"{raw_path.name}.{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')}"
            shutil.copy2(raw_path, target)
            repaired.append(f"quarantined {raw_path}")
            break
        if repaired:
            append_event(repo, "doctor", {"kind": EVENT_COMMAND, "command": "doctor repairs", "repaired": repaired})
            result = inspect(repo, against)
    result["repaired"] = repaired
    result["instructions"] = ["run loopeng doctor --fix for safe repairs", "see docs/RECOVERY.md for non-repairable conditions"]
    return result
