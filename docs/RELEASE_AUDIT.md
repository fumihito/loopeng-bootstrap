# Release Audit

This checklist is the repository's release-gate procedure for completion claims.
It is read-only except for the explicit audit log entry described below.

## Checklist

1. Run `pytest tests/` and require `failed 0` / `error 0`. Any skip must be explicit and justified.
2. Run `python3 utils/journal_sanitization_lint.py`.
3. Run `python3 .agent-loop/hooks/loop_hook.py --self-test --platform claude`.
4. Verify every new "implemented" or "completed" claim in the relevant docs has a matching test ID, line reference, or lint reference attached.
5. Record the audit outcome in `docs/audit-log.md` with the date, commit, and concise result summary.

## Notes

- The checklist is intentionally deterministic.
- If a prerequisite tool is missing, install or supply it before treating the audit as complete.
- The manual evidence review in step 4 is the only non-deterministic part; it must be noted explicitly in the audit record.
