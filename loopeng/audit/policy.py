from __future__ import annotations

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

HARD_BLOCKS = {
    "destructive_command": "Categorically destructive command patterns",
    "secret_persistence": "Secrets or tokens written to durable artifacts",
    "okf_invalid_apply": "Invalid OKF report application",
    "out_of_repo_write": "Writes outside the repository root",
}

ALERTS = {
    "protected_path_mutation": "critical",
    "budget_exceeded": "warn",
    "journal_coverage": "critical",
    "single_author_memory_change": "warn",
    "unreviewed_claim_persisted": "warn",
    "learning_backlog": "info",
    "high_risk_command": "warn",
    "skill_structure_violation": "warn",
}
