#!/usr/bin/env python3
"""Deterministic, content-minimizing learning observability for loop-engineering turns."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

DEFAULT_POLICY: dict[str, Any] = {
    "window_turns": 50,
    "minimum_turns_for_health": 5,
    "minimum_eligible_turns_for_reuse": 3,
    "stale_after_turns": 12,
    "orphan_after_turns": 6,
    "unresolved_question_after_turns": 6,
    "minimum_observation_coverage": 0.9,
    "minimum_retrieval_coverage": 0.9,
    "degraded_reuse_rate_below": 0.25,
    "degraded_question_resolution_rate_below": 0.3,
    "unhealthy_recurrence_after_learning_rate_above": 0.4,
    "unhealthy_learning_debt_score": 12,
    "weights": {
        "missing_observation": 2,
        "overdue_question": 2,
        "orphan_lesson": 1,
        "stale_lesson": 1,
        "contradiction": 4,
        "harmful_reuse": 4,
        "recurrence_after_learning": 3,
        "unknown_lesson_reference": 2,
        "accepted_without_record": 4,
        "unassessed_reuse": 1,
        "weak_lesson_evidence": 2,
        "missing_learning_retrieval": 1,
        "unconsidered_relevant_lesson": 2,
        "missing_memory_retrieval": 1,
        "memory_commit_failure": 4,
        "accepted_memory_not_committed": 3,
    },
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def parse_timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def load_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def digest(value: Any) -> str:
    rendered = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def safe_list(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def safe_dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 4)


def normalize_prior_learning(value: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in safe_list(value):
        if not isinstance(item, dict):
            continue
        lesson_id = str(item.get("lesson_id") or "").strip()
        disposition = str(item.get("disposition") or "").upper()
        if not lesson_id or disposition not in {"APPLIED", "CHALLENGED", "REJECTED", "NOT_APPLICABLE"}:
            continue
        result.append({"lesson_id": lesson_id, "disposition": disposition})
    return result


def normalize_learning_retrieval(value: Any) -> dict[str, Any]:
    body = safe_dict(value)
    candidates = [str(v) for v in safe_list(body.get("candidate_lesson_ids")) if str(v).strip()]
    relevant = [str(v) for v in safe_list(body.get("relevant_lesson_ids")) if str(v).strip()]
    return {
        "performed": bool(body.get("performed")),
        "candidate_lesson_ids": candidates,
        "relevant_lesson_ids": relevant,
        "unavailable": bool(body.get("unavailable_reason")),
    }


def normalize_learning_records(value: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in safe_list(value):
        if not isinstance(item, dict):
            continue
        lesson_id = str(item.get("lesson_id") or "").strip()
        if not lesson_id:
            continue
        status = str(item.get("status") or "PROPOSED").upper()
        kind = str(item.get("kind") or "OTHER").upper()
        statement = str(item.get("statement") or "")
        result.append({
            "lesson_id": lesson_id,
            "kind": kind,
            "status": status,
            "statement_digest": digest(statement),
            "confidence": item.get("confidence"),
            "supersedes": [str(v) for v in safe_list(item.get("supersedes")) if str(v).strip()],
            "review_after_turns": int(item.get("review_after_turns", 0) or 0),
            "evidence_count": len(safe_list(item.get("evidence_refs"))),
            "has_applicability": bool(item.get("applicability")),
            "has_invalidation_conditions": bool(item.get("invalidation_conditions")),
        })
    return result


def normalize_question_updates(value: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in safe_list(value):
        if isinstance(item, str):
            question_id = "Q-" + digest(item)[:16]
            result.append({"question_id": question_id, "status": "OPEN"})
            continue
        if not isinstance(item, dict):
            continue
        question_id = str(item.get("question_id") or "").strip()
        status = str(item.get("status") or "OPEN").upper()
        if question_id and status in {"OPEN", "ANSWERED", "DEFERRED", "INVALIDATED"}:
            result.append({"question_id": question_id, "status": status})
    return result


def normalize_learning_assessment(value: Any) -> dict[str, Any]:
    body = safe_dict(value)
    result: dict[str, Any] = {}
    for key in ("accepted_lesson_ids", "rejected_lesson_ids", "challenged_lesson_ids", "superseded_lesson_ids"):
        result[key] = [str(v) for v in safe_list(body.get(key)) if str(v).strip()]
    reuse: list[dict[str, str]] = []
    for item in safe_list(body.get("reuse_assessment")):
        if not isinstance(item, dict):
            continue
        lesson_id = str(item.get("lesson_id") or "").strip()
        outcome = str(item.get("outcome") or "UNVERIFIED").upper()
        if lesson_id and outcome in {"HELPFUL", "NEUTRAL", "HARMFUL", "UNVERIFIED"}:
            reuse.append({"lesson_id": lesson_id, "outcome": outcome})
    result["reuse_assessment"] = reuse
    changes: list[dict[str, str]] = []
    for item in safe_list(body.get("evaluation_changes")):
        if not isinstance(item, dict):
            continue
        change_id = str(item.get("change_id") or "").strip()
        status = str(item.get("status") or "PROPOSED").upper()
        if change_id and status in {"PROPOSED", "ACCEPTED", "REJECTED", "DEFERRED"}:
            changes.append({"change_id": change_id, "status": status})
    result["evaluation_changes"] = changes
    result["knowledge_gap_count"] = len(safe_list(body.get("knowledge_gaps")))
    return result



def normalize_memory_retrieval(value: Any) -> dict[str, Any]:
    body = safe_dict(value)
    return {
        "performed": bool(body.get("performed")),
        "candidate_concept_ids": [str(v) for v in safe_list(body.get("candidate_concept_ids")) if str(v).strip()],
        "relevant_concept_ids": [str(v) for v in safe_list(body.get("relevant_concept_ids")) if str(v).strip()],
        "deprecated_concept_ids": [str(v) for v in safe_list(body.get("deprecated_concept_ids")) if str(v).strip()],
        "unavailable": bool(body.get("unavailable_reason")),
    }


def normalize_memory_proposals(value: Any) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for item in safe_list(value):
        if not isinstance(item, dict):
            continue
        proposal_id = str(item.get("proposal_id") or "").strip()
        concept_id = str(item.get("concept_id") or "").strip()
        if proposal_id and concept_id:
            result.append({
                "proposal_id": proposal_id,
                "concept_id": concept_id,
                "action": str(item.get("action") or ""),
                "sensitivity": str(item.get("sensitivity") or ""),
                "evidence_count": len(safe_list(item.get("evidence_refs"))),
                "citation_count": len(safe_list(item.get("citations"))),
            })
    return result


def normalize_memory_assessment(value: Any) -> dict[str, Any]:
    body = safe_dict(value)
    return {
        "accepted_proposal_ids": [str(v) for v in safe_list(body.get("accepted_proposal_ids")) if str(v).strip()],
        "rejected_proposal_ids": [str(v) for v in safe_list(body.get("rejected_proposal_ids")) if str(v).strip()],
        "challenged_proposal_ids": [str(v) for v in safe_list(body.get("challenged_proposal_ids")) if str(v).strip()],
        "memory_gap_count": len(safe_list(body.get("memory_gaps"))),
    }


def normalize_memory_commit(value: Any) -> dict[str, Any]:
    body = safe_dict(value)
    return {
        "present": bool(body),
        "ok": bool(body.get("ok")),
        "status": str(body.get("status") or ""),
        "applied_count": len(safe_list(body.get("applied_concept_ids"))),
        "created_count": int(body.get("created_count", 0) or 0),
        "updated_count": int(body.get("updated_count", 0) or 0),
        "deprecated_count": int(body.get("deprecated_count", 0) or 0),
    }

def build_turn_observation(turn_path: Path) -> dict[str, Any]:
    state = safe_dict(load_json(turn_path / "turn.json", {}))
    sense = safe_dict(load_json(turn_path / "sensemaker.json", {}))
    steward = safe_dict(load_json(turn_path / "state-steward.json", {}))
    meta = safe_dict(load_json(turn_path / "meta-evaluator.json", {}))
    prior = normalize_prior_learning(sense.get("prior_learning_considered"))
    retrieval = normalize_learning_retrieval(sense.get("learning_retrieval"))
    lessons = normalize_learning_records(steward.get("learning_records"))
    questions = normalize_question_updates(steward.get("question_updates"))
    assessment = normalize_learning_assessment(meta.get("learning_assessment"))
    memory_retrieval = normalize_memory_retrieval(sense.get("memory_retrieval"))
    memory_proposals = normalize_memory_proposals(steward.get("memory_proposals"))
    memory_assessment = normalize_memory_assessment(meta.get("memory_assessment"))
    memory_commit = normalize_memory_commit(load_json(turn_path / "memory-commit.json", {}))
    expected = [
        bool(sense.get("problem_signature")),
        isinstance(sense.get("prior_learning_considered"), list),
        isinstance(sense.get("learning_retrieval"), dict),
        isinstance(steward.get("learning_records"), list),
        isinstance(steward.get("question_updates"), list),
        isinstance(meta.get("learning_assessment"), dict),
        isinstance(sense.get("memory_retrieval"), dict),
        isinstance(steward.get("memory_proposals"), list),
        isinstance(meta.get("memory_assessment"), dict),
        not memory_assessment["accepted_proposal_ids"] or memory_commit["ok"],
    ]
    return {
        "schema_version": 1,
        "turn_id": turn_path.name,
        "session_ref": digest(str(state.get("session_id") or "unknown"))[:16],
        "started_at": state.get("started_at"),
        "completed_at": state.get("completed_at"),
        "final_status": state.get("final_status"),
        "routing_mode": state.get("routing_mode"),
        "problem_signature": str(sense.get("problem_signature") or ""),
        "prior_learning_considered": prior,
        "learning_retrieval": retrieval,
        "learning_records": lessons,
        "question_updates": questions,
        "learning_assessment": assessment,
        "memory_retrieval": memory_retrieval,
        "memory_proposals": memory_proposals,
        "memory_assessment": memory_assessment,
        "memory_commit": memory_commit,
        "meta_verdict": meta.get("verdict"),
        "tool_calls": int(state.get("tool_calls", 0) or 0),
        "mutations": int(state.get("mutations", 0) or 0),
        "failures": int(state.get("failures", 0) or 0),
        "watchdog_tripped": bool(safe_dict(state.get("watchdog")).get("tripped")),
        "observation_complete": all(expected),
        "observed_at": utc_now(),
    }


def turn_paths(root: Path) -> list[Path]:
    base = root / ".agent-loop/runtime/turns"
    paths = [p for p in base.glob("*") if p.is_dir()]
    def key(path: Path) -> tuple[str, str]:
        state = safe_dict(load_json(path / "turn.json", {}))
        return str(state.get("started_at") or ""), path.name
    return sorted(paths, key=key)


def completed_loop_turns(root: Path) -> list[Path]:
    result: list[Path] = []
    for path in turn_paths(root):
        state = safe_dict(load_json(path / "turn.json", {}))
        if state.get("routing_mode") == "LOOP" and state.get("final_status") == "PASS":
            result.append(path)
    return result


def persist_turn_observation(root: Path, turn_path: Path) -> dict[str, Any]:
    observation = build_turn_observation(turn_path)
    atomic_json(turn_path / "learning-observation.json", observation)
    state_dir = root / ".agent-loop/state/learning/turns"
    atomic_json(state_dir / f"{observation['turn_id']}.json", observation)
    return observation


def _first_status(events: list[dict[str, Any]], status: str) -> int | None:
    for event in events:
        if event.get("status") == status:
            return int(event["turn_index"])
    return None


def compute_health(records: list[dict[str, Any]], policy: dict[str, Any], window: int | None = None, *, include_trend: bool = True) -> dict[str, Any]:
    records = sorted(records, key=lambda r: (str(r.get("started_at") or ""), str(r.get("turn_id") or "")))
    total_all = len(records)
    configured_window = int(window or policy.get("window_turns", 50))
    window_records = records[-configured_window:] if configured_window > 0 else records
    window_start_index = max(0, total_all - len(window_records))

    lesson_events: dict[str, list[dict[str, Any]]] = {}
    lesson_meta: dict[str, dict[str, Any]] = {}
    question_state: dict[str, dict[str, Any]] = {}
    known_accepted: set[str] = set()
    signature_prior: dict[str, dict[str, Any]] = {}

    eligible_turns = 0
    reuse_turns = 0
    retrieval_turns = 0
    considered_events = 0
    unconsidered_relevant_lessons = 0
    helpful_reuse = 0
    neutral_reuse = 0
    harmful_reuse = 0
    unverified_reuse = 0
    recurrence_count = 0
    recurrence_after_learning = 0
    accepted_evaluation_changes = 0
    turns_with_accepted_lessons = 0
    proposed_count = 0
    accepted_count = 0
    rejected_count = 0
    challenged_count = 0
    superseded_count = 0
    complete_count = 0
    lesson_id_collisions = 0
    unknown_lesson_references = 0
    accepted_without_record = 0
    unassessed_reuse_events = 0
    weak_lesson_evidence = 0
    missing_learning_retrieval = 0
    first_reuse_turn: dict[str, int] = {}
    validation_turn: dict[str, int] = {}
    memory_retrieval_turns = 0
    missing_memory_retrieval = 0
    memory_proposal_count = 0
    accepted_memory_proposal_count = 0
    committed_memory_concept_count = 0
    accepted_memory_not_committed = 0
    memory_commit_failures = 0

    for index, record in enumerate(records):
        in_window = index >= window_start_index
        prior_known = set(known_accepted)
        considered = safe_list(record.get("prior_learning_considered"))
        retrieval = safe_dict(record.get("learning_retrieval"))
        relevant_ids = {str(v) for v in safe_list(retrieval.get("relevant_lesson_ids")) if str(v)}
        candidate_ids = {str(v) for v in safe_list(retrieval.get("candidate_lesson_ids")) if str(v)}
        considered_ids = {str(item.get("lesson_id") or "") for item in considered if isinstance(item, dict)}
        if in_window and retrieval.get("performed"):
            retrieval_turns += 1
        elif in_window:
            missing_learning_retrieval += 1
        if in_window and relevant_ids:
            eligible_turns += 1
            if considered_ids & relevant_ids:
                reuse_turns += 1
            unconsidered_relevant_lessons += len(relevant_ids - considered_ids)
        if in_window and considered:
            considered_events += len(considered)
        for lesson_id in candidate_ids | relevant_ids:
            if lesson_id not in lesson_meta and lesson_id not in prior_known and in_window:
                unknown_lesson_references += 1
        for item in considered:
            lesson_id = str(item.get("lesson_id") or "")
            if lesson_id and lesson_id not in first_reuse_turn:
                first_reuse_turn[lesson_id] = index
            if lesson_id:
                lesson_events.setdefault(lesson_id, []).append({"turn_index": index, "status": "CONSIDERED_" + str(item.get("disposition") or "UNKNOWN")})
        if in_window and record.get("observation_complete"):
            complete_count += 1
        memory_retrieval = safe_dict(record.get("memory_retrieval"))
        memory_proposals = safe_list(record.get("memory_proposals"))
        memory_assessment = safe_dict(record.get("memory_assessment"))
        memory_commit = safe_dict(record.get("memory_commit"))
        if in_window and memory_retrieval.get("performed"):
            memory_retrieval_turns += 1
        elif in_window:
            missing_memory_retrieval += 1
        if in_window:
            memory_proposal_count += len(memory_proposals)
            accepted_memory = len(safe_list(memory_assessment.get("accepted_proposal_ids")))
            accepted_memory_proposal_count += accepted_memory
            committed_memory_concept_count += int(memory_commit.get("applied_count", 0) or 0)
            if accepted_memory and not memory_commit.get("ok"):
                accepted_memory_not_committed += accepted_memory
                if memory_commit.get("present"):
                    memory_commit_failures += 1

        signature = str(record.get("problem_signature") or "")
        previous_signature = signature_prior.get(signature) if signature else None
        if previous_signature is not None and in_window:
            recurrence_count += 1
            if previous_signature.get("accepted_lessons"):
                recurrence_after_learning += 1

        turn_accepted: set[str] = set()
        assessment = safe_dict(record.get("learning_assessment"))
        accepted_ids = set(str(v) for v in safe_list(assessment.get("accepted_lesson_ids")))
        rejected_ids = set(str(v) for v in safe_list(assessment.get("rejected_lesson_ids")))
        challenged_ids = set(str(v) for v in safe_list(assessment.get("challenged_lesson_ids")))
        superseded_ids = set(str(v) for v in safe_list(assessment.get("superseded_lesson_ids")))

        for lesson in safe_list(record.get("learning_records")):
            if not isinstance(lesson, dict):
                continue
            lesson_id = str(lesson.get("lesson_id") or "")
            if not lesson_id:
                continue
            metadata = lesson_meta.setdefault(lesson_id, {
                "first_seen_turn": index,
                "last_seen_turn": index,
                "statement_digest": lesson.get("statement_digest"),
                "kind": lesson.get("kind"),
                "review_after_turns": int(lesson.get("review_after_turns", 0) or 0),
                "evidence_count": int(lesson.get("evidence_count", 0) or 0),
                "has_applicability": bool(lesson.get("has_applicability")),
                "has_invalidation_conditions": bool(lesson.get("has_invalidation_conditions")),
            })
            metadata["last_seen_turn"] = index
            metadata["review_after_turns"] = int(lesson.get("review_after_turns", 0) or metadata.get("review_after_turns", 0))
            if in_window and (int(lesson.get("evidence_count", 0) or 0) <= 0 or not lesson.get("has_applicability") or not lesson.get("has_invalidation_conditions")):
                weak_lesson_evidence += 1
            if metadata.get("statement_digest") and lesson.get("statement_digest") != metadata.get("statement_digest"):
                lesson_id_collisions += 1
            event_status = str(lesson.get("status") or "PROPOSED").upper()
            lesson_events.setdefault(lesson_id, []).append({"turn_index": index, "status": event_status})
            if in_window and event_status == "PROPOSED":
                proposed_count += 1

        for lesson_id in accepted_ids:
            if lesson_id not in lesson_meta and in_window:
                accepted_without_record += 1
            lesson_events.setdefault(lesson_id, []).append({"turn_index": index, "status": "VALIDATED"})
            validation_turn.setdefault(lesson_id, index)
            known_accepted.add(lesson_id)
            turn_accepted.add(lesson_id)
            if in_window:
                accepted_count += 1
        for lesson_id in rejected_ids:
            lesson_events.setdefault(lesson_id, []).append({"turn_index": index, "status": "REJECTED"})
            known_accepted.discard(lesson_id)
            if in_window:
                rejected_count += 1
        for lesson_id in challenged_ids:
            lesson_events.setdefault(lesson_id, []).append({"turn_index": index, "status": "CHALLENGED"})
            if in_window:
                challenged_count += 1
        for lesson_id in superseded_ids:
            lesson_events.setdefault(lesson_id, []).append({"turn_index": index, "status": "SUPERSEDED"})
            known_accepted.discard(lesson_id)
            if in_window:
                superseded_count += 1

        if in_window and turn_accepted:
            turns_with_accepted_lessons += 1
        if signature:
            prior_signature_lessons = set(previous_signature.get("accepted_lessons", set())) if previous_signature else set()
            signature_prior[signature] = {
                "turn_index": index,
                "accepted_lessons": prior_signature_lessons | set(turn_accepted),
            }

        assessed_ids: set[str] = set()
        for item in safe_list(assessment.get("reuse_assessment")):
            if not isinstance(item, dict) or not in_window:
                continue
            lesson_id = str(item.get("lesson_id") or "")
            if lesson_id:
                assessed_ids.add(lesson_id)
            outcome = str(item.get("outcome") or "UNVERIFIED").upper()
            if lesson_id:
                lesson_events.setdefault(lesson_id, []).append({"turn_index": index, "status": "REUSE_" + outcome})
            if outcome == "HELPFUL":
                helpful_reuse += 1
            elif outcome == "NEUTRAL":
                neutral_reuse += 1
            elif outcome == "HARMFUL":
                harmful_reuse += 1
            else:
                unverified_reuse += 1
        if in_window:
            required_assessment_ids = {str(item.get("lesson_id") or "") for item in considered if item.get("disposition") in {"APPLIED", "CHALLENGED"}}
            unassessed_reuse_events += len({item for item in required_assessment_ids if item and item not in assessed_ids})

        for change in safe_list(assessment.get("evaluation_changes")):
            if isinstance(change, dict) and in_window and change.get("status") == "ACCEPTED":
                accepted_evaluation_changes += 1

        for update in safe_list(record.get("question_updates")):
            if not isinstance(update, dict):
                continue
            qid = str(update.get("question_id") or "")
            if not qid:
                continue
            existing = question_state.setdefault(qid, {"opened_turn": index, "status": "OPEN", "last_turn": index})
            existing["status"] = str(update.get("status") or "OPEN")
            existing["last_turn"] = index

    final_index = max(total_all - 1, 0)
    stale_after = int(policy.get("stale_after_turns", 12))
    orphan_after = int(policy.get("orphan_after_turns", 6))
    overdue_after = int(policy.get("unresolved_question_after_turns", 6))

    stale_lessons: list[str] = []
    orphan_lessons: list[str] = []
    for lesson_id, events in lesson_events.items():
        validated_at = _first_status(events, "VALIDATED")
        terminal = any(e.get("status") in {"REJECTED", "SUPERSEDED"} for e in events)
        last_active = max(int(e["turn_index"]) for e in events)
        if validated_at is not None and not terminal:
            review_after = int(lesson_meta.get(lesson_id, {}).get("review_after_turns", 0) or stale_after)
            if final_index - last_active >= review_after:
                stale_lessons.append(lesson_id)
        if validated_at is None and not terminal:
            first = min(int(e["turn_index"]) for e in events)
            if final_index - first >= orphan_after:
                orphan_lessons.append(lesson_id)

    overdue_questions = [
        qid for qid, state in question_state.items()
        if state.get("status") in {"OPEN", "DEFERRED"}
        and final_index - int(state.get("opened_turn", final_index)) >= overdue_after
    ]
    answered_questions = sum(1 for state in question_state.values() if state.get("status") == "ANSWERED")
    introduced_questions = len(question_state)

    window_total = len(window_records)
    coverage = ratio(complete_count, window_total)
    retrieval_coverage = ratio(retrieval_turns, window_total)
    memory_retrieval_coverage = ratio(memory_retrieval_turns, window_total)
    memory_promotion_completion_rate = ratio(committed_memory_concept_count, accepted_memory_proposal_count)
    capture_rate = ratio(turns_with_accepted_lessons, window_total)
    reuse_rate = ratio(reuse_turns, eligible_turns)
    assessed_reuse = helpful_reuse + neutral_reuse + harmful_reuse
    helpful_reuse_rate = ratio(helpful_reuse, assessed_reuse)
    question_resolution_rate = ratio(answered_questions, introduced_questions)
    repeated_signatures = recurrence_count
    recurrence_after_learning_rate = ratio(recurrence_after_learning, repeated_signatures)
    evaluation_adaptation_rate = ratio(accepted_evaluation_changes, window_total)
    knowledge_correction_rate = ratio(rejected_count + challenged_count + superseded_count, accepted_count)
    validated_lifetime = len(validation_turn)
    validated_reused = sum(1 for lesson_id in validation_turn if lesson_id in first_reuse_turn and first_reuse_turn[lesson_id] > validation_turn[lesson_id])
    learning_chain_completion_rate = ratio(validated_reused, validated_lifetime)
    reuse_latencies = [first_reuse_turn[lesson_id] - turn_index for lesson_id, turn_index in validation_turn.items() if lesson_id in first_reuse_turn and first_reuse_turn[lesson_id] > turn_index]
    average_turns_to_first_reuse = round(sum(reuse_latencies) / len(reuse_latencies), 2) if reuse_latencies else None

    weights = {**DEFAULT_POLICY["weights"], **safe_dict(policy.get("weights"))}
    missing_observation = max(0, window_total - complete_count)
    debt_components = {
        "missing_observation": missing_observation,
        "overdue_question": len(overdue_questions),
        "orphan_lesson": len(orphan_lessons),
        "stale_lesson": len(stale_lessons),
        "contradiction": lesson_id_collisions,
        "harmful_reuse": harmful_reuse,
        "recurrence_after_learning": recurrence_after_learning,
        "unknown_lesson_reference": unknown_lesson_references,
        "accepted_without_record": accepted_without_record,
        "unassessed_reuse": unassessed_reuse_events,
        "weak_lesson_evidence": weak_lesson_evidence,
        "missing_learning_retrieval": missing_learning_retrieval,
        "unconsidered_relevant_lesson": unconsidered_relevant_lessons,
        "missing_memory_retrieval": missing_memory_retrieval,
        "memory_commit_failure": memory_commit_failures,
        "accepted_memory_not_committed": accepted_memory_not_committed,
    }
    debt_score = sum(int(weights.get(key, 1)) * count for key, count in debt_components.items())

    reasons: list[str] = []
    minimum_turns = int(policy.get("minimum_turns_for_health", 5))
    minimum_eligible = int(policy.get("minimum_eligible_turns_for_reuse", 3))
    unhealthy = False
    degraded = False
    if lesson_id_collisions > 0:
        unhealthy = True
        reasons.append("lesson identifiers changed meaning without explicit supersession")
    if harmful_reuse > 0:
        unhealthy = True
        reasons.append("previous learning was assessed as harmful")
    if accepted_without_record > 0:
        unhealthy = True
        reasons.append("lesson identifiers were accepted without a corresponding structured record")
    if recurrence_after_learning_rate is not None and recurrence_after_learning_rate > float(policy.get("unhealthy_recurrence_after_learning_rate_above", 0.4)):
        unhealthy = True
        reasons.append("problem signatures recur after validated learning")
    if debt_score >= int(policy.get("unhealthy_learning_debt_score", 12)):
        unhealthy = True
        reasons.append("learning debt exceeded the configured threshold")
    if unknown_lesson_references > 0:
        degraded = True
        reasons.append("turns referenced lessons that were not present in prior learning state")
    if unassessed_reuse_events > 0:
        degraded = True
        reasons.append("applied or challenged lessons were not assessed for reuse outcome")
    if weak_lesson_evidence > 0:
        degraded = True
        reasons.append("learning records lack evidence, applicability, or invalidation conditions")
    if coverage is not None and coverage < float(policy.get("minimum_observation_coverage", 0.9)):
        degraded = True
        reasons.append("learning observation coverage is incomplete")
    if retrieval_coverage is not None and retrieval_coverage < float(policy.get("minimum_retrieval_coverage", 0.9)):
        degraded = True
        reasons.append("prior-learning retrieval was not performed consistently")
    if memory_retrieval_coverage is not None and memory_retrieval_coverage < float(policy.get("minimum_memory_retrieval_coverage", 0.9)):
        degraded = True
        reasons.append("OKF LLMWiki retrieval was not performed consistently")
    if accepted_memory_not_committed > 0:
        unhealthy = True
        reasons.append("accepted durable-memory proposals were not committed transactionally")
    if memory_commit_failures > 0:
        unhealthy = True
        reasons.append("deterministic OKF memory commits failed")
    if unconsidered_relevant_lessons > 0:
        degraded = True
        reasons.append("relevant retrieved lessons were not explicitly considered")
    if eligible_turns >= minimum_eligible and reuse_rate is not None and reuse_rate < float(policy.get("degraded_reuse_rate_below", 0.25)):
        degraded = True
        reasons.append("validated learning is rarely considered in later turns")
    if introduced_questions > 0 and question_resolution_rate is not None and question_resolution_rate < float(policy.get("degraded_question_resolution_rate_below", 0.3)):
        degraded = True
        reasons.append("open questions are not being resolved")
    if stale_lessons:
        degraded = True
        reasons.append("validated lessons have become stale without review or reuse")
    if orphan_lessons:
        degraded = True
        reasons.append("proposed lessons remain unvalidated")
    if unhealthy:
        health = "UNHEALTHY"
    elif window_total < minimum_turns:
        health = "UNKNOWN"
        reasons.insert(0, "insufficient completed loop turns")
    else:
        health = "DEGRADED" if degraded else "HEALTHY"

    result = {
        "schema_version": 1,
        "generated_at": utc_now(),
        "health": health,
        "reasons": reasons,
        "window": {
            "configured_turns": configured_window,
            "observed_turns": window_total,
            "all_completed_turns": total_all,
        },
        "metrics": {
            "observation_coverage": coverage,
            "learning_retrieval_coverage": retrieval_coverage,
            "memory_retrieval_coverage": memory_retrieval_coverage,
            "memory_proposal_count": memory_proposal_count,
            "accepted_memory_proposal_count": accepted_memory_proposal_count,
            "committed_memory_concept_count": committed_memory_concept_count,
            "memory_promotion_completion_rate": memory_promotion_completion_rate,
            "memory_commit_failure_count": memory_commit_failures,
            "accepted_memory_not_committed_count": accepted_memory_not_committed,
            "knowledge_capture_rate": capture_rate,
            "eligible_turns_for_reuse": eligible_turns,
            "turns_considering_prior_learning": reuse_turns,
            "learning_reuse_rate": reuse_rate,
            "considered_learning_events": considered_events,
            "unknown_lesson_reference_count": unknown_lesson_references,
            "missing_learning_retrieval_count": missing_learning_retrieval,
            "unconsidered_relevant_lesson_count": unconsidered_relevant_lessons,
            "unassessed_reuse_count": unassessed_reuse_events,
            "learning_chain_completion_rate": learning_chain_completion_rate,
            "average_turns_to_first_reuse": average_turns_to_first_reuse,
            "helpful_reuse_rate": helpful_reuse_rate,
            "helpful_reuse_count": helpful_reuse,
            "neutral_reuse_count": neutral_reuse,
            "harmful_reuse_count": harmful_reuse,
            "unverified_reuse_count": unverified_reuse,
            "problem_signature_recurrence_count": recurrence_count,
            "recurrence_after_learning_count": recurrence_after_learning,
            "recurrence_after_learning_rate": recurrence_after_learning_rate,
            "accepted_lesson_count": accepted_count,
            "proposed_lesson_count": proposed_count,
            "rejected_lesson_count": rejected_count,
            "challenged_lesson_count": challenged_count,
            "superseded_lesson_count": superseded_count,
            "knowledge_correction_rate": knowledge_correction_rate,
            "stale_lesson_count": len(stale_lessons),
            "orphan_lesson_count": len(orphan_lessons),
            "lesson_identifier_collision_count": lesson_id_collisions,
            "accepted_without_record_count": accepted_without_record,
            "weak_lesson_evidence_count": weak_lesson_evidence,
            "open_question_count": sum(1 for state in question_state.values() if state.get("status") in {"OPEN", "DEFERRED"}),
            "overdue_question_count": len(overdue_questions),
            "question_resolution_rate": question_resolution_rate,
            "accepted_evaluation_change_count": accepted_evaluation_changes,
            "evaluation_adaptation_rate": evaluation_adaptation_rate,
            "learning_debt_score": debt_score,
        },
        "debt_components": debt_components,
        "sets": {
            "stale_lesson_ids": sorted(stale_lessons),
            "orphan_lesson_ids": sorted(orphan_lessons),
            "overdue_question_ids": sorted(overdue_questions),
        },
        "interpretation_limits": [
            "Metric association does not prove that a reused lesson caused the outcome.",
            "A recurring problem signature may represent a legitimate repeated task rather than a failed lesson.",
            "Low correction counts are not automatically positive; they may indicate missing challenge behavior.",
            "Textual similarity and embeddings are intentionally not used by the deterministic observer.",
        ],
    }
    if include_trend and configured_window > 0 and total_all >= configured_window * 2:
        previous = compute_health(records[:-configured_window], policy, window=configured_window, include_trend=False)
        previous_metrics = safe_dict(previous.get("metrics"))
        current_metrics = safe_dict(result.get("metrics"))
        comparable = [
            "observation_coverage", "learning_retrieval_coverage", "learning_reuse_rate", "helpful_reuse_rate",
            "recurrence_after_learning_rate", "question_resolution_rate",
            "evaluation_adaptation_rate", "memory_retrieval_coverage",
            "memory_promotion_completion_rate", "learning_debt_score",
        ]
        deltas: dict[str, float | int | None] = {}
        for key in comparable:
            current_value = current_metrics.get(key)
            previous_value = previous_metrics.get(key)
            if isinstance(current_value, (int, float)) and not isinstance(current_value, bool) and isinstance(previous_value, (int, float)) and not isinstance(previous_value, bool):
                deltas[key] = round(float(current_value) - float(previous_value), 4)
            else:
                deltas[key] = None
        result["trend"] = {
            "comparison_available": True,
            "previous_health": previous.get("health"),
            "metric_deltas": deltas,
        }
    else:
        result["trend"] = {"comparison_available": False, "previous_health": None, "metric_deltas": {}}
    return result


def rebuild(root: Path, window: int | None = None) -> dict[str, Any]:
    policy = {**DEFAULT_POLICY, **safe_dict(load_json(root / ".agent-loop/learning-policy.json", {}))}
    records: list[dict[str, Any]] = []
    history_start_at = policy.get("history_start_at")
    for path in completed_loop_turns(root):
        state = safe_dict(load_json(path / "turn.json", {}))
        if history_start_at:
            baseline = parse_timestamp(history_start_at)
            started = parse_timestamp(state.get("started_at"))
            if baseline is not None and (started is None or started < baseline):
                continue
        observation = persist_turn_observation(root, path)
        records.append(observation)
    summary = compute_health(records, policy, window=window)
    state_root = root / ".agent-loop/state/learning"
    atomic_json(state_root / "learning-health.json", summary)
    atomic_json(state_root / "learning-index.json", {
        "schema_version": 1,
        "generated_at": summary["generated_at"],
        "turn_ids": [str(r.get("turn_id")) for r in records],
        "observation_digests": {str(r.get("turn_id")): digest(r) for r in records},
    })
    return summary


def observe_completed_turn(root: Path, turn_path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    observation = persist_turn_observation(root, turn_path)
    summary = rebuild(root)
    return observation, summary


def markdown_report(summary: dict[str, Any]) -> str:
    metrics = safe_dict(summary.get("metrics"))
    lines = [
        "# Learning health report",
        "",
        f"- Health: {summary.get('health', 'UNKNOWN')}",
        f"- Generated: {summary.get('generated_at', '')}",
        f"- Observed turns: {safe_dict(summary.get('window')).get('observed_turns', 0)}",
        f"- Observation coverage: {metrics.get('observation_coverage')}",
        f"- Learning reuse rate: {metrics.get('learning_reuse_rate')}",
        f"- Helpful reuse rate: {metrics.get('helpful_reuse_rate')}",
        f"- Memory retrieval coverage: {metrics.get('memory_retrieval_coverage')}",
        f"- Memory promotion completion: {metrics.get('memory_promotion_completion_rate')}",
        f"- Memory commit failures: {metrics.get('memory_commit_failure_count')}",
        f"- Recurrence after learning: {metrics.get('recurrence_after_learning_count')}",
        f"- Overdue questions: {metrics.get('overdue_question_count')}",
        f"- Stale lessons: {metrics.get('stale_lesson_count')}",
        f"- Learning debt score: {metrics.get('learning_debt_score')}",
        "",
        "## Reasons",
    ]
    reasons = safe_list(summary.get("reasons"))
    lines.extend([f"- {reason}" for reason in reasons] or ["- No configured degradation reason was detected."])
    lines.extend(["", "## Interpretation limits"])
    lines.extend(f"- {item}" for item in safe_list(summary.get("interpretation_limits")))
    return "\n".join(lines) + "\n"
