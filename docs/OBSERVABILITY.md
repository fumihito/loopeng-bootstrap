# Observability

This repository exposes two deterministic observation surfaces:

- `learning_health.py` rebuilds the cross-turn learning summary and learning-debt metrics.
- `loop_status.py` renders the live loop-health view from the current runtime artifacts.

## Loop status

`loop_status.py` reads only the deterministic turn artifacts, scheduler events, and policy files. It does not call an LLM.

```bash
python3 .agent-loop/bin/loop_status.py --text
python3 .agent-loop/bin/loop_status.py --html
```

The HTML output is self-contained and written to `.agent-loop/runtime/status.html` by default.
When `.agent-loop/scheduler-policy.json` sets `render_status_page` to `true`, the persistent scheduler daemon regenerates the same page at the end of each cycle.

The status page intentionally omits Loop Brief goal text by default. The page is meant for local operational triage, so the default view favors IDs, states, counts, timestamps, and hashes over content. Use `--include-brief` only when the operator explicitly wants to see brief text in the local page.

Verified by `tests/test_loop_status.py::LoopStatusTests`.

## Learning observability

See `docs/LEARNING_OBSERVABILITY.md` for the cross-turn learning observer, metrics, and audit workflow.
