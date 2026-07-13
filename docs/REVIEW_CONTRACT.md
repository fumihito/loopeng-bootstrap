# External Review Contract

External-agent review reports are accepted only when they are JSON matching
contract version 1. Semantic judgment remains with the external reviewer;
`loopeng review intake` performs schema validation, packet identity checks,
evidence-pointer resolution, and deterministic cross-checks.

```json
{"contract":1,"reviewer":{"model":"<model id>","session":"<free text>","relation":"external"},"packet":{"run_id":"...","packet_hash":"<sha256>"},"dimensions":[{"id":"D1","verdict":"pass|fail|unable","evidence":[{"ref":"journal:<run>:<line>","note":"..."}],"note":"..."}],"overall":"pass|fail|blocked-on-info","findings":["..."]}
```

The fixed dimensions are D1 process consistency, D2 outcome validity, D3
memory-write quality (including approval decision quote validity), D4 alert handling, and D5 one randomly selected
implementation claim inspected at a named file and line. Every non-`unable`
dimension requires at least one evidence pointer; D5 always requires a
`file:<path>:<line>` pointer. Three or more `unable` verdicts require
`blocked-on-info`.

`review intake` checks contract fields, packet SHA-256 identity, journal/file/
report/sidecar pointer existence, D2 outcome consistency, D3 memory-write
claims, D4 critical/warn counts, and external reviewer relation. Direct
`tui-interactive` decision events are valid without a quote; the direct user
operation is the authorization record. A reviewer
model matching the run agent is accepted with a `self_review` warning. On
acceptance it appends `external-review`; only that event resolves the due item.

The configured review actor is a separate agent. Review execution and result
return are outside this deterministic mechanism.
