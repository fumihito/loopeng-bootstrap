from __future__ import annotations

import json
import re
import secrets
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ._paths import agent_root
from .audit.export import packet_hash
from .journal import EVENT_DECISION, EVENT_EXTERNAL_REVIEW, append_event
from .review_contract import DIMENSION_DESCRIPTIONS, REVIEW_DIMENSIONS, validate_contract

INCOMING_REL = agent_root("state", "reviews", "incoming")
ACCEPTED_REL = agent_root("state", "reviews", "accepted")
REJECTED_REL = agent_root("state", "reviews", "rejected-intake")


def _load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def _incoming_value(path: Path) -> dict[str, Any] | None:
    try:
        value = _load_json(path)
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def incoming_dir(repo: Path) -> Path:
    path = repo.resolve() / INCOMING_REL
    path.mkdir(parents=True, exist_ok=True)
    return path


def incoming_candidates(repo: Path) -> list[Path]:
    root = repo.resolve() / INCOMING_REL
    return sorted(root.glob("*.json")) if root.is_dir() else []


def incoming_matches(repo: Path, value: dict[str, Any]) -> bool:
    packet = value.get("packet")
    if not isinstance(packet, dict):
        return False
    run_id = str(packet.get("run_id") or "")
    expected_hash = str(packet.get("packet_hash") or "")
    if not run_id or not expected_hash:
        return False
    found, errors = _find_packet(repo.resolve(), run_id, expected_hash)
    return found is not None and not errors


def incoming_run_id(path: Path) -> str | None:
    value = _incoming_value(path)
    packet = value.get("packet") if value else None
    run_id = packet.get("run_id") if isinstance(packet, dict) else None
    return str(run_id) if run_id else None


def incoming_preview(path: Path) -> str:
    value = _incoming_value(path)
    if value is None:
        return "unreadable incoming review"
    reviewer = value.get("reviewer") if isinstance(value.get("reviewer"), dict) else {}
    confirmation = value.get("human_confirmation") if isinstance(value.get("human_confirmation"), dict) else {}
    packet = value.get("packet") if isinstance(value.get("packet"), dict) else {}
    dimensions = value.get("dimensions") if isinstance(value.get("dimensions"), list) else []
    lines = [
        f"packet.run_id: {packet.get('run_id', '(missing)')}",
        f"packet_hash: {packet.get('packet_hash', '(missing)')}",
        f"reviewer.model: {reviewer.get('model', '(missing)')}",
        f"reviewer.session: {reviewer.get('session', '(missing)')}",
        f"reviewer.relation: {reviewer.get('relation', '(missing)')}",
        f"human_confirmation: {'confirmed' if confirmation.get('confirmed') else 'required'}",
        f"overall: {value.get('overall', '(missing)')}",
        "dimensions:",
    ]
    for dimension in dimensions:
        if isinstance(dimension, dict):
            identifier = str(dimension.get("id", "?"))
            lines.append(f"  {identifier} ({DIMENSION_DESCRIPTIONS.get(identifier, 'unknown dimension')})")
            lines.append(f"    verdict: {dimension.get('verdict', '(missing)')}")
            lines.append(f"    note: {dimension.get('note', '(none)')}")
            evidence = dimension.get("evidence") if isinstance(dimension.get("evidence"), list) else []
            for pointer in evidence:
                if isinstance(pointer, dict):
                    lines.append(f"    evidence: {pointer.get('ref', '(missing)')} — {pointer.get('note', '')}")
    findings = value.get("findings") if isinstance(value.get("findings"), list) else []
    if findings:
        lines.append("findings:")
        for finding in findings[:10]:
            lines.extend(f"  {line}" for line in str(finding).splitlines()[:10])
    return "\n".join(lines)


def incoming_is_confirmed(path: Path) -> bool:
    value = _incoming_value(path)
    confirmation = value.get("human_confirmation") if value else None
    return isinstance(confirmation, dict) and confirmation.get("confirmed") is True


