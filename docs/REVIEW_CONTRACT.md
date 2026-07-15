# External Review Contract

Review reports are accepted only when they are JSON matching
contract version 1. Semantic judgment remains with the external reviewer;
`loopeng review intake` performs schema validation, packet identity checks,
evidence-pointer resolution, and deterministic cross-checks.

```json
{"contract":1,"reviewer":{"model":"<model id>","session":"<new session id>","relation":"external|self-family"},"packet":{"run_id":"...","packet_hash":"<sha256>"},"dimensions":[{"id":"D1","verdict":"pass|fail|unable","evidence":[{"ref":"journal:<run>:<line>","note":"..."}],"note":"..."}],"overall":"pass|fail|blocked-on-info","findings":["..."],"meta_review":{"decision":"accept","spot_dim":"D3","spot_result":"ok","authorization":"tui-interactive"}}
```

The fixed dimensions are D1 process consistency, D2 outcome validity, D3
memory-write quality (including approval decision quote validity), D4 alert handling, and D5 one randomly selected
implementation claim inspected at a named file and line. Request generation
selects and records one `d5_target` in the packet manifest and journal; D5
evidence must match it exactly. Every non-`unable`
dimension requires at least one evidence pointer; D5 always requires a
`file:<path>:<line>` pointer. Three or more `unable` verdicts require
`blocked-on-info`.

`review intake` checks contract fields, packet SHA-256 identity, journal/file/
report/sidecar pointer existence, D2 outcome consistency, D3 memory-write
claims, D4 critical/warn counts, D5 target, and reviewer relation. `external`
is accepted normally. `self-family` requires a TUI meta-review decision and
is never accepted by `--auto`; without it the report remains incoming with
"meta-review required — use inbox --tui". Direct
`tui-interactive` decision events are valid without a quote; the direct user
operation is the authorization record. A reviewer
model matching the run agent is accepted with a `self_review` warning. On
acceptance it appends `external-review`; only that event resolves the due item.

The configured review actor is a separate agent. Review execution and result
return are outside this deterministic mechanism.

The HTML review view is a read-only, HTTPS-only escape hatch from the TUI for
the dimension table and resolved evidence excerpts.

Standard handoff: `python3 -m loopeng review request --run <run-id>` creates
the incoming drop-off directory; save the contract JSON there, then run
`python3 -m loopeng review intake --auto`. Incoming filenames are arbitrary.
Accepted files move to `accepted/`, malformed JSON to `rejected-intake/`, and
valid but rejected contracts remain in `incoming/`.

```bash
./loopeng.py review request --run latest-due
# deliver the request to the reviewer; the JSON is saved under incoming/
./loopeng.py inbox --tui
# or: ./loopeng.py review intake --auto
```
