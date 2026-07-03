# Release Audit

This checklist is the repository's release-gate procedure for completion claims.
It is read-only except for the explicit audit log entry described below.

## Checklist

1. Run `pytest tests/` and require `failed 0` / `error 0`. Any skip must be explicit and justified.
2. Run `python3 utils/journal_sanitization_lint.py`.
3. Run `python3 .agent-loop/hooks/loop_hook.py --self-test --platform claude` and confirm it does not mutate `.agent-loop/runtime/`.
4. Run `pytest tests/test_installed_repo_self_sufficiency.py` and confirm both (a) and (b) execute when Go is available; if (a) skips, record the skip reason in `docs/audit-log.md`.
5. Verify every new "implemented" or "completed" claim in the relevant docs has a matching test ID, line reference, or lint reference attached.
6. Run `git status --porcelain` and confirm the only remaining diff is `docs/audit-log.md`.
7. Record the audit outcome in `docs/audit-log.md` with the date, commit, and concise result summary.
8. Confirm `.git/hooks/pre-push` is installed; if not, run `utils/install-dev-hooks.sh` from the repository root.
9. Before pushing, simulate the planned push through `python3 utils/audit_guard.py --repo .` with the relevant `refs/heads/<branch> <local-sha> refs/heads/<branch> $(git rev-parse origin/<branch>)` line and confirm exit 0.

The audit log uses two line types: `- <date> | audit <parent-full-hash> | <summary>` for canonical release audits, and `- <date> | note <target-full-hash> | <summary>` for supplementary notes and corrections. The `audit` hash is the full 40-character hash of the push's remote tip, meaning the commit that the push advances from; for an ordinary single-work-item push, that value matches the audited snapshot's current `HEAD`. If in doubt, use `git rev-parse origin/<branch>` as the source of truth. The pre-push guard only recognizes `audit` lines when it checks whether a push is covered.

## Notes

- The checklist is intentionally deterministic.
- If a prerequisite tool is missing, install or supply it before treating the audit as complete.
- The manual evidence review in step 5 is the only non-deterministic part; it must be noted explicitly in the audit record.
- When recording the audit hash, use the push's remote tip: the commit that the push advances from, typically `git rev-parse origin/<branch>`. Do not write the not-yet-created audit commit hash.
- If `pytest` is unavailable, `python3 -m unittest discover -s tests` is an acceptable substitute. If you use the substitute, state that explicitly in `docs/audit-log.md`.
- If Go is unavailable, the audit is partial and must say so explicitly; do not report it as a full audit.

The repository also ships `utils/audit_guard.py` and `utils/install-dev-hooks.sh` as an opt-in developer pre-push guard for audit-tracked changes. Run the installer from the repository root to write `.git/hooks/pre-push`, which blocks pushes that touch `.agent-loop/`, `tests/`, `install.py`, `utils/`, or `docs/loop-structure*` unless `docs/audit-log.md` already contains the parent hash of the earliest pushed commit.