def confirm_incoming(path: Path, actor: str = "tui-human") -> dict[str, Any]:
    value = _incoming_value(path)
    if value is None:
        return {"confirmed": False, "error": "incoming review is not valid JSON"}
    value["human_confirmation"] = {"confirmed": True, "actor": actor, "timestamp": datetime.now(timezone.utc).isoformat()}
    path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return {"confirmed": True, "path": str(path)}


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


def _d5_target(packet: Path) -> str | None:
    try:
        value = _load_json(packet / "manifest.json")
        target = value.get("d5_target") if isinstance(value, dict) else None
        return str(target) if target else None
    except (OSError, json.JSONDecodeError):
        return None


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
    incoming_root = repo / INCOMING_REL
    try:
        report_path.resolve().relative_to(incoming_root.resolve())
    except ValueError:
        pass
    else:
        incoming_reviewer = report.get("reviewer") if isinstance(report.get("reviewer"), dict) else {}
        if incoming_reviewer.get("relation") != "self-family" and not incoming_is_confirmed(report_path):
            packet = report.get("packet") if isinstance(report.get("packet"), dict) else {}
            return {"accepted": False, "errors": ["human confirmation required"], "warnings": [], "run_id": packet.get("run_id")}
    run_id = report["packet"]["run_id"]
    packet, packet_errors = _find_packet(repo, run_id, report["packet"]["packet_hash"])
    errors.extend(f"packet: {error}" for error in packet_errors)
    if packet is None:
        return {"accepted": False, "errors": errors, "warnings": warnings}
    for dimension in report["dimensions"]:
        for evidence in dimension.get("evidence", []):
            if not _pointer_exists(packet, evidence["ref"]):
                errors.append(f"evidence: unresolved {evidence['ref']}")
    target = _d5_target(packet)
    d5 = _dimension(report, "D5")
    if target and d5 and not any(pointer.get("ref") == target for pointer in d5.get("evidence", []) if isinstance(pointer, dict)):
        errors.append(f"d5_target mismatch: expected {target}")
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
    requirement = sidecar.get("review_requirement") if isinstance(sidecar.get("review_requirement"), dict) else {}
    if requirement.get("relation") == "external" and report.get("reviewer", {}).get("relation") != "external":
        errors.append("calibration: this due requires relation=external")
    try:
        journal = _load_json(packet / "journal.json")
    except (OSError, json.JSONDecodeError):
        journal = []
    starts = [event for event in journal if isinstance(event, dict) and event.get("kind") == "run-start"]
    agent = str(starts[0].get("agent") or "") if starts else ""
    reviewer = report["reviewer"]
    relation = reviewer.get("relation")
    meta = report.get("meta_review") if isinstance(report.get("meta_review"), dict) else None
    if relation == "self-family":
        if meta and meta.get("decision") == "accept":
            warnings.append("self_review_info")
        else:
            warnings.append("self_review")
            errors.append("meta-review required for self-family review")
    elif reviewer.get("model") == agent:
        warnings.append("self_review")
    if errors:
        return {"accepted": False, "errors": errors, "warnings": warnings, "run_id": run_id}
    relative_report = str(report_path)
    try:
        relative_report = str(report_path.resolve().relative_to(repo))
    except ValueError:
        pass
    append_event(repo, run_id, {"kind": EVENT_EXTERNAL_REVIEW, "run_id": run_id, "overall": report["overall"], "report": relative_report, "relation": relation, "dimensions": report["dimensions"], "findings": report.get("findings", []), "meta_review": meta, "warnings": warnings, "accepted_by": "loopeng review intake"})
    return {"accepted": True, "errors": [], "warnings": warnings, "run_id": run_id, "overall": report["overall"]}


def _move_intake_file(path: Path, destination: Path) -> str:
    destination.mkdir(parents=True, exist_ok=True)
    target = destination / path.name
    if target.exists():
        target = destination / f"{path.stem}-{path.stat().st_mtime_ns}{path.suffix}"
    shutil.move(str(path), str(target))
    return str(target)


