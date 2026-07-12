# Release Audit

This checklist is the repository's release-gate procedure for completion claims.
It is read-only except for the explicit audit log entry created by `record`.

## Primary path

1. Run `python3 utils/audit_guard.py record [--branch <branch>] [--summary "..."]` from a clean worktree.
   The command is the canonical release-gate action and it internally runs:
   - the test suite with `pytest tests -q`, or `python3 -m unittest discover -s tests -q` if `pytest` is unavailable;
   - `python3 utils/journal_sanitization_lint.py`;
   - `python3 utils/routing_hints_lint.py --root .`;
   - `python3 utils/completion_protocol_lint.py --root .`;
   - `python3 utils/skill_structure_lint.py --root .`;
   - `python3 .agent-loop/hooks/loop_hook.py --self-test --platform claude`.
   It appends `- <date> | audit <origin/<branch>-hash> | <deterministic summary>` to `docs/audit-log.md` only when every check passes.
2. If `record` fails, fix the reported issue and rerun `record`. Do not hand-write a failed audit line.
3. `record` commits the generated entry automatically: it amends HEAD when safe and otherwise creates the separate `audit: record release gate` commit.
4. Confirm `.git/hooks/pre-push` is installed; if not, run `utils/install-dev-hooks.sh` from the repository root.
5. Before pushing, simulate the planned push through `python3 utils/audit_guard.py --repo .` with the relevant `refs/heads/<branch> <local-sha> refs/heads/<branch> $(git rev-parse origin/<branch>)` line and confirm exit 0.

## Fallback path

Use this only if `record` cannot be run directly in the current environment.

1. Run `pytest tests/` and require `failed 0` / `error 0`. If `pytest` is unavailable, `python3 -m unittest discover -s tests` is acceptable and must be noted in `docs/audit-log.md`.
2. Run `python3 utils/journal_sanitization_lint.py`.
3. Run `python3 utils/routing_hints_lint.py --root .`.
4. Run `python3 utils/completion_protocol_lint.py --root .`.
5. Run `python3 .agent-loop/hooks/loop_hook.py --self-test --platform claude` and confirm it does not mutate `.agent-loop/runtime/`.
6. Run `pytest tests/test_installed_repo_self_sufficiency.py` and confirm both (a) and (b) execute when Go is available; if (a) skips, record the skip reason in `docs/audit-log.md`.
7. Verify every new "implemented" or "completed" claim in the relevant docs has a matching test ID, line reference, or lint reference attached.
8. Run `git status --porcelain` and confirm the only remaining diff is `docs/audit-log.md`.
9. Record the audit outcome in `docs/audit-log.md` with the date, commit, and concise result summary.
10. Run `python3 utils/audit_guard.py --repo .` with the relevant `refs/heads/<branch> <local-sha> refs/heads/<branch> $(git rev-parse origin/<branch>)` line and confirm exit 0.

The audit log uses two line types: `- <date> | audit <parent-full-hash> | <summary>` for canonical release audits, and `- <date> | note <target-full-hash> | <summary>` for supplementary notes and corrections. The `audit` hash is the full 40-character hash of the push's remote tip, meaning the commit that the push advances from; for an ordinary single-work-item push, that value matches the audited snapshot's current `HEAD`. If in doubt, use `git rev-parse origin/<branch>` as the source of truth. The pre-push guard only recognizes `audit` lines when it checks whether a push is covered.

## Notes

- The checklist is intentionally deterministic.
- If a prerequisite tool is missing, install or supply it before treating the audit as complete.
- The manual evidence review in step 7 is the only non-deterministic part; it must be noted explicitly in the audit record.
- When recording the audit hash, use the push's remote tip: the commit that the push advances from, typically `git rev-parse origin/<branch>`. Do not write the not-yet-created audit commit hash.
- If `pytest` is unavailable, `python3 -m unittest discover -s tests` is an acceptable substitute. If you use the substitute, state that explicitly in `docs/audit-log.md`.
- If Go is unavailable, the audit is partial and must say so explicitly; do not report it as a full audit.

The repository also ships `utils/audit_guard.py` and `utils/install-dev-hooks.sh` as an opt-in developer pre-push guard for audit-tracked changes. Run the installer from the repository root to write `.git/hooks/pre-push`, which blocks pushes that touch `.agent-loop/`, `tests/`, `install.py`, `utils/`, or `docs/loop-structure*` unless `docs/audit-log.md` already contains the parent hash of the earliest pushed commit.
