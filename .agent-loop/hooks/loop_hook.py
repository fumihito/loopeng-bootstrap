#!/usr/bin/env python3
"""Deterministic lifecycle hook and sanitized OTel exporter for Codex and Claude Code."""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROLES = {
    "gatekeeper": ({"role","verdict","mode","condition_checklist","normalized_loop_brief","missing_conditions","ambiguities","questions_to_user","risk_class","rejection_reasons","handoff_to_loop_brief_assistant","assistant_handoff_reason","handoff_to_sensemaker","brief_pattern_directive","brief_pattern_assessment"}, "gatekeeper.json"),
    "loop-brief-assistant": ({"role","status","interaction_mode","draft_loop_brief","resolved_conditions","remaining_conditions","assumptions","questions_to_user","conflicts","handoff_to_gatekeeper","pattern_retrieval","pattern_application","pattern_proposals"}, "loop-brief-assistant.json"),
    "sensemaker": ({"role","problem_frame","problem_signature","observations","inferences","alternative_frames","acceptance_criteria","non_goals","risks","recommended_action","prior_learning_considered","learning_retrieval","memory_retrieval","hypothesis_updates"}, "sensemaker.json"),
    "integrator": ({"role","status","inputs","merged_result","conflicts","resolution_strategy","handoff_to_evaluator"}, "integrator.json"),
    "governor": ({"role","classification","reasons","constraints","approval_scope"}, "governor.json"),
    "state-steward": ({"role","facts","inferences","decisions","open_questions","artifacts","next_state","learning_records","question_updates","memory_proposals"}, "state-steward.json"),
    "watchdog-recovery": ({"role","status","trigger","root_cause_hypotheses","safe_checkpoint","recovery_steps","human_action_required"}, "watchdog-recovery.json"),
    "meta-evaluator": ({"role","verdict","evaluation_basis","evidence","assumption_failures","metric_gaming_risk","unverified","required_actions","learning_assessment","memory_assessment"}, "meta-evaluator.json"),
    "learning-auditor": ({"role","verdict","window","evidence_quality","learning_metrics_assessment","recurrence_findings","reuse_findings","knowledge_debt_findings","adaptation_findings","memory_findings","systemic_patterns","recommended_policy_changes","human_review_required"}, "learning-auditor.json"),
    "memory-curator": ({"role","status","processed_proposal_ids","operations","skipped_proposals","conflicts","validation_expectations"}, "memory-curator.json"),
    "brief-pattern-curator": ({"role","status","processed_proposal_ids","operations","skipped_proposals","conflicts","validation_expectations"}, "brief-pattern-curator.json"),
}
SHELL_CONTROL = {";", "&&", "||", "|", "&", "(", ")", "then", "do", "else", "elif", "fi", "done"}
SHELL_KEYWORDS = {"if", "for", "while", "until", "case", "select", "function", "time", "coproc", "!", "{", "}"}
SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._+:-]{0,79}$")
LEARNING_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,119}$")
CONCEPT_ID = re.compile(r"^[a-z0-9][a-z0-9._/-]{0,239}$")
GATEKEEPER_VERDICTS = {"READY", "NEEDS_INPUT", "REJECT"}
CONTINUATION_MARKER = "[AGENT_LOOP_CONTINUE]"
LOOP_BRIEF_FIELDS = {
    "outcome", "discovery_scope", "authority_envelope", "evaluation_contract",
    "persistence_contract", "learning_contract", "memory_contract", "stop_conditions", "escalation_contract", "trigger_cadence",
}
SOP_HEADER_PATTERN = re.compile(r"^([a-z][a-z0-9-]{0,31}):(?!//)[ \t]*(.*)$", re.S)
DIRECT_HEADER_PATTERN = re.compile(r"^direct:[ \t]*(.*)$", re.S)
SOP_ROUTING_MODE = "SOP"
FRAME_ROUTING_MODE = "FRAME"
DIRECT_ROUTING_MODE = "DIRECT"
LOOP_ROUTING_MODE = "LOOP"
LEARNING_AUDIT_SKILL = "sop-learning-audit"
MEMORY_CURATOR_ROLE = "memory-curator"
BRIEF_PATTERN_CURATOR_ROLE = "brief-pattern-curator"
LOOP_BRIEF_ASSISTANT_ROLE = "loop-brief-assistant"
INTEGRATOR_ROLE = "integrator"
LOOP_BRIEF_ASSISTANT_STATUSES = {"ASK_USER", "READY_FOR_REVIEW", "BLOCKED"}
INTEGRATOR_STATUSES = {"MERGED", "BLOCKED", "NO_CHANGE"}
LOOP_BRIEF_ASSISTANT_MODES = {"CLARIFY", "PATTERN_CAPTURE"}
BRIEF_PATTERN_ACTIONS = {"NONE", "CAPTURE"}
BRIEF_PATTERN_HANDOFF_REASONS = {"MISSING_INPUT", "PATTERN_CAPTURE", "NONE"}


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def now_ns() -> str:
    return str(time.time_ns())


def emit(value: dict[str, Any]) -> int:
    sys.stdout.write(json.dumps(value, ensure_ascii=False))
    return 0


def read_event() -> dict[str, Any]:
    raw = sys.stdin.read()
    try:
        value = json.loads(raw) if raw.strip() else {}
        return value if isinstance(value, dict) else {}
    except json.JSONDecodeError:
        return {}


def root_for(cwd: str | None = None) -> Path:
    path = Path(cwd or os.getcwd()).resolve()
    for candidate in (path, *path.parents):
        if (candidate / ".agent-loop/policy.json").exists():
            return candidate
    return path


