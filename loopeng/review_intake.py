from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from ._paths import agent_root
from .audit.export import packet_hash
from .journal import EVENT_EXTERNAL_REVIEW, append_event
from .review_contract import validate_contract


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _find_packet(repo: Path, run_id: str, expected_hash: str) -> tuple[Path | None, list[str]]:
    root = repo / agent_root("state", "review-packets")
    candidates = sorted(path for path in root.glob(run_id) if path.is_dir()) if root.is_dir() else []
    if not candidates:
        return None, ["packet not found"]
    for candidate in candidates:
        manifest_path = candidate / "manifest.json"
        try:
            manifest = _load_json(manifest_path)
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(manifest, dict) and manifest.get("packet_hash") == expected_hash:
            actual = packet_hash(candidate)
            return candidate, ([] if actual == expected_hash else ["packet_hash mismatch"])
    return None, ["packet_hash mismatch"]


def _pointer_exists(packet: Path, ref: str) -> bool:
    if ref.startswith("journal:"):
        parts = ref.split(":")
        if len(parts) != 3 or parts[1] != json.loads((packet / "manifest.json").read_text(encoding="utf-8")).get("run_id"):
            return False
        try:
            line = int(parts[2])
            events = _load_json(packet / "journal.json")
            return isinstance(events, list) and 1 <= line <= len(events)
        except (ValueError, OSError, json.JSONDecodeError):
            return False
    if ref.startswith("file:"):
        parts = ref.split(":")
        if len(parts) != 3:
            return False
        try:
            index = _load_json(packet / "source-index.json")
            return isinstance(index, dict) and parts[1] in index and 1 <= int(parts[2]) <= int(index[parts[1]])
        except (ValueError, OSError, json.JSONDecodeError, TypeError):
            return False
    if ref.startswith("report:"):
        section = ref.split(":", 1)[1].strip().casefold()
        report = packet / "r1.md"
        reports = list(packet.glob("*.md"))
        if not reports:
            return False
        try:
            return any(line.lstrip().startswith("#") and section in line.lstrip("# ").casefold() for line in reports[0].read_text(encoding="utf-8").splitlines())
        except OSError:
            return False
    if ref.startswith("sidecar:"):
        try:
            sidecars = list(packet.glob("*.json"))
            sidecar = next(path for path in sidecars if path.name != "manifest.json" and path.name != "journal.json" and path.name != "source-index.json")
            value: Any = _load_json(sidecar)
            for key in ref.split(":", 1)[1].split("."):
                value = value[key]
            return True
        except (StopIteration, OSError, json.JSONDecodeError, KeyError, TypeError):
            return False
    return False


def _dimension(value: dict[str, Any], identifier: str) -> dict[str, Any] | None:
    return next((item for item in value.get("dimensions", []) if isinstance(item, dict) and item.get("id") == identifier), None)


def intake(repo: Path, report_path: Path) -> dict[str, Any]:
    repo = repo.resolve()
    errors = []
    warnings: list[str] = []
    try:
        report = _load_json(report_path)
    except (OSError, json.JSONDecodeError) as exc:
        return {"accepted": False, "errors": [f"schema: {type(exc).__name__}"], "warnings": []}
    errors.extend(f"schema: {error}" for error in validate_contract(report))
    if errors:
        return {"accepted": False, "errors": errors, "warnings": warnings}
    assert isinstance(report, dict)
    run_id = report["packet"]["run_id"]
    packet, packet_errors = _find_packet(repo, run_id, report["packet"]["packet_hash"])
    errors.extend(f"packet: {error}" for error in packet_errors)
    if packet is None:
        return {"accepted": False, "errors": errors, "warnings": warnings}
    for dimension in report["dimensions"]:
        for evidence in dimension.get("evidence", []):
            if not _pointer_exists(packet, evidence["ref"]):
                errors.append(f"evidence: unresolved {evidence['ref']}")
    sidecars = [path for path in packet.glob("*.json") if path.name not in {"manifest.json", "journal.json", "source-index.json"}]
    sidecar: dict[str, Any] = {}
    if sidecars:
        try:
            loaded = _load_json(sidecars[0])
            sidecar = loaded if isinstance(loaded, dict) else {}
        except (OSError, json.JSONDecodeError):
            errors.append("cross-check: sidecar unreadable")
    d2 = _dimension(report, "D2")
    outcome = sidecar.get("outcome")
    if d2 and ((d2.get("verdict") == "pass" and outcome == "fail") or (d2.get("verdict") == "fail" and outcome == "pass")):
        errors.append("review_inconsistency: D2 verdict contradicts sidecar outcome")
    d4 = _dimension(report, "D4")
    if d4:
        note = str(d4.get("note") or "")
        actual_critical = sum(1 for alert in sidecar.get("alerts", []) if isinstance(alert, dict) and alert.get("severity") == "critical")
        actual_warn = sum(1 for alert in sidecar.get("alerts", []) if isinstance(alert, dict) and alert.get("severity") == "warn")
        for label, actual in (("critical", actual_critical), ("warn", actual_warn)):
            match = re.search(rf"{label}\s*[:=]\s*(\d+)", note, re.I)
            if match and int(match.group(1)) != actual:
                errors.append(f"cross-check: D4 {label} count {match.group(1)} != {actual}")
    d3 = _dimension(report, "D3")
    no_memory = d3 and "no memory" in str(d3.get("note") or "").casefold()
    if no_memory and (int(sidecar.get("memory", {}).get("applied", 0) or 0) > 0):
        errors.append("cross-check: D3 says no memory write but sidecar records applied memory")
    try:
        journal = _load_json(packet / "journal.json")
    except (OSError, json.JSONDecodeError):
        journal = []
    starts = [event for event in journal if isinstance(event, dict) and event.get("kind") == "run-start"]
    agent = str(starts[0].get("agent") or "") if starts else ""
    reviewer = report["reviewer"]
    if reviewer.get("relation") != "external":
        errors.append("independence: reviewer.relation must be external")
    if reviewer.get("model") == agent:
        warnings.append("self_review")
    if errors:
        return {"accepted": False, "errors": errors, "warnings": warnings, "run_id": run_id}
    relative_report = str(report_path)
    try:
        relative_report = str(report_path.resolve().relative_to(repo))
    except ValueError:
        pass
    append_event(repo, run_id, {"kind": EVENT_EXTERNAL_REVIEW, "run_id": run_id, "overall": report["overall"], "report": relative_report, "warnings": warnings, "accepted_by": "loopeng review intake"})
    return {"accepted": True, "errors": [], "warnings": warnings, "run_id": run_id, "overall": report["overall"]}
