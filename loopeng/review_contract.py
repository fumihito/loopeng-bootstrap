from __future__ import annotations

CONTRACT_VERSION = 1
REVIEW_DIMENSIONS = ("D1", "D2", "D3", "D4", "D5")
REVIEWER_RELATIONS = ("external", "self-family")
DIMENSION_DESCRIPTIONS = {
    "D1": "process consistency",
    "D2": "outcome validity",
    "D3": "memory-write quality",
    "D4": "alert handling",
    "D5": "implementation claim inspection",
}
VERDICTS = ("pass", "fail", "unable")
OVERALLS = ("pass", "fail", "blocked-on-info")


def validate_contract(value: object) -> list[str]:
    errors: list[str] = []
    if not isinstance(value, dict):
        return ["report must be an object"]
    if value.get("contract") != CONTRACT_VERSION:
        errors.append(f"contract must be {CONTRACT_VERSION}")
    reviewer = value.get("reviewer")
    if not isinstance(reviewer, dict) or not all(isinstance(reviewer.get(key), str) and reviewer[key] for key in ("model", "session", "relation")):
        errors.append("reviewer.model/session/relation are required strings")
    elif reviewer.get("relation") not in REVIEWER_RELATIONS:
        errors.append("reviewer.relation must be external or self-family")
    packet = value.get("packet")
    if not isinstance(packet, dict) or not isinstance(packet.get("run_id"), str) or not isinstance(packet.get("packet_hash"), str):
        errors.append("packet.run_id and packet.packet_hash are required strings")
    dimensions = value.get("dimensions")
    if not isinstance(dimensions, list):
        errors.append("dimensions must be a list")
        dimensions = []
    seen: set[str] = set()
    identifiers: list[str] = []
    for item in dimensions:
        if not isinstance(item, dict):
            errors.append("dimension must be an object")
            continue
        identifier = item.get("id")
        verdict = item.get("verdict")
        if identifier not in REVIEW_DIMENSIONS or identifier in seen:
            errors.append(f"invalid or duplicate dimension id: {identifier}")
        seen.add(str(identifier))
        identifiers.append(str(identifier))
        if verdict not in VERDICTS:
            errors.append(f"invalid verdict for {identifier}: {verdict}")
        evidence = item.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            if verdict != "unable":
                errors.append(f"{identifier} requires evidence")
        elif any(not isinstance(pointer, dict) or not isinstance(pointer.get("ref"), str) or not pointer["ref"] or not isinstance(pointer.get("note"), str) for pointer in evidence):
            errors.append(f"invalid evidence in {identifier}")
        if identifier == "D5" and verdict != "unable":
            if not any(isinstance(pointer, dict) and str(pointer.get("ref", "")).startswith("file:") for pointer in evidence or []):
                errors.append("D5 requires a file:path:line evidence pointer")
    if set(seen) != set(REVIEW_DIMENSIONS):
        errors.append("dimensions must contain D1 through D5 exactly once")
    elif tuple(identifiers) != REVIEW_DIMENSIONS:
        errors.append("dimensions must be ordered D1 through D5")
    if value.get("overall") not in OVERALLS:
        errors.append(f"invalid overall: {value.get('overall')}")
    if sum(1 for item in dimensions if isinstance(item, dict) and item.get("verdict") == "unable") >= 3 and value.get("overall") != "blocked-on-info":
        errors.append("three or more unable dimensions require overall blocked-on-info")
    meta = value.get("meta_review")
    if meta is not None and (not isinstance(meta, dict) or meta.get("decision") not in {"accept", "send-back", "defer"}):
        errors.append("meta_review.decision must be accept, send-back, or defer")
    if isinstance(meta, dict) and meta.get("decision") == "accept" and meta.get("spot_result") not in {"ok", "mismatch"}:
        errors.append("accepted meta_review requires spot_result ok or mismatch")
    if isinstance(meta, dict) and meta.get("decision") == "accept" and meta.get("spot_dim") not in REVIEW_DIMENSIONS:
        errors.append("accepted meta_review requires spot_dim D1 through D5")
    return errors
