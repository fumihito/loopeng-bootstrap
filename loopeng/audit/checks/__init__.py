from __future__ import annotations

from .budget_exceeded import check_budget_exceeded
from .common import AuditContext, AuditFinding, collect_context
from .destructive_command import check_destructive_command
from .high_risk_command import check_high_risk_command
from .journal_coverage import check_journal_coverage
from .learning_backlog import check_learning_backlog
from .out_of_repo_write import check_out_of_repo_write
from .protected_path_mutation import check_protected_path_mutation
from .intent_overdeclaration import check_intent_overdeclaration
from .secret_persistence import check_secret_persistence
from .single_author_memory_change import check_single_author_memory_change
from .skill_structure_violation import check_skill_structure_violation
from .unreviewed_claim_persisted import check_unreviewed_claim_persisted
from .retrieval_volume import check_retrieval_volume
from .provisional_stagnation import check_provisional_stagnation
from .memory_commit_divergence import check_memory_commit_divergence
from .outcome_missing import check_outcome_missing
from .concurrent_runs_detected import check_concurrent_runs_detected
from .memory_instruction_smell import check_memory_instruction_smell
from .learning_ineffective import check_learning_ineffective
from .inbox_stale import check_inbox_stale
from .external_review_overdue import check_external_review_overdue
from .external_review_failed import check_external_review_failed
from .wiki_space_mismatch import check_wiki_space_mismatch


CHECKS = (
    check_destructive_command,
    check_secret_persistence,
    check_out_of_repo_write,
    check_protected_path_mutation,
    check_intent_overdeclaration,
    check_budget_exceeded,
    check_journal_coverage,
    check_single_author_memory_change,
    check_unreviewed_claim_persisted,
    check_learning_backlog,
    check_high_risk_command,
    check_skill_structure_violation,
    check_retrieval_volume,
    check_provisional_stagnation,
    check_memory_commit_divergence,
    check_outcome_missing,
    check_concurrent_runs_detected,
    check_memory_instruction_smell,
    check_learning_ineffective,
    check_inbox_stale,
    check_external_review_overdue,
    check_external_review_failed,
    check_wiki_space_mismatch,
)


def run_checks(context: AuditContext) -> list[AuditFinding]:
    findings: list[AuditFinding] = []
    for check in CHECKS:
        findings.extend(check(context))
    return findings