def load(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def atomic(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    temporary.replace(path)


def append_jsonl(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(value, ensure_ascii=False) + "\n")


def safe(value: Any) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", str(value or "unknown"))[:120]


def safe_identity(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if "/" in candidate or "\\" in candidate:
        return None
    return candidate if SAFE_NAME.fullmatch(candidate) else None


def session_path(root: Path, event: dict[str, Any]) -> Path:
    return root / ".agent-loop/runtime/sessions" / f"{safe(event.get('session_id'))}.json"


def gatekeeper_session_path(root: Path, event: dict[str, Any]) -> Path:
    return root / ".agent-loop/runtime/gatekeeper-sessions" / f"{safe(event.get('session_id'))}.json"


def loop_brief_assistant_session_path(root: Path, event: dict[str, Any]) -> Path:
    return root / ".agent-loop/runtime/loop-brief-assistant-sessions" / f"{safe(event.get('session_id'))}.json"


def runtime(root: Path, event: dict[str, Any]) -> dict[str, Any]:
    return load(session_path(root, event), {})


def save_runtime(root: Path, event: dict[str, Any], value: dict[str, Any]) -> None:
    atomic(session_path(root, event), value)


def next_turn_handoff_path(root: Path, state: dict[str, Any]) -> Path:
    return turn_dir(root, state) / "next-turn.json"


def write_next_turn_handoff(root: Path, state: dict[str, Any]) -> dict[str, Any]:
    handoff = {
        "source_turn_id": state.get("turn_id"),
        "session_id": state.get("session_id"),
        "routing_mode": state.get("routing_mode"),
        "final_status": state.get("final_status"),
        "ready_for_next_turn": state.get("routing_mode") == LOOP_ROUTING_MODE and state.get("final_status") == "PASS",
        "next_entry_role": "gatekeeper",
        "trigger_kind": "external-user-prompt",
        "started_at": state.get("started_at"),
        "completed_at": state.get("completed_at"),
        "resume_hint": "Submit the next ordinary user message to enter Gatekeeper.",
    }
    atomic(next_turn_handoff_path(root, state), handoff)
    return handoff


def turn_dir(root: Path, state: dict[str, Any]) -> Path:
    return root / ".agent-loop/runtime/turns" / safe(state.get("turn_id"))


def matches(patterns: list[str], text: str) -> bool:
    return any(re.search(pattern, text, re.I | re.M) for pattern in patterns)


def direct_route(prompt: str) -> str | None:
    match = DIRECT_HEADER_PATTERN.match(prompt)
    return match.group(1) if match else None


def direct_config(root: Path) -> dict[str, Any]:
    config = load(root / ".agent-loop/direct-policy.json", {})
    return {
        "enabled": bool(config.get("enabled", True)),
        "allow_mutations": bool(config.get("allow_mutations", False)),
        "max_prompt_bytes": int(config.get("max_prompt_bytes", 65536)),
        "allow_loop_control_roles": bool(config.get("allow_loop_control_roles", False)),
    }


def sop_route(prompt: str) -> tuple[str, str, str] | None:
    """Return (header, skill_name, task_body) for a strict leading SOP header.

    A URI such as https://... is intentionally not treated as an SOP header.
    Headers are lowercase ASCII identifiers with optional digits/hyphens.
    """
    match = SOP_HEADER_PATTERN.match(prompt)
    if not match:
        return None
    header = match.group(1)
    if header == "direct":
        return None
    return header, f"sop-{header}", match.group(2)


def frame_route(prompt: str) -> tuple[str, str, str] | None:
    match = SOP_HEADER_PATTERN.match(prompt)
    if not match:
        return None
    header = match.group(1)
    if not header.startswith("frame-"):
        return None
    return header, header, match.group(2)


def parse_skill_name(content: str) -> str | None:
    """Read only the name field from YAML-like SKILL.md frontmatter."""
    match = re.match(r"\A---\s*\r?\n(.*?)\r?\n---\s*(?:\r?\n|\Z)", content, re.S)
    if not match:
        return None
    for line in match.group(1).splitlines():
        key, sep, value = line.partition(":")
        if sep and key.strip() == "name":
            return value.strip().strip('"\'')
    return None


def sop_config(root: Path, skill_name: str) -> dict[str, Any]:
    config = load(root / ".agent-loop/sop-policy.json", {})
    defaults = config.get("defaults", {}) if isinstance(config.get("defaults"), dict) else {}
    overrides = config.get("skills", {}) if isinstance(config.get("skills"), dict) else {}
    override = overrides.get(skill_name, {}) if isinstance(overrides.get(skill_name), dict) else {}
    return {
        "allow_mutations": bool(override.get("allow_mutations", defaults.get("allow_mutations", False))),
        "max_skill_bytes": int(override.get("max_skill_bytes", defaults.get("max_skill_bytes", 65536))),
    }


def resolve_sop_skill(root: Path, platform: str, skill_name: str) -> dict[str, Any]:
    """Resolve and validate the platform-native SOP skill, then return safe metadata and content."""
    relative_candidates: list[Path] = []
    if platform == "claude":
        relative_candidates.append(Path(".claude/skills") / skill_name / "SKILL.md")
    elif platform == "codex":
        relative_candidates.append(Path(".agents/skills") / skill_name / "SKILL.md")
    else:
        relative_candidates.extend([
            Path(".agents/skills") / skill_name / "SKILL.md",
            Path(".claude/skills") / skill_name / "SKILL.md",
        ])
    selected: Path | None = None
    selected_relative: Path | None = None
    root_resolved = root.resolve()
    for relative in relative_candidates:
        candidate = (root / relative)
        if not candidate.is_file():
            continue
        resolved = candidate.resolve()
        if resolved != root_resolved and root_resolved not in resolved.parents:
            raise ValueError("SOP skill resolves outside the repository")
        selected, selected_relative = resolved, relative
        break
    if selected is None or selected_relative is None:
        expected = ", ".join(str(path) for path in relative_candidates)
        raise FileNotFoundError(f"required skill {skill_name} is not installed; expected {expected}")
    config = sop_config(root, skill_name)
    size = selected.stat().st_size
    if size > config["max_skill_bytes"]:
        raise ValueError(f"SOP skill exceeds max_skill_bytes ({size} > {config['max_skill_bytes']})")
    content = selected.read_text(encoding="utf-8")
    declared_name = parse_skill_name(content)
    if declared_name != skill_name:
        raise ValueError(f"SKILL.md name mismatch: expected {skill_name}, found {declared_name or 'missing'}")
    return {
        "name": skill_name,
        "relative_path": str(selected_relative),
        "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "content": content,
        "allow_mutations": config["allow_mutations"],
    }


def resolve_frame_skill(root: Path, platform: str, skill_name: str) -> dict[str, Any]:
    """Resolve and validate a human-facing frame skill."""
    relative_candidates: list[Path] = []
    if platform == "claude":
        relative_candidates.append(Path(".claude/skills") / skill_name / "SKILL.md")
    elif platform == "codex":
        relative_candidates.append(Path(".agents/skills") / skill_name / "SKILL.md")
    else:
        relative_candidates.extend([
            Path(".agents/skills") / skill_name / "SKILL.md",
            Path(".claude/skills") / skill_name / "SKILL.md",
        ])
    selected: Path | None = None
    selected_relative: Path | None = None
    root_resolved = root.resolve()
    for relative in relative_candidates:
        candidate = root / relative
        if not candidate.is_file():
            continue
        resolved = candidate.resolve()
        if resolved != root_resolved and root_resolved not in resolved.parents:
            raise ValueError("frame skill resolves outside the repository")
        selected, selected_relative = resolved, relative
        break
    if selected is None or selected_relative is None:
        expected = ", ".join(str(path) for path in relative_candidates)
        raise FileNotFoundError(f"required skill {skill_name} is not installed; expected {expected}")
    content = selected.read_text(encoding="utf-8")
    declared_name = parse_skill_name(content)
    if declared_name != skill_name:
        raise ValueError(f"SKILL.md name mismatch: expected {skill_name}, found {declared_name or 'missing'}")
    return {
        "name": skill_name,
        "relative_path": str(selected_relative),
        "sha256": hashlib.sha256(content.encode("utf-8")).hexdigest(),
        "content": content,
        "allow_mutations": False,
    }


def sop_context(skill: dict[str, Any], header: str) -> str:
    return (
        "[MANDATORY_SOP_ROUTING]\n"
        f"Routing mode: {SOP_ROUTING_MODE}\n"
        f"Header: {header}\n"
        f"Required skill: {skill['name']}\n"
        f"Skill SHA-256: {skill['sha256']}\n"
        "The project hook has loaded the complete required skill below before the prompt is processed. "
        "Follow it for this turn. Do not invoke Gatekeeper, Sensemaker, State Steward, Meta-Evaluator, "
        "or the autonomous-loop workflow. Treat the text after the leading header as the task. "
        "All normal destructive-command, protected-path, permission, Watchdog, and telemetry controls remain active.\n\n"
        "----- BEGIN REQUIRED SKILL -----\n"
        f"{skill['content'].rstrip()}\n"
        "----- END REQUIRED SKILL -----\n"
        "[/MANDATORY_SOP_ROUTING]"
    )


def frame_context(skill: dict[str, Any], header: str) -> str:
    return (
        "[MANDATORY_FRAME_ROUTING]\n"
        f"Routing mode: {FRAME_ROUTING_MODE}\n"
        f"Header: {header}\n"
        f"Required skill: {skill['name']}\n"
        f"Skill SHA-256: {skill['sha256']}\n"
        "The project hook has loaded the complete required human-facing frame below before the prompt is processed. "
        "Follow it for this turn. Do not invoke Gatekeeper, the autonomous-loop workflow, or loop-control subagents. "
        "Treat the text after the leading header as the task. Read-only inspection is allowed; mutations remain blocked unless a separate explicit policy permits them.\n\n"
        "----- BEGIN REQUIRED FRAME -----\n"
        f"{skill['content'].rstrip()}\n"
        "----- END REQUIRED FRAME -----\n"
        "[/MANDATORY_FRAME_ROUTING]"
    )


def prompt_block(platform: str, reason: str) -> dict[str, Any]:
    value: dict[str, Any] = {"decision": "block", "reason": reason}
    if platform == "claude":
        value["suppressOriginalPrompt"] = False
    return value


def tool_text(event: dict[str, Any]) -> str:
    tool_input = event.get("tool_input")
    if isinstance(tool_input, dict) and isinstance(tool_input.get("command"), str):
        return tool_input["command"]
    return json.dumps(tool_input, sort_keys=True, ensure_ascii=False) if isinstance(tool_input, (dict, list)) else str(tool_input or "")


def action_hash(event: dict[str, Any]) -> str:
    raw = json.dumps({"tool_name": event.get("tool_name"), "tool_input": event.get("tool_input")}, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def command_names(command: str) -> list[str]:
    """Extract executable basenames only. Never return options, paths, values, or arguments."""
    if not command:
        return []
    try:
        lexer = shlex.shlex(command, posix=True, punctuation_chars=";&|()")
        lexer.whitespace_split = True
        lexer.commenters = ""
        tokens = list(lexer)
    except (ValueError, TypeError):
        return []
    names: list[str] = []
    expect_command = True
    for token in tokens:
        if token in SHELL_CONTROL:
            expect_command = True
            continue
        if token in SHELL_KEYWORDS:
            continue
        if not expect_command:
            continue
        if re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*=.*", token):
            continue
        if token.startswith((">", "<")):
            continue
        base = Path(token).name
        if base.startswith("-"):
            expect_command = False
            continue
        name = safe_identity(base)
        if name:
            names.append(name)
        expect_command = False
        # Preserve order, remove duplicates, cap cardinality.
    return list(dict.fromkeys(names))[:8]


def skill_name(event: dict[str, Any]) -> str | None:
    name = str(event.get("hook_event_name") or "")
    if name == "UserPromptExpansion":
        return safe_identity(event.get("command_name"))
    tool_name = str(event.get("tool_name") or "")
    tool_input = event.get("tool_input")
    if tool_name.lower() == "skill" and isinstance(tool_input, dict):
        for key in ("skill", "skill_name", "name", "command"):
            value = safe_identity(tool_input.get(key))
            if value:
                return value
    role = safe_identity(event.get("agent_type"))
    if name in {"SubagentStart", "SubagentStop"} and role in ROLES:
        return role
    return None


def is_mutation(event: dict[str, Any], policy: dict[str, Any]) -> bool:
    name = str(event.get("tool_name") or "")
    if name in {"apply_patch", "Edit", "Write", "NotebookEdit"}:
        return True
    if name == "Bash":
        return matches(policy.get("bash_mutation_patterns", []), tool_text(event))
    if name.startswith("mcp__"):
        lower = tool_text(event).lower()
        return any(word in lower for word in ("create", "update", "delete", "write", "send", "merge", "apply"))
    return False


def protected(policy: dict[str, Any], text: str) -> str | None:
    return next((item for item in policy.get("protected_path_fragments", []) if item in text), None)


def memory_policy(root: Path) -> dict[str, Any]:
    return load(root / ".agent-loop/memory-policy.json", {})


def brief_pattern_policy(root: Path) -> dict[str, Any]:
    return load(root / ".agent-loop/brief-pattern-policy.json", {})


def memory_root_path(root: Path) -> Path:
    configured = str(memory_policy(root).get("bundle_root") or "llmwiki")
    candidate = (root / configured).resolve(strict=False)
    try:
        candidate.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("memory bundle root escapes repository") from exc
    return candidate


def touches_memory_root(root: Path, text: str) -> bool:
    configured = str(memory_policy(root).get("bundle_root") or "llmwiki").strip("/")
    absolute = str(memory_root_path(root))
    normalized = text.replace("\\", "/")
    return bool(configured) and (configured + "/" in normalized or normalized.strip().endswith(configured) or absolute in text)


def apply_memory_report(root: Path, target: Path, report_path: Path, result_filename: str = "memory-commit.json") -> tuple[bool, dict[str, Any]]:
    command = root / ".agent-loop/bin/okfctl"
    if not command.is_file():
        return False, {"ok": False, "error_type": "MissingOKFCTL"}
    bundle = memory_root_path(root)
    backup = root / ".agent-loop/runtime/memory-backups"
    try:
        completed = subprocess.run(
            [str(command), "apply-report", "--root", str(bundle), "--report", str(report_path), "--backup-dir", str(backup)],
            cwd=root, text=True, capture_output=True, timeout=180, check=False,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        result = {"ok": False, "error_type": type(exc).__name__}
        atomic(target / result_filename, result)
        return False, result
    try:
        result = json.loads(completed.stdout) if completed.stdout.strip() else {}
    except json.JSONDecodeError:
        result = {}
    if not isinstance(result, dict):
        result = {}
    result.setdefault("ok", completed.returncode == 0)
    result["exit_code"] = completed.returncode
    if completed.returncode != 0:
        result["error_type"] = "OKFApplyFailed"
        result["stderr_digest"] = hashlib.sha256(completed.stderr.encode("utf-8", errors="replace")).hexdigest()
    atomic(target / result_filename, result)
    return completed.returncode == 0 and bool(result.get("ok")), result


def start_turn(root: Path, event: dict[str, Any], routing_mode: str = LOOP_ROUTING_MODE) -> dict[str, Any]:
    turn_id = event.get("turn_id") or hashlib.sha256(f"{event.get('session_id')}|{event.get('prompt')}|{time.time_ns()}".encode()).hexdigest()[:16]
    state = {
        "session_id": event.get("session_id"), "turn_id": str(turn_id), "started_at": now(),
        "prompt_length": len(str(event.get("prompt", ""))), "tool_calls": 0, "mutations": 0,
        "mutation_epoch": 0, "failures": 0, "action_counts": {}, "stop_continuations": 0,
        "watchdog": {"tripped": False, "reasons": []}, "routing_mode": routing_mode,
    }
    prior_gatekeeper = load(gatekeeper_session_path(root, event), {}) if routing_mode == LOOP_ROUTING_MODE else {}
    prior_assistant = load(loop_brief_assistant_session_path(root, event), {}) if routing_mode == LOOP_ROUTING_MODE else {}
    state["prior_gatekeeper_available"] = bool(prior_gatekeeper)
    state["prior_gatekeeper_verdict"] = prior_gatekeeper.get("verdict") if prior_gatekeeper else None
    state["prior_loop_brief_assistant_available"] = bool(prior_assistant)
    state["prior_loop_brief_assistant_status"] = prior_assistant.get("status") if prior_assistant else None
    if (prior_gatekeeper.get("verdict") == "NEEDS_INPUT" or prior_gatekeeper.get("assistant_handoff_reason") == "PATTERN_CAPTURE") and prior_assistant.get("status") == "ASK_USER":
        state["entry_role"] = LOOP_BRIEF_ASSISTANT_ROLE
    else:
        state["entry_role"] = "gatekeeper"
    save_runtime(root, event, state)
    target = turn_dir(root, state)
    target.mkdir(parents=True, exist_ok=True)
    if prior_gatekeeper:
        atomic(target / "prior-gatekeeper.json", prior_gatekeeper)
    if prior_assistant:
        atomic(target / "prior-loop-brief-assistant.json", prior_assistant)
        if isinstance(prior_assistant.get("draft_loop_brief"), dict):
            atomic(target / "prior-loop-brief-draft.json", prior_assistant.get("draft_loop_brief"))
    atomic(target / "turn.json", state)
    return state


def deny(event: str, reason: str) -> dict[str, Any]:
    return {"hookSpecificOutput": {"hookEventName": event, "permissionDecision": "deny", "permissionDecisionReason": reason}}


def add_context(event: str, text: str) -> dict[str, Any]:
    return {"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}


def block(reason: str) -> dict[str, Any]:
    return {"decision": "block", "reason": reason}


def parse_json_message(message: str) -> dict[str, Any] | None:
    stripped = message.strip()
    candidates = [stripped]
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", stripped, re.S)
    if fenced:
        candidates.append(fenced.group(1))
    start, end = stripped.find("{"), stripped.rfind("}")
    if start >= 0 and end > start:
        candidates.append(stripped[start:end + 1])
    for candidate in candidates:
        try:
            value = json.loads(candidate)
            if isinstance(value, dict):
                return value
        except json.JSONDecodeError:
            pass
    return None


def validate(role: str, body: dict[str, Any], root: Path | None = None) -> list[str]:
    required, _ = ROLES[role]
    errors: list[str] = []
    missing = sorted(required - set(body))
    if missing:
        errors.append("missing keys: " + ", ".join(missing))
    if body.get("role") != role:
        errors.append(f"role must be {role}")
    if role == "gatekeeper":
        verdict = body.get("verdict")
        if verdict not in GATEKEEPER_VERDICTS:
            errors.append("gatekeeper verdict must be READY, NEEDS_INPUT, or REJECT")
        if body.get("mode") not in {"AUTONOMOUS_LOOP", "ADVISORY_ONLY"}:
            errors.append("mode must be AUTONOMOUS_LOOP or ADVISORY_ONLY")
        checklist = body.get("condition_checklist")
        if not isinstance(checklist, dict):
            errors.append("condition_checklist must be an object")
        else:
            missing_checks = sorted(LOOP_BRIEF_FIELDS - set(checklist))
            if missing_checks:
                errors.append("condition_checklist missing fields: " + ", ".join(missing_checks))
            if verdict == "READY" and any(not bool(checklist.get(field)) for field in LOOP_BRIEF_FIELDS):
                errors.append("READY requires every condition_checklist field to be true")
        if body.get("risk_class") not in {"low", "medium", "high", "critical"}:
            errors.append("risk_class must be low, medium, high, or critical")
        brief = body.get("normalized_loop_brief")
        if not isinstance(brief, dict):
            errors.append("normalized_loop_brief must be an object")
        elif verdict == "READY":
            missing_brief = sorted(LOOP_BRIEF_FIELDS - set(brief))
            if missing_brief:
                errors.append("READY brief missing fields: " + ", ".join(missing_brief))
            if body.get("missing_conditions"):
                errors.append("READY must have no missing_conditions")
            if body.get("questions_to_user"):
                errors.append("READY must have no questions_to_user")
        if verdict == "NEEDS_INPUT":
            if not body.get("questions_to_user"):
                errors.append("NEEDS_INPUT requires questions_to_user")
            missing_conditions = body.get("missing_conditions")
            if not isinstance(missing_conditions, list) or not missing_conditions:
                errors.append("NEEDS_INPUT requires non-empty missing_conditions")
            elif any(str(field) not in LOOP_BRIEF_FIELDS for field in missing_conditions):
                errors.append("missing_conditions contains unknown fields")
            elif isinstance(checklist, dict) and any(bool(checklist.get(str(field))) for field in missing_conditions):
                errors.append("missing_conditions must be false in condition_checklist")
        directive = body.get("brief_pattern_directive")
        if not isinstance(directive, dict):
            errors.append("brief_pattern_directive must be an object")
            directive = {}
        if directive.get("action") not in BRIEF_PATTERN_ACTIONS:
            errors.append("brief_pattern_directive.action must be NONE or CAPTURE")
        if not isinstance(directive.get("reason"), str):
            errors.append("brief_pattern_directive.reason must be a string")
        assessment = body.get("brief_pattern_assessment")
        required_assessment = {"accepted_proposal_ids", "rejected_proposal_ids", "challenged_proposal_ids", "duplicate_pattern_ids", "required_corrections"}
        if not isinstance(assessment, dict):
            errors.append("brief_pattern_assessment must be an object")
            assessment = {}
        else:
            missing_assessment = sorted(required_assessment - set(assessment))
            if missing_assessment:
                errors.append("brief_pattern_assessment missing keys: " + ", ".join(missing_assessment))
            classified_sets = []
            for key in ("accepted_proposal_ids", "rejected_proposal_ids", "challenged_proposal_ids"):
                values = assessment.get(key)
                if not isinstance(values, list) or any(not LEARNING_ID.fullmatch(str(value)) for value in values):
                    errors.append(f"brief_pattern_assessment.{key} must contain valid proposal identifiers")
                    values = []
                classified_sets.append(set(str(value) for value in values))
            if len(classified_sets) == 3 and ((classified_sets[0] & classified_sets[1]) or (classified_sets[0] & classified_sets[2]) or (classified_sets[1] & classified_sets[2])):
                errors.append("brief pattern proposal classifications must be disjoint")
            duplicates = assessment.get("duplicate_pattern_ids")
            if not isinstance(duplicates, list) or any(not CONCEPT_ID.fullmatch(str(value)) for value in duplicates):
                errors.append("brief_pattern_assessment.duplicate_pattern_ids must contain valid concept identifiers")
            if not isinstance(assessment.get("required_corrections"), list):
                errors.append("brief_pattern_assessment.required_corrections must be an array")
        handoff = body.get("handoff_to_loop_brief_assistant")
        handoff_reason = body.get("assistant_handoff_reason")
        if handoff_reason not in BRIEF_PATTERN_HANDOFF_REASONS:
            errors.append("assistant_handoff_reason must be MISSING_INPUT, PATTERN_CAPTURE, or NONE")
        if verdict == "NEEDS_INPUT":
            if handoff is not True or handoff_reason != "MISSING_INPUT":
                errors.append("NEEDS_INPUT requires Assistant handoff reason MISSING_INPUT")
            if body.get("handoff_to_sensemaker"):
                errors.append("NEEDS_INPUT may not hand off to Sensemaker")
        elif verdict == "REJECT":
            if handoff is not False or handoff_reason != "NONE":
                errors.append("REJECT requires no Assistant handoff")
            if body.get("handoff_to_sensemaker"):
                errors.append("REJECT may not hand off to Sensemaker")
            if not body.get("rejection_reasons"):
                errors.append("REJECT requires rejection_reasons")
        elif verdict == "READY":
            if handoff is True:
                if handoff_reason != "PATTERN_CAPTURE" or directive.get("action") != "CAPTURE":
                    errors.append("READY Assistant handoff is permitted only for PATTERN_CAPTURE")
                if body.get("handoff_to_sensemaker"):
                    errors.append("READY may not hand off to Sensemaker while pattern capture is pending")
            else:
                if handoff_reason != "NONE":
                    errors.append("READY without Assistant handoff requires reason NONE")
                if not body.get("handoff_to_sensemaker"):
                    errors.append("READY requires handoff_to_sensemaker after pattern work is complete")
    if role == LOOP_BRIEF_ASSISTANT_ROLE:
        status = body.get("status")
        if status not in LOOP_BRIEF_ASSISTANT_STATUSES:
            errors.append("loop-brief-assistant status must be ASK_USER, READY_FOR_REVIEW, or BLOCKED")
        if body.get("interaction_mode") not in LOOP_BRIEF_ASSISTANT_MODES:
            errors.append("interaction_mode must be CLARIFY or PATTERN_CAPTURE")
        draft = body.get("draft_loop_brief")
        if not isinstance(draft, dict):
            errors.append("draft_loop_brief must be an object")
        elif set(draft) - LOOP_BRIEF_FIELDS:
            errors.append("draft_loop_brief contains unknown fields: " + ", ".join(sorted(set(draft) - LOOP_BRIEF_FIELDS)))
        for key in ("resolved_conditions", "remaining_conditions", "assumptions", "questions_to_user", "conflicts"):
            if not isinstance(body.get(key), list):
                errors.append(f"{key} must be an array")
        resolved = set(str(v) for v in (body.get("resolved_conditions") or []))
        remaining = set(str(v) for v in (body.get("remaining_conditions") or []))
        if not resolved.issubset(LOOP_BRIEF_FIELDS):
            errors.append("resolved_conditions contains unknown fields")
        if not remaining.issubset(LOOP_BRIEF_FIELDS):
            errors.append("remaining_conditions contains unknown fields")
        if resolved & remaining:
            errors.append("resolved_conditions and remaining_conditions must be disjoint")
        if resolved | remaining != LOOP_BRIEF_FIELDS:
            errors.append("resolved_conditions and remaining_conditions must cover every Loop Brief field")
        retrieval = body.get("pattern_retrieval")
        required_retrieval = {"performed", "candidate_pattern_ids", "relevant_pattern_ids", "deprecated_pattern_ids", "unavailable_reason"}
        if not isinstance(retrieval, dict):
            errors.append("pattern_retrieval must be an object")
            retrieval = {}
        else:
            missing_retrieval = sorted(required_retrieval - set(retrieval))
            if missing_retrieval:
                errors.append("pattern_retrieval missing keys: " + ", ".join(missing_retrieval))
            if not isinstance(retrieval.get("performed"), bool):
                errors.append("pattern_retrieval.performed must be boolean")
            ids = {}
            for key in ("candidate_pattern_ids", "relevant_pattern_ids", "deprecated_pattern_ids"):
                values = retrieval.get(key)
                if not isinstance(values, list) or any(not CONCEPT_ID.fullmatch(str(value)) or not str(value).startswith("loop-brief-patterns/") for value in values):
                    errors.append(f"pattern_retrieval.{key} must contain valid Loop Brief Pattern concept identifiers")
                    values = []
                ids[key] = set(str(value) for value in values)
            if not ids.get("relevant_pattern_ids", set()).issubset(ids.get("candidate_pattern_ids", set())):
                errors.append("relevant_pattern_ids must be a subset of candidate_pattern_ids")
            if not ids.get("deprecated_pattern_ids", set()).issubset(ids.get("candidate_pattern_ids", set())):
                errors.append("deprecated_pattern_ids must be a subset of candidate_pattern_ids")
            if retrieval.get("performed") is False and not retrieval.get("unavailable_reason"):
                errors.append("pattern_retrieval.unavailable_reason is required when retrieval was not performed")
        applications = body.get("pattern_application")
        unresolved_pattern_fields: set[str] = set()
        if not isinstance(applications, list):
            errors.append("pattern_application must be an array")
        else:
            for index, item in enumerate(applications):
                if not isinstance(item, dict):
                    errors.append(f"pattern_application[{index}] must be an object")
                    continue
                missing_item = sorted({"pattern_id", "suggested_fields", "confirmed_fields", "rejected_fields"} - set(item))
                if missing_item:
                    errors.append(f"pattern_application[{index}] missing keys: {', '.join(missing_item)}")
                pattern_id = str(item.get("pattern_id") or "")
                if not CONCEPT_ID.fullmatch(pattern_id) or not pattern_id.startswith("loop-brief-patterns/"):
                    errors.append(f"pattern_application[{index}].pattern_id is invalid")
                sets = {}
                for key in ("suggested_fields", "confirmed_fields", "rejected_fields"):
                    values = item.get(key)
                    if not isinstance(values, list) or any(str(value) not in LOOP_BRIEF_FIELDS for value in values):
                        errors.append(f"pattern_application[{index}].{key} contains unknown fields")
                        values = []
                    sets[key] = set(str(value) for value in values)
                if sets["confirmed_fields"] & sets["rejected_fields"]:
                    errors.append(f"pattern_application[{index}] confirmed and rejected fields must be disjoint")
                if not (sets["confirmed_fields"] | sets["rejected_fields"]).issubset(sets["suggested_fields"]):
                    errors.append(f"pattern_application[{index}] dispositions must be subsets of suggested_fields")
                unresolved_pattern_fields |= sets["suggested_fields"] - sets["confirmed_fields"] - sets["rejected_fields"]
        proposals = body.get("pattern_proposals")
        max_proposals = int((brief_pattern_policy(root or root_for()).get("max_proposals_per_brief") or 2))
        proposal_ids: set[str] = set()
        if not isinstance(proposals, list):
            errors.append("pattern_proposals must be an array")
        elif len(proposals) > max_proposals:
            errors.append(f"pattern_proposals exceeds configured maximum: {len(proposals)} > {max_proposals}")
        else:
            for index, item in enumerate(proposals):
                if not isinstance(item, dict):
                    errors.append(f"pattern_proposals[{index}] must be an object")
                    continue
                required_proposal = {"proposal_id", "concept_id", "action", "title", "task_class", "repository_kind", "risk_class", "trigger_kind", "reusable_fields", "confirmation_required_fields", "source_pattern_ids", "summary", "sensitivity", "confidence"}
                missing_proposal = sorted(required_proposal - set(item))
                if missing_proposal:
                    errors.append(f"pattern_proposals[{index}] missing keys: {', '.join(missing_proposal)}")
                proposal_id = str(item.get("proposal_id") or "")
                if not LEARNING_ID.fullmatch(proposal_id) or proposal_id in proposal_ids:
                    errors.append(f"pattern_proposals[{index}].proposal_id is invalid or duplicated")
                proposal_ids.add(proposal_id)
                concept_id = str(item.get("concept_id") or "")
                if not CONCEPT_ID.fullmatch(concept_id) or not concept_id.startswith("loop-brief-patterns/"):
                    errors.append(f"pattern_proposals[{index}].concept_id must be under loop-brief-patterns/")
                if item.get("action") not in {"UPSERT", "DEPRECATE"}:
                    errors.append(f"pattern_proposals[{index}].action is invalid")
                if item.get("risk_class") not in {"low", "medium", "high", "critical", "*"}:
                    errors.append(f"pattern_proposals[{index}].risk_class is invalid")
                for key in ("reusable_fields", "confirmation_required_fields"):
                    values = item.get(key)
                    if not isinstance(values, list) or any(str(value) not in LOOP_BRIEF_FIELDS for value in values):
                        errors.append(f"pattern_proposals[{index}].{key} contains unknown fields")
                sources = item.get("source_pattern_ids")
                if not isinstance(sources, list) or any(not CONCEPT_ID.fullmatch(str(value)) or not str(value).startswith("loop-brief-patterns/") for value in sources):
                    errors.append(f"pattern_proposals[{index}].source_pattern_ids is invalid")
                if item.get("sensitivity") not in {"public", "internal"}:
                    errors.append(f"pattern_proposals[{index}].sensitivity is invalid")
                try:
                    confidence = float(item.get("confidence"))
                except (TypeError, ValueError):
                    confidence = -1
                if confidence < 0 or confidence > 1:
                    errors.append(f"pattern_proposals[{index}].confidence must be between 0 and 1")
                if not isinstance(item.get("summary"), str) or not item.get("summary").strip():
                    errors.append(f"pattern_proposals[{index}].summary is required")
        if status == "READY_FOR_REVIEW":
            if remaining or body.get("questions_to_user") or body.get("assumptions"):
                errors.append("READY_FOR_REVIEW requires no remaining conditions, questions, or assumptions")
            if unresolved_pattern_fields:
                errors.append("READY_FOR_REVIEW requires every pattern-suggested field to be confirmed or rejected")
            if body.get("handoff_to_gatekeeper") is not True:
                errors.append("READY_FOR_REVIEW requires handoff_to_gatekeeper=true")
            if isinstance(draft, dict) and set(draft) != LOOP_BRIEF_FIELDS:
                errors.append("READY_FOR_REVIEW requires all Loop Brief fields")
            elif isinstance(draft, dict) and any(not bool(draft.get(field)) for field in LOOP_BRIEF_FIELDS):
                errors.append("READY_FOR_REVIEW requires non-empty values for all Loop Brief fields")
        if status == "ASK_USER":
            if not body.get("questions_to_user"):
                errors.append("ASK_USER requires questions_to_user")
            if body.get("handoff_to_gatekeeper") is not False:
                errors.append("ASK_USER requires handoff_to_gatekeeper=false")
        if status == "BLOCKED":
            if not body.get("conflicts"):
                errors.append("BLOCKED requires conflicts")
            if body.get("handoff_to_gatekeeper") is not False:
                errors.append("BLOCKED requires handoff_to_gatekeeper=false")
    if role == "sensemaker":
        signature = body.get("problem_signature")
        if not isinstance(signature, str) or not LEARNING_ID.fullmatch(signature):
            errors.append("problem_signature must be a stable non-secret identifier")
        prior = body.get("prior_learning_considered")
        if not isinstance(prior, list):
            errors.append("prior_learning_considered must be an array")
        else:
            for index, item in enumerate(prior):
                if not isinstance(item, dict):
                    errors.append(f"prior_learning_considered[{index}] must be an object")
                    continue
                if not LEARNING_ID.fullmatch(str(item.get("lesson_id") or "")):
                    errors.append(f"prior_learning_considered[{index}].lesson_id is invalid")
                if item.get("disposition") not in {"APPLIED", "CHALLENGED", "REJECTED", "NOT_APPLICABLE"}:
                    errors.append(f"prior_learning_considered[{index}].disposition is invalid")
        retrieval = body.get("learning_retrieval")
        if not isinstance(retrieval, dict):
            errors.append("learning_retrieval must be an object")
        else:
            required_retrieval = {"performed", "candidate_lesson_ids", "relevant_lesson_ids", "unavailable_reason"}
            missing_retrieval = sorted(required_retrieval - set(retrieval))
            if missing_retrieval:
                errors.append("learning_retrieval missing keys: " + ", ".join(missing_retrieval))
            if not isinstance(retrieval.get("performed"), bool):
                errors.append("learning_retrieval.performed must be boolean")
            candidates = retrieval.get("candidate_lesson_ids")
            relevant = retrieval.get("relevant_lesson_ids")
            if not isinstance(candidates, list) or any(not LEARNING_ID.fullmatch(str(value)) for value in candidates):
                errors.append("learning_retrieval.candidate_lesson_ids must contain valid identifiers")
                candidates = []
            if not isinstance(relevant, list) or any(not LEARNING_ID.fullmatch(str(value)) for value in relevant):
                errors.append("learning_retrieval.relevant_lesson_ids must contain valid identifiers")
                relevant = []
            if isinstance(candidates, list) and isinstance(relevant, list) and not set(map(str, relevant)).issubset(set(map(str, candidates))):
                errors.append("learning_retrieval.relevant_lesson_ids must be a subset of candidate_lesson_ids")
            if retrieval.get("performed") is False and not retrieval.get("unavailable_reason"):
                errors.append("learning_retrieval.unavailable_reason is required when retrieval was not performed")
        memory_retrieval = body.get("memory_retrieval")
        if not isinstance(memory_retrieval, dict):
            errors.append("memory_retrieval must be an object")
        else:
            required_memory_retrieval = {"performed", "candidate_concept_ids", "relevant_concept_ids", "deprecated_concept_ids", "unavailable_reason"}
            missing_memory_retrieval = sorted(required_memory_retrieval - set(memory_retrieval))
            if missing_memory_retrieval:
                errors.append("memory_retrieval missing keys: " + ", ".join(missing_memory_retrieval))
            if not isinstance(memory_retrieval.get("performed"), bool):
                errors.append("memory_retrieval.performed must be boolean")
            candidates = memory_retrieval.get("candidate_concept_ids")
            relevant = memory_retrieval.get("relevant_concept_ids")
            deprecated = memory_retrieval.get("deprecated_concept_ids")
            for key, values in (("candidate_concept_ids", candidates), ("relevant_concept_ids", relevant), ("deprecated_concept_ids", deprecated)):
                if not isinstance(values, list) or any(not CONCEPT_ID.fullmatch(str(value)) for value in values):
                    errors.append(f"memory_retrieval.{key} must contain valid concept identifiers")
            if isinstance(candidates, list) and isinstance(relevant, list) and not set(map(str, relevant)).issubset(set(map(str, candidates))):
                errors.append("memory_retrieval.relevant_concept_ids must be a subset of candidate_concept_ids")
            if isinstance(candidates, list) and isinstance(deprecated, list) and not set(map(str, deprecated)).issubset(set(map(str, candidates))):
                errors.append("memory_retrieval.deprecated_concept_ids must be a subset of candidate_concept_ids")
            if memory_retrieval.get("performed") is False and not memory_retrieval.get("unavailable_reason"):
                errors.append("memory_retrieval.unavailable_reason is required when retrieval was not performed")
        if not isinstance(body.get("hypothesis_updates"), list):
            errors.append("hypothesis_updates must be an array")
    if role == INTEGRATOR_ROLE:
        if body.get("status") not in INTEGRATOR_STATUSES:
            errors.append("integrator status must be MERGED, BLOCKED, or NO_CHANGE")
        inputs = body.get("inputs")
        if not isinstance(inputs, list):
            errors.append("inputs must be an array")
        else:
            for index, item in enumerate(inputs):
                if not isinstance(item, dict):
                    errors.append(f"inputs[{index}] must be an object")
                    continue
                if not isinstance(item.get("source_role"), str) or not item.get("source_role").strip():
                    errors.append(f"inputs[{index}].source_role must be a string")
                if not isinstance(item.get("summary"), str) or not item.get("summary").strip():
                    errors.append(f"inputs[{index}].summary must be a string")
        if body.get("status") == "MERGED":
            if not inputs:
                errors.append("MERGED requires at least one input")
            if not isinstance(body.get("merged_result"), dict):
                errors.append("merged_result must be an object")
            if body.get("handoff_to_evaluator") is not True:
                errors.append("MERGED requires handoff_to_evaluator=true")
        else:
            if body.get("merged_result") not in ({}, None):
                errors.append("non-MERGED integrator reports must not include merged_result")
            if body.get("handoff_to_evaluator") not in {False, None}:
                errors.append("non-MERGED integrator reports must not hand off to Evaluator")
        conflicts = body.get("conflicts")
        if not isinstance(conflicts, list):
            errors.append("conflicts must be an array")
        if not isinstance(body.get("resolution_strategy"), str):
            errors.append("resolution_strategy must be a string")
    if role == "state-steward":
        records = body.get("learning_records")
        if not isinstance(records, list):
            errors.append("learning_records must be an array")
        else:
            seen: set[str] = set()
            for index, item in enumerate(records):
                if not isinstance(item, dict):
                    errors.append(f"learning_records[{index}] must be an object")
                    continue
                lesson_id = str(item.get("lesson_id") or "")
                if not LEARNING_ID.fullmatch(lesson_id):
                    errors.append(f"learning_records[{index}].lesson_id is invalid")
                elif lesson_id in seen:
                    errors.append(f"duplicate lesson_id: {lesson_id}")
                seen.add(lesson_id)
                required_learning = {"lesson_id", "kind", "statement", "status", "evidence_refs", "confidence", "applicability", "invalidation_conditions", "supersedes", "review_after_turns"}
                missing_learning = sorted(required_learning - set(item))
                if missing_learning:
                    errors.append(f"learning_records[{index}] missing keys: {', '.join(missing_learning)}")
                if item.get("kind") not in {"FACT", "HEURISTIC", "CONSTRAINT", "FAILURE_PATTERN", "EVALUATION_RULE", "RECOVERY_PATTERN"}:
                    errors.append(f"learning_records[{index}].kind is invalid")
                if item.get("status") not in {"PROPOSED", "VALIDATED", "CHALLENGED", "SUPERSEDED", "REJECTED"}:
                    errors.append(f"learning_records[{index}].status is invalid")
                confidence = item.get("confidence")
                if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not 0 <= float(confidence) <= 1:
                    errors.append(f"learning_records[{index}].confidence must be between 0 and 1")
                if not isinstance(item.get("evidence_refs"), list):
                    errors.append(f"learning_records[{index}].evidence_refs must be an array")
                if not isinstance(item.get("supersedes"), list):
                    errors.append(f"learning_records[{index}].supersedes must be an array")
                if not isinstance(item.get("review_after_turns"), int) or isinstance(item.get("review_after_turns"), bool) or item.get("review_after_turns", 0) < 1:
                    errors.append(f"learning_records[{index}].review_after_turns must be a positive integer")
        questions = body.get("question_updates")
        if not isinstance(questions, list):
            errors.append("question_updates must be an array")
        else:
            for index, item in enumerate(questions):
                if not isinstance(item, dict):
                    errors.append(f"question_updates[{index}] must be an object")
                    continue
                if not LEARNING_ID.fullmatch(str(item.get("question_id") or "")):
                    errors.append(f"question_updates[{index}].question_id is invalid")
                if item.get("status") not in {"OPEN", "ANSWERED", "DEFERRED", "INVALIDATED"}:
                    errors.append(f"question_updates[{index}].status is invalid")
        proposals = body.get("memory_proposals")
        if not isinstance(proposals, list):
            errors.append("memory_proposals must be an array")
        else:
            seen_proposals: set[str] = set()
            for index, item in enumerate(proposals):
                if not isinstance(item, dict):
                    errors.append(f"memory_proposals[{index}] must be an object")
                    continue
                required_proposal = {"proposal_id", "action", "concept_id", "type", "title", "description", "tags", "source_lesson_ids", "evidence_refs", "citations", "related_concept_ids", "status", "sensitivity", "confidence", "applicability", "invalidation_conditions", "supersedes", "decision_log_entry"}
                missing_proposal = sorted(required_proposal - set(item))
                if missing_proposal:
                    errors.append(f"memory_proposals[{index}] missing keys: {', '.join(missing_proposal)}")
                proposal_id = str(item.get("proposal_id") or "")
                concept_id = str(item.get("concept_id") or "")
                if not LEARNING_ID.fullmatch(proposal_id):
                    errors.append(f"memory_proposals[{index}].proposal_id is invalid")
                elif proposal_id in seen_proposals:
                    errors.append(f"duplicate memory proposal_id: {proposal_id}")
                seen_proposals.add(proposal_id)
                if not CONCEPT_ID.fullmatch(concept_id) or "/" not in concept_id:
                    errors.append(f"memory_proposals[{index}].concept_id is invalid")
                if item.get("action") not in {"CREATE", "UPDATE", "DEPRECATE", "NO_CHANGE"}:
                    errors.append(f"memory_proposals[{index}].action is invalid")
                if item.get("status") not in {"active", "deprecated"}:
                    errors.append(f"memory_proposals[{index}].status is invalid")
                if item.get("sensitivity") not in {"public", "internal", "restricted"}:
                    errors.append(f"memory_proposals[{index}].sensitivity is invalid")
                confidence = item.get("confidence")
                if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not 0 <= float(confidence) <= 1:
                    errors.append(f"memory_proposals[{index}].confidence must be between 0 and 1")
                for key in ("tags", "source_lesson_ids", "evidence_refs", "citations", "related_concept_ids", "supersedes"):
                    if not isinstance(item.get(key), list):
                        errors.append(f"memory_proposals[{index}].{key} must be an array")
    if role == "meta-evaluator":
        if body.get("verdict") not in {"PASS", "REVISE", "ESCALATE"}:
            errors.append("invalid verdict")
        assessment = body.get("learning_assessment")
        required_assessment = {"accepted_lesson_ids", "rejected_lesson_ids", "challenged_lesson_ids", "superseded_lesson_ids", "reuse_assessment", "evaluation_changes", "knowledge_gaps"}
        if not isinstance(assessment, dict):
            errors.append("learning_assessment must be an object")
        else:
            missing_assessment = sorted(required_assessment - set(assessment))
            if missing_assessment:
                errors.append("learning_assessment missing keys: " + ", ".join(missing_assessment))
            for key in ("accepted_lesson_ids", "rejected_lesson_ids", "challenged_lesson_ids", "superseded_lesson_ids"):
                values = assessment.get(key)
                if not isinstance(values, list) or any(not LEARNING_ID.fullmatch(str(value)) for value in values):
                    errors.append(f"learning_assessment.{key} must contain valid identifiers")
            reuse = assessment.get("reuse_assessment")
            if not isinstance(reuse, list):
                errors.append("learning_assessment.reuse_assessment must be an array")
            else:
                for index, item in enumerate(reuse):
                    if not isinstance(item, dict) or not LEARNING_ID.fullmatch(str(item.get("lesson_id") or "")) or item.get("outcome") not in {"HELPFUL", "NEUTRAL", "HARMFUL", "UNVERIFIED"}:
                        errors.append(f"learning_assessment.reuse_assessment[{index}] is invalid")
            changes = assessment.get("evaluation_changes")
            if not isinstance(changes, list):
                errors.append("learning_assessment.evaluation_changes must be an array")
            else:
                for index, item in enumerate(changes):
                    if not isinstance(item, dict) or not LEARNING_ID.fullmatch(str(item.get("change_id") or "")) or item.get("status") not in {"PROPOSED", "ACCEPTED", "REJECTED", "DEFERRED"}:
                        errors.append(f"learning_assessment.evaluation_changes[{index}] is invalid")
            if not isinstance(assessment.get("knowledge_gaps"), list):
                errors.append("learning_assessment.knowledge_gaps must be an array")
        memory_assessment = body.get("memory_assessment")
        required_memory_assessment = {"accepted_proposal_ids", "rejected_proposal_ids", "challenged_proposal_ids", "duplicate_concept_ids", "citation_findings", "sensitivity_findings", "required_corrections", "memory_gaps"}
        if not isinstance(memory_assessment, dict):
            errors.append("memory_assessment must be an object")
        else:
            missing_memory_assessment = sorted(required_memory_assessment - set(memory_assessment))
            if missing_memory_assessment:
                errors.append("memory_assessment missing keys: " + ", ".join(missing_memory_assessment))
            for key in ("accepted_proposal_ids", "rejected_proposal_ids", "challenged_proposal_ids"):
                values = memory_assessment.get(key)
                if not isinstance(values, list) or any(not LEARNING_ID.fullmatch(str(value)) for value in values):
                    errors.append(f"memory_assessment.{key} must contain valid proposal identifiers")
            duplicate_ids = memory_assessment.get("duplicate_concept_ids")
            if not isinstance(duplicate_ids, list) or any(not CONCEPT_ID.fullmatch(str(value)) for value in duplicate_ids):
                errors.append("memory_assessment.duplicate_concept_ids must contain valid concept identifiers")
            for key in ("citation_findings", "sensitivity_findings", "required_corrections", "memory_gaps"):
                if not isinstance(memory_assessment.get(key), list):
                    errors.append(f"memory_assessment.{key} must be an array")
    if role in {MEMORY_CURATOR_ROLE, BRIEF_PATTERN_CURATOR_ROLE}:
        if body.get("status") not in {"COMMIT", "NO_CHANGES", "BLOCKED"}:
            errors.append("memory-curator status must be COMMIT, NO_CHANGES, or BLOCKED")
        processed = body.get("processed_proposal_ids")
        if not isinstance(processed, list) or any(not LEARNING_ID.fullmatch(str(value)) for value in processed):
            errors.append("processed_proposal_ids must contain valid identifiers")
        operations = body.get("operations")
        memory_limits = memory_policy(root or root_for())
        max_operations = int(memory_limits.get("max_operations_per_commit", 20) or 20)
        max_concept_bytes = int(memory_limits.get("max_concept_bytes", 131072) or 131072)
        if not isinstance(operations, list):
            errors.append("operations must be an array")
        elif len(operations) > max_operations:
            errors.append(f"operations exceeds configured maximum: {len(operations)} > {max_operations}")
        else:
            seen_operation_proposals: set[str] = set()
            seen_operation_concepts: set[str] = set()
            for index, item in enumerate(operations):
                if not isinstance(item, dict):
                    errors.append(f"operations[{index}] must be an object")
                    continue
                missing_operation = sorted({"action", "proposal_id", "concept_id", "document"} - set(item))
                if missing_operation:
                    errors.append(f"operations[{index}] missing keys: {', '.join(missing_operation)}")
                if item.get("action") not in {"UPSERT", "DEPRECATE"}:
                    errors.append(f"operations[{index}].action is invalid")
                proposal_id = str(item.get("proposal_id") or "")
                if not LEARNING_ID.fullmatch(proposal_id):
                    errors.append(f"operations[{index}].proposal_id is invalid")
                elif proposal_id in seen_operation_proposals:
                    errors.append(f"operations[{index}].proposal_id is duplicated")
                seen_operation_proposals.add(proposal_id)
                concept_id = str(item.get("concept_id") or "")
                if not CONCEPT_ID.fullmatch(concept_id) or "/" not in concept_id:
                    errors.append(f"operations[{index}].concept_id is invalid")
                elif concept_id in seen_operation_concepts:
                    errors.append(f"operations[{index}].concept_id is duplicated")
                seen_operation_concepts.add(concept_id)
                document = item.get("document")
                if not isinstance(document, str) or not document.startswith("---\n"):
                    errors.append(f"operations[{index}].document must be a complete OKF markdown document")
                elif len(document.encode("utf-8")) > max_concept_bytes:
                    errors.append(f"operations[{index}].document exceeds configured maximum bytes")
        for key in ("skipped_proposals", "conflicts"):
            if not isinstance(body.get(key), list):
                errors.append(f"{key} must be an array")
        if not isinstance(body.get("validation_expectations"), dict):
            errors.append("validation_expectations must be an object")
        if body.get("status") == "COMMIT" and not operations:
            errors.append("COMMIT requires at least one operation")
        if body.get("status") == "NO_CHANGES" and operations:
            errors.append("NO_CHANGES must not contain operations")
    if role == "learning-auditor" and body.get("verdict") not in {"HEALTHY", "DEGRADED", "UNHEALTHY", "UNKNOWN"}:
        errors.append("learning-auditor verdict must be HEALTHY, DEGRADED, UNHEALTHY, or UNKNOWN")
    if role == "watchdog-recovery" and body.get("status") not in {"continue", "rollback", "escalate"}:
        errors.append("invalid status")
    if role == "governor" and body.get("classification") not in {"ALLOW", "REQUIRE_APPROVAL", "DENY"}:
        errors.append("invalid classification")
    return errors


def trip_reasons(state: dict[str, Any], policy: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if state.get("tool_calls", 0) > policy.get("max_tool_calls_per_turn", 80):
        reasons.append("tool-call limit exceeded")
    if state.get("mutations", 0) > policy.get("max_mutations_per_turn", 30):
        reasons.append("mutation limit exceeded")
    if state.get("failures", 0) > policy.get("max_failures_per_turn", 5):
        reasons.append("failure limit exceeded")
    if any(count > policy.get("max_same_action_repeats", 3) for count in state.get("action_counts", {}).values()):
        reasons.append("same action repeated too many times")
    return reasons


def continuation(root: Path, event: dict[str, Any], state: dict[str, Any], policy: dict[str, Any], reason: str) -> int:
    if not reason.startswith(CONTINUATION_MARKER):
        reason = CONTINUATION_MARKER + " " + reason
    count = int(state.get("stop_continuations", 0)) + 1
    state["stop_continuations"] = count
    save_runtime(root, event, state)
    atomic(turn_dir(root, state) / "turn.json", state)
    if count > int(policy.get("max_stop_continuations", 4)):
        return emit({"continue": False, "stopReason": "Loop control gate could not be satisfied; human intervention is required.", "systemMessage": reason})
    return emit(block(reason))


def otel_any(value: Any) -> dict[str, Any]:
    if isinstance(value, bool):
        return {"boolValue": value}
    if isinstance(value, int):
        return {"intValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    if isinstance(value, (list, tuple)):
        return {"arrayValue": {"values": [otel_any(item) for item in value]}}
    return {"stringValue": str(value)}


def parse_headers(raw: str) -> dict[str, str]:
    result: dict[str, str] = {}
    for item in raw.split(","):
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        key = key.strip()
        if key:
            result[key] = value.strip()
    return result


def telemetry_config(root: Path) -> dict[str, Any]:
    config = load(root / ".agent-loop/otel.json", {})
    exporter = os.getenv(config.get("exporter_env", "AGENT_LOOP_OTEL_EXPORTER"), config.get("exporter", "none"))
    endpoint = os.getenv(config.get("endpoint_env", "AGENT_LOOP_OTEL_ENDPOINT"), config.get("endpoint", ""))
    environment = os.getenv(config.get("environment_env", "AGENT_LOOP_ENVIRONMENT"), config.get("environment", "dev"))
    headers = parse_headers(os.getenv(config.get("headers_env", "AGENT_LOOP_OTEL_HEADERS"), ""))
    return {**config, "exporter": exporter, "endpoint": endpoint, "environment": environment, "headers": headers}


def telemetry_attributes(event: dict[str, Any], platform: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    attrs: dict[str, Any] = {
        "agent.platform": platform,
        "hook.event": str(event.get("hook_event_name") or "unknown"),
        "agent.session.id": safe(event.get("session_id")),
        "agent.turn.id": safe(event.get("turn_id")) if event.get("turn_id") else "unknown",
        "tool_input_redacted": True,
        "tool.identity_redacted": False,
        "tool.arguments_logged": False,
        "command.arguments_logged": False,
    }
    role = safe_identity(event.get("agent_type"))
    if role:
        attrs["agent.role"] = role
    tool = safe_identity(event.get("tool_name"))
    if tool:
        attrs["tool.name"] = tool
    skill = skill_name(event)
    if skill:
        attrs["skill.name"] = skill
    if str(event.get("tool_name") or "") == "Bash":
        names = command_names(tool_text(event))
        if names:
            attrs["command.names"] = names
            attrs["command.name"] = names[0]
    if event.get("tool_use_id"):
        attrs["tool.call.id"] = safe(event.get("tool_use_id"))
    if extra:
        attrs.update({key: value for key, value in extra.items() if value is not None})
    return attrs


def send_otel(root: Path, event_name: str, attrs: dict[str, Any], severity: str = "INFO") -> None:
    """Best-effort OTLP/HTTP JSON export. Never exports raw prompts, arguments, outputs, paths, or headers."""
    config = telemetry_config(root)
    if not config.get("enabled", True) or config.get("exporter") == "none":
        return
    severity_number = {"DEBUG": 5, "INFO": 9, "WARN": 13, "ERROR": 17}.get(severity, 9)
    resource_attrs = {
        "service.name": config.get("service_name", "loop-engineering-agents"),
        "service.version": config.get("service_version", "unknown"),
        "deployment.environment.name": config.get("environment", "dev"),
    }
    payload = {
        "resourceLogs": [{
            "resource": {"attributes": [{"key": k, "value": otel_any(v)} for k, v in resource_attrs.items()]},
            "scopeLogs": [{
                "scope": {"name": "loop-engineering-hooks", "version": str(config.get("service_version", "unknown"))},
                "logRecords": [{
                    "timeUnixNano": now_ns(), "observedTimeUnixNano": now_ns(),
                    "severityNumber": severity_number, "severityText": severity,
                    "body": {"stringValue": event_name},
                    "attributes": [{"key": k, "value": otel_any(v)} for k, v in attrs.items()],
                }],
            }],
        }],
    }
    spool_record = {"time": now(), "event.name": event_name, **attrs}
    exporter = str(config.get("exporter", "otlp-http"))
    delivered = False
    if exporter == "console":
        print(json.dumps(spool_record, ensure_ascii=False), file=sys.stderr)
        delivered = True
    elif exporter == "otlp-http" and config.get("endpoint"):
        try:
            request = urllib.request.Request(
                str(config["endpoint"]), data=json.dumps(payload).encode("utf-8"), method="POST",
                headers={"Content-Type": "application/json", **config.get("headers", {})},
            )
            with urllib.request.urlopen(request, timeout=float(config.get("timeout_seconds", 0.5))) as response:
                delivered = 200 <= int(response.status) < 300
        except (urllib.error.URLError, TimeoutError, OSError, ValueError):
            delivered = False
    if not delivered and config.get("spool_on_failure", True):
        spool_path = root / str(config.get("spool_path", ".agent-loop/runtime/telemetry.jsonl"))
        append_jsonl(spool_path, spool_record)


def observe_learning_health(root: Path, target: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    module_path = root / ".agent-loop/lib/learning_observer.py"
    spec = importlib.util.spec_from_file_location("agent_loop_learning_observer", module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError("learning observer module cannot be loaded")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.observe_completed_turn(root, target)


def telemetry_for_hook(root: Path, event: dict[str, Any], platform: str) -> None:
    name = str(event.get("hook_event_name") or "unknown")
    extra: dict[str, Any] = {}
    severity = "INFO"
    semantic = "agent.loop.lifecycle"
    if name == "PreToolUse":
        semantic = "agent.loop.tool.started"
        extra["tool.phase"] = "started"
    elif name == "PostToolUse":
        semantic = "agent.loop.tool.completed"
        extra["tool.success"] = True
        if event.get("duration_ms") is not None:
            extra["tool.duration_ms"] = int(event["duration_ms"])
    elif name == "PostToolUseFailure":
        semantic = "agent.loop.tool.completed"
        extra["tool.success"] = False
        severity = "ERROR"
        if event.get("duration_ms") is not None:
            extra["tool.duration_ms"] = int(event["duration_ms"])
    elif name == "PermissionRequest":
        semantic = "agent.loop.tool.permission_requested"
    elif name == "PermissionDenied":
        semantic = "agent.loop.tool.permission_denied"
        severity = "WARN"
    elif name == "UserPromptExpansion":
        semantic = "agent.loop.skill.activated"
        extra["skill.invocation_trigger"] = "user-slash"
        source = safe_identity(event.get("command_source"))
        if source:
            extra["skill.source"] = source
    elif name == "SubagentStart":
        semantic = "agent.loop.agent.started"
        if skill_name(event):
            extra["skill.invocation_trigger"] = f"{platform}-subagent-adapter"
    elif name == "SubagentStop":
        semantic = "agent.loop.agent.stopped"
    elif name == "UserPromptSubmit":
        semantic = "agent.loop.turn.started"
        extra["prompt.content_logged"] = False
        extra["prompt.length"] = len(str(event.get("prompt", "")))
    elif name == "Stop":
        semantic = "agent.loop.turn.stopping"
    send_otel(root, semantic, telemetry_attributes(event, platform, extra), severity)


def handle(event: dict[str, Any], platform: str = "unknown") -> int:
    root = root_for(event.get("cwd"))
    policy = load(root / ".agent-loop/policy.json", {})
    name = str(event.get("hook_event_name") or "")
    telemetry_for_hook(root, event, platform)

    if name == "SessionStart":
        return emit(add_context(name, "Routing protocol active. A strict leading direct: prefix starts a bounded Gatekeeper-free direct turn. A strict leading frame-<name>: prefix loads the matching human-facing frame skill in isolated FRAME mode. Other strict leading <header>: prefixes load the matching sop-<header> skill in isolated SOP mode. All remaining requests enter Gatekeeper. Gatekeeper NEEDS_INPUT activates the read-only loop-brief-assistant, which retrieves reviewed Loop Brief patterns, asks for explicit confirmation or missing fields, and returns a draft to Gatekeeper for independent review. Gatekeeper may also request PATTERN_CAPTURE for a complete brief; accepted proposals are curated by brief-pattern-curator and committed transactionally. Only a trusted READY Gatekeeper report may hand off to Sensemaker. The Loop Brief includes explicit learning_contract and memory_contract fields. Sensemaker retrieves the OKF LLMWiki progressively. After loop mutations, use state-steward and meta-evaluator; accepted durable-memory proposals are committed only by memory-curator through the deterministic Go okfctl transaction. Completed turns are summarized by the deterministic learning observer; use learning-audit: to invoke the read-only learning-auditor. Sanitized OTel records role, skill, tool, and executable names only; arguments and content are excluded."))
    if name == "UserPromptSubmit":
        prompt = str(event.get("prompt", ""))
        if prompt.startswith(CONTINUATION_MARKER):
            state = runtime(root, event)
            if not state:
                state = start_turn(root, event)
            return emit(add_context(name, "This is an internal loop-control continuation. Preserve the existing turn and follow the instruction after the continuation marker; do not invoke Gatekeeper again."))
        direct_task = direct_route(prompt)
        if direct_task is not None:
            config = direct_config(root)
            if not config.get("enabled"):
                return emit(prompt_block(platform, "Direct mode is disabled by .agent-loop/direct-policy.json."))
            if len(prompt.encode("utf-8")) > int(config.get("max_prompt_bytes", 65536)):
                return emit(prompt_block(platform, "Direct prompt exceeds max_prompt_bytes."))
            state = start_turn(root, event, DIRECT_ROUTING_MODE)
            state["direct"] = {"loaded": True, "allow_mutations": bool(config.get("allow_mutations")), "content_logged": False}
            save_runtime(root, event, state)
            target = turn_dir(root, state)
            atomic(target / "turn.json", state)
            atomic(target / "direct-route.json", {"loaded_at": now(), "allow_mutations": bool(config.get("allow_mutations")), "content_logged": False})
            append_jsonl(target / "journal.jsonl", {"time": now(), "event": "direct-started", "routing_mode": DIRECT_ROUTING_MODE, "allow_mutations": bool(config.get("allow_mutations")), "content_logged": False, "arguments_logged": False})
            send_otel(root, "agent.loop.direct.started", telemetry_attributes(event, platform, {"routing.mode": DIRECT_ROUTING_MODE, "direct.allow_mutations": bool(config.get("allow_mutations")), "prompt.content_logged": False}))
            return emit(add_context(name, "[DIRECT_MODE] The leading direct: prefix selected a bounded Gatekeeper-free turn. Answer the task after the prefix directly. Do not invoke Gatekeeper, Loop Brief Assistant, Sensemaker, State Steward, Meta-Evaluator, Memory Curator, or the autonomous-loop workflow. Direct mode is read-only unless .agent-loop/direct-policy.json explicitly allows mutations. Destructive-command, protected-path, LLMWiki, permission, Watchdog, and telemetry controls remain active. [/DIRECT_MODE]"))
        frame = frame_route(prompt)
        if frame:
            header, required_skill, _task_body = frame
            state = start_turn(root, event, FRAME_ROUTING_MODE)
            target = turn_dir(root, state)
            try:
                skill = resolve_frame_skill(root, platform, required_skill)
            except (FileNotFoundError, ValueError, UnicodeError, OSError) as exc:
                state["frame"] = {"header": header, "required_skill": required_skill, "loaded": False, "error": type(exc).__name__}
                save_runtime(root, event, state)
                atomic(target / "turn.json", state)
                send_otel(root, "agent.loop.frame.load_failed", telemetry_attributes(event, platform, {"routing.mode": FRAME_ROUTING_MODE, "frame.header": header, "skill.name": required_skill, "frame.loaded": False}), "ERROR")
                return emit(prompt_block(platform, f"Mandatory FRAME routing failed: {exc}. Install and validate {required_skill} before retrying."))
            state["frame"] = {
                "header": header, "required_skill": required_skill, "loaded": True,
                "skill_sha256": skill["sha256"], "allow_mutations": skill["allow_mutations"],
            }
            save_runtime(root, event, state)
            atomic(target / "turn.json", state)
            atomic(target / "frame-route.json", {
                "header": header, "skill_name": required_skill, "skill_sha256": skill["sha256"],
                "allow_mutations": skill["allow_mutations"], "loaded_at": now(), "content_logged": False,
            })
            append_jsonl(target / "journal.jsonl", {
                "time": now(), "event": "frame-loaded", "routing_mode": FRAME_ROUTING_MODE,
                "frame_header": header, "skill_name": required_skill, "skill_sha256": skill["sha256"],
                "allow_mutations": skill["allow_mutations"], "content_logged": False, "arguments_logged": False,
            })
            send_otel(root, "agent.loop.frame.loaded", telemetry_attributes(event, platform, {
                "routing.mode": FRAME_ROUTING_MODE, "frame.header": header, "skill.name": required_skill,
                "frame.loaded": True, "frame.allow_mutations": skill["allow_mutations"],
            }))
            return emit(add_context(name, frame_context(skill, header)))
        route = sop_route(prompt)
        if route:
            header, required_skill, _task_body = route
            state = start_turn(root, event, SOP_ROUTING_MODE)
            target = turn_dir(root, state)
            try:
                skill = resolve_sop_skill(root, platform, required_skill)
            except (FileNotFoundError, ValueError, UnicodeError, OSError) as exc:
                state["sop"] = {"header": header, "required_skill": required_skill, "loaded": False, "error": type(exc).__name__}
                save_runtime(root, event, state)
                atomic(target / "turn.json", state)
                send_otel(root, "agent.loop.sop.load_failed", telemetry_attributes(event, platform, {"routing.mode": SOP_ROUTING_MODE, "sop.header": header, "skill.name": required_skill, "sop.loaded": False}), "ERROR")
                return emit(prompt_block(platform, f"Mandatory SOP routing failed: {exc}. Install and validate {required_skill} before retrying."))
            state["sop"] = {
                "header": header, "required_skill": required_skill, "loaded": True,
                "skill_sha256": skill["sha256"], "allow_mutations": skill["allow_mutations"],
            }
            save_runtime(root, event, state)
            atomic(target / "turn.json", state)
            atomic(target / "sop-route.json", {
                "header": header, "skill_name": required_skill, "skill_sha256": skill["sha256"],
                "allow_mutations": skill["allow_mutations"], "loaded_at": now(), "content_logged": False,
            })
            append_jsonl(target / "journal.jsonl", {
                "time": now(), "event": "sop-loaded", "routing_mode": SOP_ROUTING_MODE,
                "sop_header": header, "skill_name": required_skill, "skill_sha256": skill["sha256"],
                "allow_mutations": skill["allow_mutations"], "content_logged": False, "arguments_logged": False,
            })
            send_otel(root, "agent.loop.sop.loaded", telemetry_attributes(event, platform, {
                "routing.mode": SOP_ROUTING_MODE, "sop.header": header, "skill.name": required_skill,
                "sop.loaded": True, "sop.allow_mutations": skill["allow_mutations"],
            }))
            return emit(add_context(name, sop_context(skill, header)))
        state = start_turn(root, event, LOOP_ROUTING_MODE)
        if state.get("entry_role") == LOOP_BRIEF_ASSISTANT_ROLE:
            return emit(add_context(name, "This message answers outstanding Loop Brief Assistant questions. Invoke loop-brief-assistant before Gatekeeper, using prior-loop-brief-assistant.json and prior-gatekeeper.json. Merge only explicit user answers. If the draft becomes READY_FOR_REVIEW, return it to Gatekeeper; otherwise ask only the remaining minimal questions. Product mutations remain blocked."))
        prior = " A prior Gatekeeper report is available in the current turn directory; use it as context and merge only explicit user-backed information." if state.get("prior_gatekeeper_available") else ""
        return emit(add_context(name, "No direct or SOP header was detected. Treat the user's message as input to Gatekeeper. Invoke the gatekeeper skill before every other control role. Gatekeeper must return READY, NEEDS_INPUT, or REJECT. NEEDS_INPUT must hand off to loop-brief-assistant; the Assistant retrieves reviewed input patterns but may not silently apply them. A READY brief may request PATTERN_CAPTURE before Sensemaker. Durable memory remains write-protected and may be promoted only by memory-curator or brief-pattern-curator through deterministic Go transactions." + prior))

    state = runtime(root, event)
    if not state:
        state = start_turn(root, event)
    target = turn_dir(root, state)

    if name == "SubagentStart":
        agent_type = safe_identity(event.get("agent_type"))
        gate = load(target / "gatekeeper.json", {})
        append_jsonl(target / "journal.jsonl", {
            "time": now(), "event": name, "agent_type": agent_type,
            "agent_id": safe(event.get("agent_id")), "arguments_logged": False,
            "routing_mode": state.get("routing_mode"), "gatekeeper_verdict": gate.get("verdict"),
        })
        if state.get("routing_mode") == DIRECT_ROUTING_MODE and agent_type in ROLES:
            config = direct_config(root)
            if not config.get("allow_loop_control_roles", False):
                return emit(add_context("SubagentStart", "This turn is in direct mode. Loop-control roles are not part of this workflow; return immediately to the parent agent."))
        if state.get("routing_mode") == FRAME_ROUTING_MODE and agent_type in ROLES:
            return emit(add_context("SubagentStart", "This turn is in isolated FRAME mode. Loop-control roles are not part of this workflow; return immediately to the parent agent."))
        if state.get("routing_mode") == SOP_ROUTING_MODE and agent_type in ROLES:
            sop = state.get("sop", {}) if isinstance(state.get("sop"), dict) else {}
            allowed_learning_audit = agent_type == "learning-auditor" and sop.get("required_skill") == LEARNING_AUDIT_SKILL
            if not allowed_learning_audit:
                return emit(add_context("SubagentStart", "This turn is in mandatory SOP mode. Loop-control roles are not part of this workflow; return immediately to the parent agent."))
            return 0
        prior_gate = load(target / "prior-gatekeeper.json", {})
        assistant_allowed = agent_type == LOOP_BRIEF_ASSISTANT_ROLE and (gate.get("verdict") == "NEEDS_INPUT" or prior_gate.get("verdict") == "NEEDS_INPUT" or gate.get("assistant_handoff_reason") == "PATTERN_CAPTURE" or prior_gate.get("assistant_handoff_reason") == "PATTERN_CAPTURE" or state.get("entry_role") == LOOP_BRIEF_ASSISTANT_ROLE)
        if agent_type in ROLES and agent_type != "gatekeeper" and gate.get("verdict") != "READY" and not assistant_allowed:
            return emit(add_context("SubagentStart", "Gatekeeper has not returned READY. Only Gatekeeper or a Gatekeeper-triggered Loop Brief Assistant may run at this stage."))
        if agent_type == MEMORY_CURATOR_ROLE:
            evaluator = load(target / "meta-evaluator.json", {})
            accepted = ((evaluator.get("memory_assessment") or {}).get("accepted_proposal_ids") or []) if isinstance(evaluator, dict) else []
            if not evaluator.get("_trusted_subagent") or evaluator.get("verdict") != "PASS" or not accepted:
                return emit(add_context("SubagentStart", "Memory Curator may run only after a trusted PASS Meta-Evaluator report has accepted at least one memory proposal. Return to the parent agent."))
        if agent_type == BRIEF_PATTERN_CURATOR_ROLE:
            accepted = ((gate.get("brief_pattern_assessment") or {}).get("accepted_proposal_ids") or []) if isinstance(gate, dict) else []
            if not gate.get("_trusted_subagent") or gate.get("verdict") != "READY" or not accepted:
                return emit(add_context("SubagentStart", "Brief Pattern Curator may run only after a trusted READY Gatekeeper report has accepted at least one Loop Brief pattern proposal. Return to the parent agent."))
        return 0

    if name == "UserPromptExpansion":
        append_jsonl(target / "journal.jsonl", {
            "time": now(), "event": name, "skill_name": skill_name(event),
            "invocation_trigger": "user-slash", "arguments_logged": False,
        })
        return 0

    if name == "PreToolUse":
        text = tool_text(event)
        mutation = is_mutation(event, policy)
        agent = str(event.get("agent_type") or "")
        if matches(policy.get("deny_command_patterns", []), text):
            return emit(deny(name, "Categorically destructive command denied."))
        if matches(policy.get("high_risk_command_patterns", []), text):
            return emit(deny(name, "High-risk operation denied. Use a human-controlled process for any separately approved operation."))
        if mutation and touches_memory_root(root, text):
            return emit(deny(name, "Direct mutation of the OKF LLMWiki is denied. Durable memory may be changed only by a trusted memory-curator or brief-pattern-curator report through deterministic okfctl apply-report."))
        hit = protected(policy, text)
        if mutation and hit:
            return emit(deny(name, f"Mutation of protected loop-control path denied: {hit}"))
        if mutation and state.get("watchdog", {}).get("tripped"):
            return emit(deny(name, "Watchdog is tripped. Stop and obtain human intervention."))
        if state.get("routing_mode") == DIRECT_ROUTING_MODE:
            config = direct_config(root)
            if agent in ROLES and not config.get("allow_loop_control_roles", False):
                return emit(deny(name, f"Loop-control role {agent} is not permitted in direct mode."))
            if mutation and not config.get("allow_mutations", False):
                return emit(deny(name, "Direct mode is read-only. Use the autonomous loop or explicitly review direct-policy.json before permitting mutations."))
            return 0
        if state.get("routing_mode") == FRAME_ROUTING_MODE:
            frame = state.get("frame", {}) if isinstance(state.get("frame"), dict) else {}
            if not frame.get("loaded"):
                return emit(deny(name, "Mandatory FRAME skill was not successfully loaded; no tool use is permitted."))
            if agent in ROLES:
                return emit(deny(name, f"Loop-control role {agent} is not permitted in isolated FRAME mode."))
            if mutation:
                return emit(deny(name, f"FRAME {frame.get('required_skill', 'unknown')} is read-only."))
            return 0
        if state.get("routing_mode") == SOP_ROUTING_MODE:
            sop = state.get("sop", {}) if isinstance(state.get("sop"), dict) else {}
            if not sop.get("loaded"):
                return emit(deny(name, "Mandatory SOP skill was not successfully loaded; no tool use is permitted."))
            if agent in ROLES:
                allowed_learning_audit = agent == "learning-auditor" and sop.get("required_skill") == LEARNING_AUDIT_SKILL
                if not allowed_learning_audit:
                    return emit(deny(name, f"Loop-control role {agent} is not permitted in isolated SOP mode."))
                if mutation:
                    return emit(deny(name, "The learning-auditor is read-only."))
            if mutation and not sop.get("allow_mutations", False):
                return emit(deny(name, f"SOP {sop.get('required_skill', 'unknown')} is read-only. Configure an explicit allow_mutations override only after security review."))
            return 0
        gate = load(target / "gatekeeper.json", {})
        prior_gate = load(target / "prior-gatekeeper.json", {})
        assistant_allowed = agent == LOOP_BRIEF_ASSISTANT_ROLE and (gate.get("verdict") == "NEEDS_INPUT" or prior_gate.get("verdict") == "NEEDS_INPUT" or gate.get("assistant_handoff_reason") == "PATTERN_CAPTURE" or prior_gate.get("assistant_handoff_reason") == "PATTERN_CAPTURE" or state.get("entry_role") == LOOP_BRIEF_ASSISTANT_ROLE)
        if agent in ROLES and agent != "gatekeeper" and gate.get("verdict") != "READY" and not assistant_allowed:
            return emit(deny(name, "Gatekeeper has not returned READY. Only Gatekeeper or the Gatekeeper-triggered Loop Brief Assistant may inspect the request at this stage."))
        if mutation and agent in ROLES:
            return emit(deny(name, f"Control role {agent} is read-only and may not mutate files or external state."))
        if mutation and policy.get("require_gatekeeper_before_mutation", True):
            gate = load(target / "gatekeeper.json", {})
            if not gate.get("_trusted_subagent") or gate.get("verdict") != "READY":
                return emit(deny(name, "No trusted READY Gatekeeper report exists for this turn. Continue the Gatekeeper dialogue first."))
        if mutation and policy.get("require_sensemaker_before_mutation", True):
            report = load(target / "sensemaker.json", {})
            if not report.get("_trusted_subagent"):
                return emit(deny(name, "No trusted Sensemaker report exists for this turn. Invoke the sensemaker skill after Gatekeeper READY."))
        if mutation and policy.get("require_integrator_before_mutation", False):
            report = load(target / "integrator.json", {})
            if not report.get("_trusted_subagent"):
                return emit(deny(name, "No trusted Integrator report exists for this turn. Invoke the integrator skill after Sensemaker and before mutation."))
            if report.get("status") != "MERGED":
                return emit(deny(name, "Integrator must report MERGED before mutation can proceed."))
        return 0

    if name == "PermissionRequest":
        text = tool_text(event)
        if matches(policy.get("deny_command_patterns", []), text) or matches(policy.get("high_risk_command_patterns", []), text) or protected(policy, text):
            return emit({"hookSpecificOutput": {"hookEventName": "PermissionRequest", "decision": {"behavior": "deny", "message": "Denied by loop-control policy; use Governor and human execution for high-risk work."}}})
        return 0

    if name in {"PostToolUse", "PostToolUseFailure"}:
        state["tool_calls"] = int(state.get("tool_calls", 0)) + 1
        fingerprint = action_hash(event)
        counts = state.setdefault("action_counts", {})
        counts[fingerprint] = int(counts.get(fingerprint, 0)) + 1
        attempted_mutation = is_mutation(event, policy)
        mutation = attempted_mutation and name == "PostToolUse"
        if mutation:
            state["mutations"] = int(state.get("mutations", 0)) + 1
            state["mutation_epoch"] = int(state.get("mutation_epoch", 0)) + 1
            state["stop_continuations"] = 0
        if name == "PostToolUseFailure":
            state["failures"] = int(state.get("failures", 0)) + 1
        reasons = trip_reasons(state, policy)
        if reasons:
            state["watchdog"] = {"tripped": True, "reasons": reasons, "tripped_at": now()}
            send_otel(root, "agent.loop.watchdog.tripped", telemetry_attributes(event, platform, {"watchdog.reasons": reasons}), "WARN")
        save_runtime(root, event, state)
        atomic(target / "turn.json", state)
        append_jsonl(target / "journal.jsonl", {
            "time": now(), "event": name, "agent_type": safe_identity(event.get("agent_type")),
            "tool_name": safe_identity(event.get("tool_name")), "command_names": command_names(tool_text(event)) if event.get("tool_name") == "Bash" else [],
            "skill_name": skill_name(event), "attempted_mutation": attempted_mutation, "mutation": mutation,
            "mutation_epoch": state.get("mutation_epoch"), "tool_success": name == "PostToolUse",
            "tool_input_redacted": True, "arguments_logged": False, "watchdog": state.get("watchdog"),
        })
        if reasons:
            return emit(add_context(name, "Watchdog tripped: " + "; ".join(reasons) + ". Further product mutations are blocked. Invoke watchdog-recovery and request a human reset."))
        return 0

    if name == "StopFailure":
        state["failures"] = int(state.get("failures", 0)) + 1
        reasons = trip_reasons(state, policy)
        if reasons:
            state["watchdog"] = {"tripped": True, "reasons": reasons, "tripped_at": now()}
        save_runtime(root, event, state)
        atomic(target / "turn.json", state)
        append_jsonl(target / "journal.jsonl", {"time": now(), "event": name, "failure_category": safe_identity(event.get("error")), "watchdog": state.get("watchdog"), "content_logged": False})
        return 0

    if name in {"PreCompact", "PostCompact"}:
        append_jsonl(target / "compaction.jsonl", {"time": now(), "event": name, "trigger": safe_identity(event.get("trigger")), "summary_logged": False})
        return 0

    if name == "SubagentStop":
        role = str(event.get("agent_type") or "")
        if role not in ROLES:
            return 0
        if state.get("routing_mode") == DIRECT_ROUTING_MODE:
            append_jsonl(target / "journal.jsonl", {"time": now(), "event": "role-report-ignored", "role": role, "routing_mode": DIRECT_ROUTING_MODE, "content_logged": False})
            return 0
        if state.get("routing_mode") == FRAME_ROUTING_MODE:
            append_jsonl(target / "journal.jsonl", {"time": now(), "event": "role-report-ignored", "role": role, "routing_mode": FRAME_ROUTING_MODE, "content_logged": False})
            return 0
        if state.get("routing_mode") == SOP_ROUTING_MODE:
            sop = state.get("sop", {}) if isinstance(state.get("sop"), dict) else {}
            if not (role == "learning-auditor" and sop.get("required_skill") == LEARNING_AUDIT_SKILL):
                append_jsonl(target / "journal.jsonl", {"time": now(), "event": "role-report-ignored", "role": role, "routing_mode": SOP_ROUTING_MODE, "content_logged": False})
                return 0
            body = parse_json_message(str(event.get("last_assistant_message") or ""))
            if body is None:
                return emit(block("learning-auditor must return exactly one valid JSON object with no surrounding prose."))
            errors = validate(role, body, root)
            if errors:
                return emit(block("Invalid learning-auditor report: " + "; ".join(errors) + ". Return a corrected JSON object."))
            body.update({"_trusted_subagent": True, "_recorded_at": now(), "_agent_id": event.get("agent_id"), "_agent_type": role})
            atomic(target / ROLES[role][1], body)
            append_jsonl(target / "journal.jsonl", {"time": now(), "event": "role-report", "role": role, "skill_name": role, "report_content_logged": False})
            send_otel(root, "agent.loop.learning.audit_reported", telemetry_attributes(event, platform, {"role.report.valid": True, "skill.name": role, "learning.health": body.get("verdict"), "human_review_required": bool(body.get("human_review_required"))}))
            return 0
        gate = load(target / "gatekeeper.json", {})
        prior_gate = load(target / "prior-gatekeeper.json", {})
        assistant_allowed = role == LOOP_BRIEF_ASSISTANT_ROLE and (gate.get("verdict") == "NEEDS_INPUT" or prior_gate.get("verdict") == "NEEDS_INPUT" or gate.get("assistant_handoff_reason") == "PATTERN_CAPTURE" or prior_gate.get("assistant_handoff_reason") == "PATTERN_CAPTURE" or state.get("entry_role") == LOOP_BRIEF_ASSISTANT_ROLE)
        if role != "gatekeeper" and gate.get("verdict") != "READY" and not assistant_allowed:
            return emit(block("Gatekeeper has not returned READY. This role report cannot be accepted."))
        accepted_patterns = set(str(v) for v in ((gate.get("brief_pattern_assessment") or {}).get("accepted_proposal_ids") or []))
        pattern_commit = load(target / "brief-pattern-commit.json", {})
        if accepted_patterns and role not in {"gatekeeper", LOOP_BRIEF_ASSISTANT_ROLE, BRIEF_PATTERN_CURATOR_ROLE} and not pattern_commit.get("ok"):
            return emit(block("Gatekeeper accepted Loop Brief pattern proposals, but the deterministic pattern commit is incomplete."))
        body = parse_json_message(str(event.get("last_assistant_message") or ""))
        if body is None:
            return emit(block(f"{role} must return exactly one valid JSON object with no surrounding prose."))
        errors = validate(role, body, root)
        if errors:
            return emit(block(f"Invalid {role} report: " + "; ".join(errors) + ". Return a corrected JSON object."))
        if role == LOOP_BRIEF_ASSISTANT_ROLE:
            active_gate = gate if gate.get("verdict") in {"NEEDS_INPUT", "READY"} and gate.get("handoff_to_loop_brief_assistant") else prior_gate
            body["_gatekeeper_recorded_at"] = active_gate.get("_recorded_at")
        if role == "gatekeeper":
            assistant_report = load(target / "loop-brief-assistant.json", {})
            proposals = assistant_report.get("pattern_proposals") if isinstance(assistant_report.get("pattern_proposals"), list) else []
            proposal_ids = {str(item.get("proposal_id")) for item in proposals if isinstance(item, dict) and item.get("proposal_id")}
            assessment = body.get("brief_pattern_assessment") if isinstance(body.get("brief_pattern_assessment"), dict) else {}
            accepted = set(str(v) for v in (assessment.get("accepted_proposal_ids") or []))
            rejected = set(str(v) for v in (assessment.get("rejected_proposal_ids") or []))
            challenged = set(str(v) for v in (assessment.get("challenged_proposal_ids") or []))
            classified = accepted | rejected | challenged
            if classified and classified != proposal_ids:
                return emit(block("Gatekeeper must classify every and only Loop Brief Assistant pattern proposal ID."))
            if proposal_ids and classified != proposal_ids:
                return emit(block("Gatekeeper must classify all Loop Brief pattern proposals before handoff to Sensemaker."))
            if proposal_ids and body.get("handoff_to_loop_brief_assistant"):
                return emit(block("Gatekeeper may not request another Assistant handoff after classifying a fresh pattern proposal."))
        if role == "meta-evaluator":
            steward = load(target / "state-steward.json", {})
            proposal_ids = {
                str(item.get("proposal_id"))
                for item in (steward.get("memory_proposals") or [])
                if isinstance(item, dict) and item.get("proposal_id")
            }
            assessment = body.get("memory_assessment") if isinstance(body.get("memory_assessment"), dict) else {}
            accepted = set(str(v) for v in (assessment.get("accepted_proposal_ids") or []))
            rejected = set(str(v) for v in (assessment.get("rejected_proposal_ids") or []))
            challenged = set(str(v) for v in (assessment.get("challenged_proposal_ids") or []))
            if (accepted & rejected) or (accepted & challenged) or (rejected & challenged):
                return emit(block("Meta-Evaluator memory proposal classifications must be disjoint."))
            classified = accepted | rejected | challenged
            if classified != proposal_ids:
                return emit(block("Meta-Evaluator must classify every and only State Steward memory proposal ID."))
        if role == MEMORY_CURATOR_ROLE:
            evaluator = load(target / "meta-evaluator.json", {})
            accepted = set(str(v) for v in ((evaluator.get("memory_assessment") or {}).get("accepted_proposal_ids") or []))
            processed = set(str(v) for v in (body.get("processed_proposal_ids") or []))
            operation_ids = set(str(item.get("proposal_id")) for item in (body.get("operations") or []) if isinstance(item, dict))
            if processed != accepted:
                return emit(block("memory-curator processed_proposal_ids must exactly match Meta-Evaluator accepted_proposal_ids."))
            if body.get("status") == "COMMIT" and operation_ids != accepted:
                return emit(block("memory-curator COMMIT operations must cover every and only accepted memory proposal."))
            if body.get("status") == "NO_CHANGES" and accepted:
                return emit(block("memory-curator cannot return NO_CHANGES when Meta-Evaluator accepted memory proposals."))
        if role == BRIEF_PATTERN_CURATOR_ROLE:
            gatekeeper_report = load(target / "gatekeeper.json", {})
            accepted = set(str(v) for v in ((gatekeeper_report.get("brief_pattern_assessment") or {}).get("accepted_proposal_ids") or []))
            processed = set(str(v) for v in (body.get("processed_proposal_ids") or []))
            operation_ids = set(str(item.get("proposal_id")) for item in (body.get("operations") or []) if isinstance(item, dict))
            if processed != accepted:
                return emit(block("brief-pattern-curator processed_proposal_ids must exactly match Gatekeeper accepted_proposal_ids."))
            if body.get("status") == "COMMIT" and operation_ids != accepted:
                return emit(block("brief-pattern-curator COMMIT operations must cover every and only accepted pattern proposal."))
            if body.get("status") == "NO_CHANGES" and accepted:
                return emit(block("brief-pattern-curator cannot return NO_CHANGES when Gatekeeper accepted pattern proposals."))
        body.update({"_trusted_subagent": True, "_recorded_at": now(), "_agent_id": event.get("agent_id"), "_agent_type": role, "_mutation_epoch": state.get("mutation_epoch", 0)})
        atomic(target / ROLES[role][1], body)
        if role == "gatekeeper":
            atomic(gatekeeper_session_path(root, event), body)
            if body.get("verdict") == "READY":
                atomic(target / "loop-brief.json", body.get("normalized_loop_brief", {}))
                if not body.get("handoff_to_loop_brief_assistant"):
                    try:
                        loop_brief_assistant_session_path(root, event).unlink()
                    except FileNotFoundError:
                        pass
            elif body.get("verdict") == "REJECT":
                try:
                    loop_brief_assistant_session_path(root, event).unlink()
                except FileNotFoundError:
                    pass
        if role == LOOP_BRIEF_ASSISTANT_ROLE:
            atomic(loop_brief_assistant_session_path(root, event), body)
            atomic(target / "loop-brief-draft.json", body.get("draft_loop_brief", {}))
        state["stop_continuations"] = 0
        save_runtime(root, event, state)
        atomic(target / "turn.json", state)
        append_jsonl(target / "journal.jsonl", {"time": now(), "event": "role-report", "role": role, "skill_name": role, "mutation_epoch": state.get("mutation_epoch", 0), "report_content_logged": False})
        send_otel(root, "agent.loop.role.reported", telemetry_attributes(event, platform, {"role.report.valid": True, "skill.name": role}))
        if role == MEMORY_CURATOR_ROLE:
            if body.get("status") == "BLOCKED":
                send_otel(root, "agent.loop.memory.curated", telemetry_attributes(event, platform, {"memory.commit.ok": False, "memory.curator.status": "BLOCKED"}), "WARN")
            else:
                ok, commit = apply_memory_report(root, target, target / ROLES[role][1])
                send_otel(root, "agent.loop.memory.curated", telemetry_attributes(event, platform, {
                    "memory.commit.ok": ok,
                    "memory.curator.status": body.get("status"),
                    "memory.applied_count": len(commit.get("applied_concept_ids", [])) if isinstance(commit.get("applied_concept_ids"), list) else 0,
                    "memory.created_count": int(commit.get("created_count", 0) or 0),
                    "memory.updated_count": int(commit.get("updated_count", 0) or 0),
                    "memory.deprecated_count": int(commit.get("deprecated_count", 0) or 0),
                }), "INFO" if ok else "ERROR")
                if not ok:
                    return emit(block("Deterministic OKF memory commit failed. Inspect memory-commit.json, correct the curator report without exposing secrets, and retry."))
        if role == BRIEF_PATTERN_CURATOR_ROLE:
            if body.get("status") == "BLOCKED":
                send_otel(root, "agent.loop.brief_pattern.curated", telemetry_attributes(event, platform, {"brief_pattern.commit_ok": False, "brief_pattern.curator_status": "BLOCKED"}), "WARN")
            else:
                ok, commit = apply_memory_report(root, target, target / ROLES[role][1], "brief-pattern-commit.json")
                send_otel(root, "agent.loop.brief_pattern.curated", telemetry_attributes(event, platform, {
                    "brief_pattern.commit_ok": ok,
                    "brief_pattern.curator_status": body.get("status"),
                    "brief_pattern.applied_count": len(commit.get("applied_concept_ids", [])) if isinstance(commit.get("applied_concept_ids"), list) else 0,
                }), "INFO" if ok else "ERROR")
                if not ok:
                    return emit(block("Deterministic Loop Brief pattern commit failed. Inspect brief-pattern-commit.json and retry."))
        if role == "learning-auditor":
            send_otel(root, "agent.loop.learning.audit_reported", telemetry_attributes(event, platform, {"learning.health": body.get("verdict"), "human_review_required": bool(body.get("human_review_required"))}))
        if role == LOOP_BRIEF_ASSISTANT_ROLE:
            send_otel(root, "agent.loop.loop_brief_assistant.reported", telemetry_attributes(event, platform, {"brief_assistant.status": body.get("status"), "brief_assistant.mode": body.get("interaction_mode"), "brief_assistant.remaining_count": len(body.get("remaining_conditions", [])), "brief_assistant.question_count": len(body.get("questions_to_user", [])), "brief_pattern.candidate_count": len((body.get("pattern_retrieval") or {}).get("candidate_pattern_ids", [])), "brief_pattern.relevant_count": len((body.get("pattern_retrieval") or {}).get("relevant_pattern_ids", [])), "brief_pattern.proposal_count": len(body.get("pattern_proposals", []))}))
            send_otel(root, "agent.loop.brief_pattern.retrieved", telemetry_attributes(event, platform, {"brief_pattern.retrieval_performed": bool((body.get("pattern_retrieval") or {}).get("performed")), "brief_pattern.candidate_count": len((body.get("pattern_retrieval") or {}).get("candidate_pattern_ids", [])), "brief_pattern.relevant_count": len((body.get("pattern_retrieval") or {}).get("relevant_pattern_ids", [])), "brief_pattern.applied_count": len(body.get("pattern_application", []))}))
        if role == "gatekeeper":
            assessment = body.get("brief_pattern_assessment") if isinstance(body.get("brief_pattern_assessment"), dict) else {}
            send_otel(root, "agent.loop.brief_pattern.assessed", telemetry_attributes(event, platform, {"brief_pattern.accepted_count": len(assessment.get("accepted_proposal_ids", [])), "brief_pattern.rejected_count": len(assessment.get("rejected_proposal_ids", [])), "brief_pattern.challenged_count": len(assessment.get("challenged_proposal_ids", [])), "brief_pattern.capture_requested": body.get("assistant_handoff_reason") == "PATTERN_CAPTURE"}))
        return 0

    if name == "Stop":
        if any(isinstance(item, dict) and str(item.get("status", "")).lower() in {"running", "pending"} for item in (event.get("background_tasks") or [])):
            return 0
        if state.get("routing_mode") == DIRECT_ROUTING_MODE:
            if state.get("watchdog", {}).get("tripped"):
                return emit({"continue": False, "stopReason": "Watchdog tripped during direct execution.", "systemMessage": "Stop the direct task and request human intervention."})
            state["final_status"] = "DIRECT_COMPLETE"
            state["completed_at"] = now()
            save_runtime(root, event, state)
            atomic(target / "turn.json", state)
            send_otel(root, "agent.loop.direct.completed", telemetry_attributes(event, platform, {"routing.mode": DIRECT_ROUTING_MODE, "turn.status": "DIRECT_COMPLETE", "mutation.epoch": int(state.get("mutation_epoch", 0))}))
            return 0
        if state.get("routing_mode") == FRAME_ROUTING_MODE:
            frame = state.get("frame", {}) if isinstance(state.get("frame"), dict) else {}
            if not frame.get("loaded"):
                return emit({"continue": False, "stopReason": "Mandatory FRAME was not loaded.", "systemMessage": "Retry after installing the required frame-<name> skill."})
            if state.get("watchdog", {}).get("tripped"):
                return emit({"continue": False, "stopReason": "Watchdog tripped during FRAME execution.", "systemMessage": "Stop the FRAME and request human intervention; no autonomous recovery role is started in isolated FRAME mode."})
            state["final_status"] = "FRAME_COMPLETE"
            state["completed_at"] = now()
            save_runtime(root, event, state)
            atomic(target / "turn.json", state)
            send_otel(root, "agent.loop.frame.completed", telemetry_attributes(event, platform, {"routing.mode": FRAME_ROUTING_MODE, "skill.name": frame.get("required_skill"), "frame.header": frame.get("header"), "turn.status": "FRAME_COMPLETE", "mutation.epoch": int(state.get("mutation_epoch", 0))}))
            return 0
        if state.get("routing_mode") == SOP_ROUTING_MODE:
            sop = state.get("sop", {}) if isinstance(state.get("sop"), dict) else {}
            if not sop.get("loaded"):
                return emit({"continue": False, "stopReason": "Mandatory SOP was not loaded.", "systemMessage": "Retry after installing the required sop-<header> skill."})
            if state.get("watchdog", {}).get("tripped"):
                return emit({"continue": False, "stopReason": "Watchdog tripped during SOP execution.", "systemMessage": "Stop the SOP and request human intervention; no autonomous recovery role is started in isolated SOP mode."})
            if sop.get("required_skill") == LEARNING_AUDIT_SKILL:
                audit = load(target / "learning-auditor.json", {})
                if not audit.get("_trusted_subagent"):
                    return continuation(root, event, state, policy, "Run the deterministic learning-health report, invoke learning-auditor, and wait for its trusted JSON report before completing this SOP.")
            state["final_status"] = "SOP_COMPLETE"
            state["completed_at"] = now()
            save_runtime(root, event, state)
            atomic(target / "turn.json", state)
            send_otel(root, "agent.loop.sop.completed", telemetry_attributes(event, platform, {"routing.mode": SOP_ROUTING_MODE, "skill.name": sop.get("required_skill"), "sop.header": sop.get("header"), "turn.status": "SOP_COMPLETE", "mutation.epoch": int(state.get("mutation_epoch", 0))}))
            return 0
        gate = load(target / "gatekeeper.json", {})
        assistant = load(target / "loop-brief-assistant.json", {})
        prior_gate = load(target / "prior-gatekeeper.json", {})
        if state.get("entry_role") == LOOP_BRIEF_ASSISTANT_ROLE and not gate.get("_trusted_subagent"):
            if not assistant.get("_trusted_subagent"):
                return continuation(root, event, state, policy, "Invoke loop-brief-assistant with the user's new answers, prior-loop-brief-assistant.json, and prior-gatekeeper.json.")
            if assistant.get("status") == "ASK_USER":
                return emit({"continue": False, "stopReason": "Loop Brief Assistant requires additional user input.", "systemMessage": "Ask the user only these Loop Brief Assistant questions: " + json.dumps(assistant.get("questions_to_user", []), ensure_ascii=False)})
            if assistant.get("status") == "BLOCKED":
                return emit({"continue": False, "stopReason": "Loop Brief Assistant cannot complete the contract.", "systemMessage": "Explain these unresolved conflicts to the user: " + json.dumps(assistant.get("conflicts", []), ensure_ascii=False)})
            if assistant.get("status") == "READY_FOR_REVIEW":
                return continuation(root, event, state, policy, "Loop Brief Assistant produced a complete explicit draft. Invoke gatekeeper to independently validate loop-brief-draft.json; do not hand directly to Sensemaker.")
        if not gate.get("_trusted_subagent"):
            return continuation(root, event, state, policy, "Invoke gatekeeper and wait for its trusted JSON report before responding to the user.")
        if gate.get("verdict") == "NEEDS_INPUT":
            fresh_assistant = assistant.get("_trusted_subagent") and assistant.get("_gatekeeper_recorded_at") == gate.get("_recorded_at")
            if not fresh_assistant:
                return continuation(root, event, state, policy, "Gatekeeper returned NEEDS_INPUT. Invoke loop-brief-assistant with gatekeeper.json to normalize the partial brief and ask the smallest useful question set.")
            if assistant.get("status") == "ASK_USER":
                return emit({"continue": False, "stopReason": "Loop Brief Assistant requires additional user input.", "systemMessage": "Ask the user only these Loop Brief Assistant questions: " + json.dumps(assistant.get("questions_to_user", []), ensure_ascii=False)})
            if assistant.get("status") == "BLOCKED":
                return emit({"continue": False, "stopReason": "Loop Brief Assistant cannot complete the contract.", "systemMessage": "Explain these unresolved conflicts to the user: " + json.dumps(assistant.get("conflicts", []), ensure_ascii=False)})
            if assistant.get("status") == "READY_FOR_REVIEW":
                return continuation(root, event, state, policy, "Loop Brief Assistant produced a revised draft. Invoke gatekeeper again to independently validate loop-brief-draft.json.")
        if gate.get("verdict") == "REJECT":
            return emit({"continue": False, "stopReason": "Gatekeeper rejected autonomous-loop startup.", "systemMessage": "Explain these Gatekeeper rejection reasons to the user: " + json.dumps(gate.get("rejection_reasons", []), ensure_ascii=False)})
        if gate.get("mode") == "ADVISORY_ONLY":
            return emit({"continue": False, "stopReason": "Gatekeeper classified the request as advisory-only.", "systemMessage": "Do not start an autonomous coding loop. Provide the Gatekeeper's normalized brief and limitations to the user."})
        if gate.get("verdict") == "READY" and gate.get("assistant_handoff_reason") == "PATTERN_CAPTURE":
            fresh_assistant = assistant.get("_trusted_subagent") and assistant.get("_gatekeeper_recorded_at") == gate.get("_recorded_at")
            if not fresh_assistant:
                return continuation(root, event, state, policy, "Gatekeeper requested PATTERN_CAPTURE. Invoke loop-brief-assistant in PATTERN_CAPTURE mode with gatekeeper.json and the normalized Loop Brief.")
            if assistant.get("status") == "BLOCKED":
                return emit({"continue": False, "stopReason": "Loop Brief pattern capture is blocked.", "systemMessage": "Explain these pattern-capture conflicts to the user: " + json.dumps(assistant.get("conflicts", []), ensure_ascii=False)})
            if assistant.get("status") == "ASK_USER":
                return emit({"continue": False, "stopReason": "Loop Brief pattern capture requires explicit user confirmation.", "systemMessage": "Ask the user only these Loop Brief pattern questions: " + json.dumps(assistant.get("questions_to_user", []), ensure_ascii=False)})
            if assistant.get("status") == "READY_FOR_REVIEW":
                return continuation(root, event, state, policy, "Loop Brief Assistant produced a pattern proposal. Invoke gatekeeper again to independently classify every proposal before Sensemaker.")
        pattern_assessment = gate.get("brief_pattern_assessment") if isinstance(gate.get("brief_pattern_assessment"), dict) else {}
        accepted_patterns = [str(value) for value in (pattern_assessment.get("accepted_proposal_ids") or [])]
        if accepted_patterns:
            curator = load(target / "brief-pattern-curator.json", {})
            if not curator.get("_trusted_subagent"):
                return continuation(root, event, state, policy, "Gatekeeper accepted reusable Loop Brief pattern proposals. Invoke brief-pattern-curator and wait for the deterministic OKF commit before Sensemaker.")
            if curator.get("status") == "BLOCKED":
                return emit({"continue": False, "stopReason": "Brief Pattern Curator blocked pattern promotion.", "systemMessage": "Resolve the recorded pattern conflicts or ask the user before starting the loop."})
            pattern_commit = load(target / "brief-pattern-commit.json", {})
            if not pattern_commit.get("ok"):
                return continuation(root, event, state, policy, "Brief Pattern Curator report exists but deterministic OKF commit did not succeed. Correct and rerun brief-pattern-curator.")
        if policy.get("require_gatekeeper_before_sensemaker", True):
            sense = load(target / "sensemaker.json", {})
            if not sense.get("_trusted_subagent"):
                return continuation(root, event, state, policy, "Gatekeeper is READY. Invoke sensemaker with the trusted normalized Loop Brief before completing or mutating product files.")
        if state.get("watchdog", {}).get("tripped"):
            recovery = load(target / "watchdog-recovery.json", {})
            if not recovery.get("_trusted_subagent"):
                return continuation(root, event, state, policy, "Watchdog is tripped. Invoke watchdog-recovery, then ask a human to reset the watchdog.")
            return emit({"continue": False, "stopReason": "Watchdog remains tripped; human reset is required.", "systemMessage": "A trusted recovery report exists, but only a human may reset the Watchdog."})
        if int(state.get("mutations", 0)) <= 0:
            return 0
        epoch = int(state.get("mutation_epoch", 0))
        if policy.get("require_state_steward_after_mutation", True):
            steward = load(target / "state-steward.json", {})
            if not steward.get("_trusted_subagent") or int(steward.get("_mutation_epoch", -1)) != epoch:
                return continuation(root, event, state, policy, "Invoke state-steward for the current mutation epoch and wait for its trusted JSON report.")
        if policy.get("require_meta_evaluator_after_mutation", True):
            evaluator = load(target / "meta-evaluator.json", {})
            if not evaluator.get("_trusted_subagent") or int(evaluator.get("_mutation_epoch", -1)) != epoch:
                return continuation(root, event, state, policy, "Invoke meta-evaluator for the current mutation epoch, using the frame, actual diff, validation evidence, and State Steward report.")
            if evaluator.get("verdict") == "REVISE":
                return continuation(root, event, state, policy, "Meta-Evaluator verdict is REVISE. Address required actions, then rerun State Steward and Meta-Evaluator. Required actions: " + json.dumps(evaluator.get("required_actions", []), ensure_ascii=False))
            if evaluator.get("verdict") == "ESCALATE":
                return emit({"continue": False, "stopReason": "Meta-Evaluator escalated the turn for human judgment.", "systemMessage": "Meta-Evaluator verdict: ESCALATE."})
            memory_assessment = evaluator.get("memory_assessment") if isinstance(evaluator.get("memory_assessment"), dict) else {}
            accepted_memory = [str(value) for value in (memory_assessment.get("accepted_proposal_ids") or [])]
            if accepted_memory:
                curator = load(target / "memory-curator.json", {})
                if not curator.get("_trusted_subagent") or int(curator.get("_mutation_epoch", -1)) != epoch:
                    return continuation(root, event, state, policy, "Meta-Evaluator accepted durable-memory proposals. Invoke memory-curator for the current mutation epoch and wait for the deterministic OKF commit.")
                if curator.get("status") == "BLOCKED":
                    return emit({"continue": False, "stopReason": "Memory Curator blocked durable-memory promotion.", "systemMessage": "Resolve the recorded memory conflicts or request human judgment before declaring the loop complete."})
                commit = load(target / "memory-commit.json", {})
                if not commit.get("ok"):
                    return continuation(root, event, state, policy, "Memory Curator report exists but the deterministic OKF commit did not succeed. Correct and rerun memory-curator.")
        state["final_status"] = "PASS"
        state["completed_at"] = now()
        save_runtime(root, event, state)
        atomic(target / "turn.json", state)
        if state.get("routing_mode") == LOOP_ROUTING_MODE:
            write_next_turn_handoff(root, state)
        try:
            observation, health = observe_learning_health(root, target)
            state["learning_observation"] = {"status": "RECORDED", "observation_complete": bool(observation.get("observation_complete")), "health": health.get("health")}
            metrics = health.get("metrics", {}) if isinstance(health.get("metrics"), dict) else {}
            send_otel(root, "agent.loop.learning.turn_observed", telemetry_attributes(event, platform, {
                "learning.observation_complete": bool(observation.get("observation_complete")),
                "learning.lessons_recorded": len(observation.get("learning_records", [])),
                "learning.prior_lessons_considered": len(observation.get("prior_learning_considered", [])),
                "learning.retrieval_performed": bool((observation.get("learning_retrieval") or {}).get("performed")),
                "learning.retrieval_candidate_count": len((observation.get("learning_retrieval") or {}).get("candidate_lesson_ids", [])),
                "learning.retrieval_relevant_count": len((observation.get("learning_retrieval") or {}).get("relevant_lesson_ids", [])),
                "learning.questions_updated": len(observation.get("question_updates", [])),
                "memory.retrieval_performed": bool((observation.get("memory_retrieval") or {}).get("performed")),
                "memory.retrieval_candidate_count": len((observation.get("memory_retrieval") or {}).get("candidate_concept_ids", [])),
                "memory.retrieval_relevant_count": len((observation.get("memory_retrieval") or {}).get("relevant_concept_ids", [])),
                "memory.proposal_count": len(observation.get("memory_proposals", [])),
                "memory.accepted_proposal_count": len((observation.get("memory_assessment") or {}).get("accepted_proposal_ids", [])),
                "memory.commit_ok": bool((observation.get("memory_commit") or {}).get("ok")),
                "memory.applied_count": int((observation.get("memory_commit") or {}).get("applied_count", 0) or 0),
            }))
            send_otel(root, "agent.loop.learning.health_updated", telemetry_attributes(event, platform, {
                "learning.health": health.get("health"),
                "learning.observation_coverage": metrics.get("observation_coverage"),
                "learning.retrieval_coverage": metrics.get("learning_retrieval_coverage"),
                "learning.reuse_rate": metrics.get("learning_reuse_rate"),
                "learning.chain_completion_rate": metrics.get("learning_chain_completion_rate"),
                "learning.helpful_reuse_rate": metrics.get("helpful_reuse_rate"),
                "learning.recurrence_after_learning_count": metrics.get("recurrence_after_learning_count"),
                "learning.overdue_question_count": metrics.get("overdue_question_count"),
                "learning.stale_lesson_count": metrics.get("stale_lesson_count"),
                "learning.unconsidered_relevant_count": metrics.get("unconsidered_relevant_lesson_count"),
                "learning.unassessed_reuse_count": metrics.get("unassessed_reuse_count"),
                "learning.debt_score": metrics.get("learning_debt_score"),
                "memory.retrieval_coverage": metrics.get("memory_retrieval_coverage"),
                "memory.promotion_completion_rate": metrics.get("memory_promotion_completion_rate"),
                "memory.commit_failure_count": metrics.get("memory_commit_failure_count"),
                "memory.accepted_not_committed_count": metrics.get("accepted_memory_not_committed_count"),
            }))
        except Exception as exc:
            state["learning_observation"] = {"status": "FAILED", "error_type": type(exc).__name__}
            append_jsonl(target / "journal.jsonl", {"time": now(), "event": "learning-observer-failed", "error_type": type(exc).__name__, "error_content_logged": False})
            send_otel(root, "agent.loop.learning.observation_failed", telemetry_attributes(event, platform, {"learning.observation_success": False, "error.type": type(exc).__name__}), "ERROR")
        save_runtime(root, event, state)
        atomic(target / "turn.json", state)
        send_otel(root, "agent.loop.turn.completed", telemetry_attributes(event, platform, {"turn.status": "PASS", "mutation.epoch": epoch}))
        return 0
    return 0


def reset(reason: str) -> int:
    if not sys.stdin.isatty():
        raise SystemExit("Watchdog reset requires an interactive TTY.")
    root = root_for()
    paths = sorted((root / ".agent-loop/runtime/sessions").glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not paths:
        raise SystemExit("No active session.")
    path = paths[0]
    state = load(path, {})
    target = turn_dir(root, state)
    recovery = load(target / "watchdog-recovery.json", {})
    if not recovery.get("_trusted_subagent"):
        raise SystemExit("No trusted watchdog-recovery report.")
    print(json.dumps(recovery, indent=2, ensure_ascii=False))
    if input(f"Type RESET to clear watchdog ({reason}): ") != "RESET":
        raise SystemExit("Cancelled.")
    state["watchdog"] = {"tripped": False, "reasons": [], "reset_at": now(), "reset_reason": reason}
    atomic(path, state)
    atomic(target / "turn.json", state)
    print("Watchdog reset.")
    return 0


def status() -> int:
    root = root_for()
    paths = sorted((root / ".agent-loop/runtime/sessions").glob("*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
    if not paths:
        print("{}")
        return 0
    state = load(paths[0], {})
    target = turn_dir(root, state)
    reports = {spec[1]: (target / spec[1]).exists() for spec in ROLES.values()}
    print(json.dumps({"runtime": state, "reports": reports}, indent=2, ensure_ascii=False))
    return 0


def telemetry_test(platform: str) -> int:
    root = root_for()
    event = {"hook_event_name": "PreToolUse", "session_id": "self-test", "turn_id": "self-test", "tool_name": "Bash", "tool_input": {"command": "SECRET=not-logged git status --porcelain"}}
    send_otel(root, "agent.loop.telemetry.self_test", telemetry_attributes(event, platform, {"self_test": True}))
    print("Sanitized telemetry self-test emitted or spooled.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("command", nargs="?", default="hook")
    parser.add_argument("--reason", default="")
    parser.add_argument("--platform", choices=["claude", "codex", "unknown"], default="unknown")
    args, _ = parser.parse_known_args()
    if args.command == "reset-watchdog":
        return reset(args.reason)
    if args.command == "status":
        return status()
    if args.command == "telemetry-test":
        return telemetry_test(args.platform)
    return handle(read_event(), args.platform)


if __name__ == "__main__":
    raise SystemExit(main())