def intake_auto(repo: Path) -> dict[str, Any]:
    repo = repo.resolve()
    incoming = incoming_dir(repo)
    accepted_dir = repo / ACCEPTED_REL
    rejected_dir = repo / REJECTED_REL
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    quarantined: list[dict[str, Any]] = []
    for path in sorted(incoming.glob("*.json")):
        if _incoming_value(path) is None:
            moved = _move_intake_file(path, rejected_dir)
            quarantined.append({"file": path.name, "path": moved, "errors": ["schema: invalid JSON"]})
            continue
        result = intake(repo, path)
        entry = {"file": path.name, **result}
        if any("meta-review required" in str(error) for error in result.get("errors", [])):
            entry["route"] = "meta-review required — use inbox --tui"
        if result.get("accepted"):
            entry["path"] = _move_intake_file(path, accepted_dir)
            accepted.append(entry)
        else:
            rejected.append(entry)
    return {"accepted": accepted, "rejected": rejected, "quarantined": quarantined,
            "processed": len(accepted) + len(rejected) + len(quarantined)}


def interactive_meta_review(repo: Path, report_path: Path, input_stream: Any, output_stream: Any) -> dict[str, Any]:
    """CLI fallback for self-family reports when a TUI is unavailable."""
    value = _incoming_value(report_path)
    if value is None:
        return {"accepted": False, "errors": ["schema: invalid JSON"], "warnings": []}
    dimensions = {str(item.get("id")): item for item in value.get("dimensions", []) if isinstance(item, dict)}
    output_stream.write("Meta-review\n")
    for identifier in REVIEW_DIMENSIONS:
        item = dimensions.get(identifier, {})
        evidence = item.get("evidence") if isinstance(item.get("evidence"), list) else []
        output_stream.write(f"{identifier}: {item.get('verdict', '?')} / {len(evidence)} evidence / {str(item.get('note') or '')[:80]}\n")
    spot_dim = secrets.choice(list(REVIEW_DIMENSIONS))
    spot = dimensions.get(spot_dim, {}).get("evidence", [])
    pointer = spot[0].get("ref") if spot and isinstance(spot[0], dict) else "none"
    output_stream.write(f"spot {spot_dim}: {pointer}\nEvidence supports verdict? [y/n]: ")
    output_stream.flush()
    spot_result = "ok" if input_stream.readline().strip().casefold() == "y" else "mismatch"
    output_stream.write("decision [a]ccept/[s]end-back/[x]defer: "); output_stream.flush()
    decision_key = input_stream.readline().strip().casefold()[:1]
    decision = {"a": "accept", "s": "send-back", "x": "defer"}.get(decision_key)
    if not decision:
        return {"accepted": False, "errors": ["meta-review cancelled"], "warnings": []}
    reason = ""
    if decision == "send-back":
        output_stream.write("send-back reason: "); output_stream.flush()
        reason = input_stream.readline().rstrip("\n")
        if not reason.strip():
            return {"accepted": False, "errors": ["send-back reason required"], "warnings": []}
    value["meta_review"] = {"decision": decision, "spot_dim": spot_dim, "spot_result": spot_result, "authorization": "cli-interactive"}
    if decision == "accept":
        value["human_confirmation"] = {"confirmed": True, "actor": "cli-meta-review", "authorization": "cli-interactive"}
    report_path.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    run_id = str(value.get("packet", {}).get("run_id") or "meta-review")
    append_event(repo, run_id, {"kind": EVENT_DECISION, "item": "meta-review", "run_id": run_id, "choice": decision, "spot_dim": spot_dim, "spot_result": spot_result, "reason": reason, "authorization": "cli-interactive"})
    if decision == "accept":
        return intake(repo, report_path)
    return {"accepted": False, "errors": [], "warnings": [], "decision": decision, "spot_dim": spot_dim, "spot_result": spot_result}
