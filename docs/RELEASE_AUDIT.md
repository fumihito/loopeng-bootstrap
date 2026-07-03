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

## Notes

- The checklist is intentionally deterministic.
- If a prerequisite tool is missing, install or supply it before treating the audit as complete.
- The manual evidence review in step 5 is the only non-deterministic part; it must be noted explicitly in the audit record.
- When recording the audit hash, use the parent commit of the audited snapshot, which is the current `HEAD` at record time. Do not write the not-yet-created audit commit hash.
- If `pytest` is unavailable, `python3 -m unittest discover -s tests` is an acceptable substitute. If you use the substitute, state that explicitly in `docs/audit-log.md`.
- If Go is unavailable, the audit is partial and must say so explicitly; do not report it as a full audit.
