# Recovery

`python3 -m loopeng doctor` is read-only and reports malformed state JSON/JSONL,
stale locks, orphaned active-run registrations, bundle validation failures,
draft state, and report/journal mismatches. `python3 -m loopeng doctor --fix`
only removes stale locks, removes orphan registrations, and copies malformed
JSONL into `.quarantine/`; it never deletes the original or repairs bundle
content.

For non-repairable conditions: restore the LLMWiki bundle from the OKF backup,
re-run `loopeng doctor`, isolate the affected journal and re-run `loopeng audit
run`, then re-register hooks with the installer. Human review is required before
declaring a recovered run complete.
