from __future__ import annotations

from .common import AuditContext, AuditFinding
from ...memory_stats import collect_stats
from ..policy import DIVERGENCE_COMMITS_MIN, DIVERGENCE_COMMITS_ZERO_SEV, DIVERGENCE_OPS_MIN, DIVERGENCE_OPS_ZERO_SEV, DIVERGENCE_WINDOW


def check_memory_commit_divergence(context: AuditContext) -> list[AuditFinding]:
    if not (context.bundle_root / "log.jsonl").is_file():
        return []
    try:
        stats = collect_stats(context.repo, context.bundle_root)
    except (OSError, ValueError):
        return []
    item = stats["windows"].get(DIVERGENCE_WINDOW, {})
    ops, commits = int(item.get("ops", 0)), int(item.get("commits", 0))
    if commits >= DIVERGENCE_COMMITS_MIN and ops == 0:
        return [AuditFinding("memory_commit_divergence", DIVERGENCE_OPS_ZERO_SEV, f"memory/commit divergence rule A: {commits} non-LLMWiki commits but 0 memory operations in {DIVERGENCE_WINDOW}", (f"window={DIVERGENCE_WINDOW}", f"commits={commits}", "ops=0"))]
    if ops >= DIVERGENCE_OPS_MIN and commits == 0:
        return [AuditFinding("memory_commit_divergence", DIVERGENCE_COMMITS_ZERO_SEV, f"memory/commit divergence rule B: {ops} memory operations but 0 non-LLMWiki commits in {DIVERGENCE_WINDOW}", (f"window={DIVERGENCE_WINDOW}", "commits=0", f"ops={ops}"))]
    return []
