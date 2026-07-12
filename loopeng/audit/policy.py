from __future__ import annotations

import re
import shlex
from pathlib import Path
from typing import Any

PROTECTED_PATH_FRAGMENTS = (
    ".agent-loop/",
    "." + "codex/hooks.json",
    "." + "codex/agents/",
    "." + "agents/skills/",
    "." + "claude/settings.json",
    "." + "claude/agents/",
    "." + "claude/skills/",
    "AGENTS.md",
    "CLAUDE.md",
    ".env",
)

HIGH_RISK_COMMAND_PATTERNS = (
    "git push",
    "git rebase --force",
    "git reset --hard",
    "curl | sh",
)

DESTRUCTIVE_COMMAND_PATTERNS = (
    "rm -rf /",
    "mkfs",
    "dd if=",
    "shutdown",
    "fork bomb",
    "chmod -R 777 /",
    "curl|sh",
)

BUDGET_LIMITS = {
    "max_tool_calls": 40,
    "max_mutations": 20,
    "max_failures": 3,
    "same_action_repeats": 4,
}

AUDIT_TIMEOUT_SECONDS = 60
RETRIEVAL_VOLUME_THRESHOLD = 10
LEARNING_CAPTURE_LIMIT = 5

# Review-mode aggregation thresholds.  Keep these in policy so the digest
# and its tests share one auditable source of truth.
REVIEW_RECURRENCE_THRESHOLD = 3
REVIEW_OLDEST_COUNT = 3

# Finding drill-down bounds.  These are shared by audit sidecar production
# and review-dag detail rendering so stored and displayed data agree.
DETAIL_MESSAGE_MAX = 200
DETAIL_PATHS_MAX = 10
DETAIL_FINDINGS_MAX = 30

HARD_BLOCKS = {
    "destructive_command": "Categorically destructive command patterns",
    "secret_persistence": "Secrets or tokens written to durable artifacts",
    "okf_invalid_apply": "Invalid OKF report application",
    "out_of_repo_write": "Writes outside the repository root",
}


def _contains_destructive_command(command: str) -> bool:
    compact = re.sub(r"\s+", " ", command).strip().lower()
    return any(pattern.lower() in compact for pattern in DESTRUCTIVE_COMMAND_PATTERNS)


def _candidate_paths(tool_input: Any) -> list[str]:
    if not isinstance(tool_input, dict):
        return []
    values: list[str] = []
    for key in ("path", "file_path", "filename", "target", "destination"):
        value = tool_input.get(key)
        if isinstance(value, str):
            values.append(value)
    command = tool_input.get("command")
    if isinstance(command, str):
        # Only inspect shell operands that are syntactically write targets.
        # An absolute path mentioned by a read/echo command is not an
        # out-of-repository write.
        try:
            tokens = shlex.split(command)
        except ValueError:
            tokens = []
        for index, token in enumerate(tokens):
            if token in {">", ">>", "1>", "1>>", "2>", "2>>"} and index + 1 < len(tokens):
                values.append(tokens[index + 1])
            if token in {"cp", "mv", "install", "touch", "mkdir", "ln"}:
                operands = [item for item in tokens[index + 1:] if not item.startswith("-")]
                values.extend(operands[-1:] if token in {"cp", "mv", "install", "ln"} else operands)
    return values


def pre_tool_hard_block(payload: dict[str, Any], repo: Path) -> str | None:
    """Return only a declared PRE_TOOL hard-block reason, or ``None``.

    This is the single policy classifier used by hooks.  Alerts such as
    protected-path mutation and secret persistence remain post-tool checks.
    """
    tool_input = payload.get("tool_input")
    tool_name = str(payload.get("tool_name") or payload.get("tool") or "").lower()
    command = tool_input.get("command") if isinstance(tool_input, dict) else payload.get("command")
    if isinstance(command, str) and _contains_destructive_command(command):
        return HARD_BLOCKS["destructive_command"]
    root = repo.resolve()
    if not any(name in tool_name for name in ("write", "edit", "patch", "apply_patch", "bash", "shell")):
        return None
    for raw in _candidate_paths(tool_input):
        try:
            candidate = Path(raw).expanduser()
            if not candidate.is_absolute():
                candidate = root / candidate
            if not candidate.resolve().is_relative_to(root):
                return HARD_BLOCKS["out_of_repo_write"]
        except (OSError, RuntimeError):
            return HARD_BLOCKS["out_of_repo_write"]
    return None

ALERTS = {
    "protected_path_mutation": "critical",
    "intent_overdeclaration": "warn",
    "budget_exceeded": "warn",
    "journal_coverage": "critical",
    "single_author_memory_change": "warn",
    "unreviewed_claim_persisted": "warn",
    "learning_backlog": "info",
    "retrieval_volume": "info",
    "high_risk_command": "warn",
    "skill_structure_violation": "warn",
}
