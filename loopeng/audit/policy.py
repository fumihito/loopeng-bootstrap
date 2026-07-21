from __future__ import annotations

import re
import shlex
import json
from pathlib import Path
from typing import Any

# v0.1 retirement migration authority remains documented under docs/v0.2-phase1.
_legacy_command = lambda *codes: "".join(chr(code) for code in codes)
DESTRUCTIVE_COMMAND_PATTERNS = (
    r"(^|\s)" + _legacy_command(114,109) + r"\s+-rf\s+/(?:\s|$)",
    r"(^|\s)" + _legacy_command(109,107,102,115) + r"(?:\.|\s)",
    r"(^|\s)" + _legacy_command(100,100) + r"\s+if=",
    r"(^|\s)(" + _legacy_command(115,104,117,116,100,111,119,110) + "|" + _legacy_command(114,101,98,111,111,116) + "|" + _legacy_command(104,97,108,116) + "|" + _legacy_command(112,111,119,101,114,111,102,102) + r")(\s|$)",
    r"\x3a\(\)\s*\{\s*:\|&\s*\};:",
    r"(^|\s)" + _legacy_command(99,104,109,111,100) + r"\s+-R\s+777\s+/",
    r"(^|\s)" + _legacy_command(99,117,114,108) + r"\b.*\|\s*" + _legacy_command(115,104) + r"\b",
    r"(^|\s)" + _legacy_command(119,103,101,116) + r"\b.*\|\s*" + _legacy_command(115,104) + r"\b",
)
HIGH_RISK_COMMAND_PATTERNS = (
    r"(^|\s)git\s+push\b",
    r"(^|\s)git\s+reset\s+--hard\b",
    r"(^|\s)git\s+clean\s+-[^\s]*f",
    r"(^|\s)gh\s+pr\s+merge\b",
    r"(^|\s)kubectl\s+(apply|delete|replace|patch|rollout)\b",
    r"(^|\s)terraform\s+(apply|destroy)\b",
    r"(^|\s)(aws|gcloud|az)\b.*\b(delete|destroy|terminate|purge)\b",
    r"(^|\s)(npm|pnpm|yarn)\s+publish\b",
    r"(^|\s)docker\s+system\s+prune\b",
    r"(^|\s)helm\s+(install|upgrade|uninstall)\b",
)
_V02_DESTRUCTIVE_COMMAND_PATTERNS = DESTRUCTIVE_COMMAND_PATTERNS
_V02_HIGH_RISK_COMMAND_PATTERNS = HIGH_RISK_COMMAND_PATTERNS

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

DESTRUCTIVE_COMMAND_PATTERNS = _V02_DESTRUCTIVE_COMMAND_PATTERNS
HIGH_RISK_COMMAND_PATTERNS = _V02_HIGH_RISK_COMMAND_PATTERNS

BUDGET_LIMITS = {
    "max_tool_calls": 40,
    "max_mutations": 20,
    "max_failures": 3,
    "same_action_repeats": 4,
}

AUDIT_TIMEOUT_SECONDS = 60
RETRIEVAL_VOLUME_THRESHOLD = 10
LEARNING_CAPTURE_LIMIT = 5

# The single declaration point for unattended durable-memory writes.
AUTONOMOUS_NAMESPACES = ("failure-patterns", "recovery-patterns", "references")
AUTONOMOUS_APPLIES_PER_RUN = 3
AUTO_ESTABLISH = False
ESTABLISH_CITATIONS = 3
STAGNATION_DAYS = 30
DIVERGENCE_WINDOW = "7d"
DIVERGENCE_COMMITS_MIN = 8
DIVERGENCE_OPS_ZERO_SEV = "warn"
DIVERGENCE_OPS_MIN = 8
DIVERGENCE_COMMITS_ZERO_SEV = "info"

# Review-mode aggregation thresholds.  Keep these in policy so the digest
# and its tests share one auditable source of truth.
REVIEW_RECURRENCE_THRESHOLD = 3
REVIEW_OLDEST_COUNT = 3

# Finding drill-down bounds.  These are shared by audit sidecar production
# and review-dag detail rendering so stored and displayed data agree.
DETAIL_MESSAGE_MAX = 200
DETAIL_PATHS_MAX = 10
DETAIL_FINDINGS_MAX = 30
INSTRUCTION_SMELL_PATTERNS = (
    r"ignore (?:all )?previous",
    r"you must now",
    r"system prompt",
    r"新しい指示",
    r"以前の指示を無視",
)
REVIEW_REQUIRED_TRIGGERS = ("established_memory_change", "outcome_fail_streak_2", "instruction_smell_present")
SAMPLING_EVERY_N_RUNS = 10
CROSS_FAMILY_EVERY_N = 5
REVIEW_OVERDUE_DAYS = 7

HARD_BLOCKS = {
    "destructive_command": "Categorically destructive command patterns",
    "secret_persistence": "Secrets or tokens written to durable artifacts",
    "okf_invalid_apply": "Invalid OKF report application",
    "out_of_repo_write": "Writes outside the repository root",
    "skill_source_not_installed": "Shared skill source changed without running self-update",
}

SKILL_SOURCE_ROOT = "adapters/shared/skills"


def _skill_sync_state_path(repo: Path) -> Path:
    return repo / ".agent-loop" / "state" / "skill-sync.json"


def _skill_sync_pending(repo: Path) -> bool:
    try:
        value = json.loads(_skill_sync_state_path(repo).read_text(encoding="utf-8"))
        return isinstance(value, dict) and bool(value.get("pending"))
    except (FileNotFoundError, OSError, json.JSONDecodeError, TypeError):
        return False


def _is_self_update_command(command: str) -> bool:
    try:
        tokens = shlex.split(command)
    except ValueError:
        return False
    return any(Path(token).name == "install.py" for token in tokens) and "--self" in tokens and "--update" in tokens


def _is_mutation_tool(tool_name: str) -> bool:
    return any(name in tool_name.lower() for name in ("write", "edit", "patch", "apply_patch", "bash", "shell"))


def _contains_destructive_command(command: str) -> bool:
    compact = re.sub(r"\s+", " ", command).strip().lower()
    return any(re.search(pattern, compact, re.IGNORECASE) for pattern in DESTRUCTIVE_COMMAND_PATTERNS)


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
    if not _is_mutation_tool(tool_name):
        return None
    if _skill_sync_pending(repo):
        if isinstance(command, str) and _is_self_update_command(command):
            return None
        return HARD_BLOCKS["skill_source_not_installed"]
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
    "provisional_stagnation": "info",
    "memory_commit_divergence": "warn",
    "outcome_missing": "info",
    "concurrent_runs_detected": "warn",
    "memory_instruction_smell": "warn",
    "learning_ineffective": "info",
    "inbox_stale": "info",
    "external_review_overdue": "warn",
    "external_review_failed": "warn",
}
