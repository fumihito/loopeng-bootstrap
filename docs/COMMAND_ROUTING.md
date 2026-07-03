# Command routing

`route:` is a dedicated pre-loop routing entrypoint. It exists outside the autonomous loop and is invoked only when the user explicitly chooses `route:`. It is separate from `direct:`, but like `direct:` it bypasses Gatekeeper for the current turn.

## Scope

`route:` activates `command-route`, a non-deterministic LLM-driven proposal mode for `frame-*` usage.

The command route does not hand the prompt to Gatekeeper.
It instead proposes one or more `frame-*` candidates, may ask the user for more context, and may immediately trigger a selected frame when a single result is sufficiently confident.

## Routing contract

- `route:` is the only trigger.
- `command-route` is called only for `route:` turns.
- The turn stays outside the autonomous loop.
- `command-route` never proposes itself.
- `command-route` only proposes `frame-*` usage.

## Candidate source of truth

The canonical `frame-*` skill files are the source of truth for candidate discovery.

- Candidate enumeration reads the installed canonical `frame-*` skills.
- Companion Markdown files named `routing.md` may be used as routing hints and weight signals.
- Each hint file lives next to its frame skill, for example `frame-plandev/routing.md`.
- The expected hint fields are `prefer`, `avoid`, `good_for`, `bad_for`, and `signals`.

## Frame differentiation

The table below is the human-readable routing map that must stay aligned with the `routing.md` files and the lint rules.
Each `summary` should say when to choose the frame instead of its neighbors.

| Cluster | Frame | Stage / target | Discriminating question | Send onward when |
|---|---|---|---|---|
| incident | `frame-distributed-incident-analysis` | Early triage for distributed, concurrent, timing-sensitive, duplicate, or partial-failure symptoms with limited evidence | Does this look distributed or concurrent, or is it still a single-local fault? | If the incident is live and the next step is diagnosis/stabilization, hand off to `frame-diag`; once the issue is contained and the task is redesign from the gap, hand off to `frame-waiwad-grill`. |
| incident | `frame-diag` | Live incident diagnosis and stabilization | Is the failure currently active and the task to diagnose or stabilize it? | If the symptoms point to timing, duplication, or partial failure across components, hand off to `frame-distributed-incident-analysis`; if the incident is already over and the task is redesign, hand off to `frame-waiwad-grill`. |
| incident | `frame-waiwad-grill` | Post-incident WAI/WAD review and condition redesign | Is the incident contained, and are you redesigning the conditions rather than diagnosing a live failure? | If the problem is still active, hand off to `frame-diag`; if the evidence is still too thin and the symptom pattern is distributed, hand off to `frame-distributed-incident-analysis`. |
| research | `frame-research` | External-source comparison and synthesis | Are you comparing published sources, documents, or evidence rather than planning a test or intervention? | If the evidence needs hypotheses and verification/falsification actions, hand off to `frame-research-tactics`; if the question is about architecture options, hand off to `frame-research-arch`; if the answer requires a live probe, hand off to `frame-experiments`. |
| research | `frame-research-tactics` | Hypothesis and verification planning | Do you already have sources or claims and now need a verification/falsification plan? | If you need to compare external sources again, hand off to `frame-research`; if the uncertainty requires a live probe with blast radius, hand off to `frame-experiments`. |
| research | `frame-research-arch` | Architecture option narrowing and tradeoff framing | Is the task to choose between design options and their conditions, not to run a probe? | If the design choice needs source-backed comparison, hand off to `frame-research`; if you need testable hypotheses or probes, hand off to `frame-research-tactics` or `frame-experiments`. |
| research | `frame-experiments` | Real intervention with bounded blast radius | Does the answer require a probe in the world, with blast radius, reversibility, and timebox stated? | If the problem can still be narrowed by comparing sources or designing checks on paper, hand off to `frame-research` or `frame-research-tactics`. |
| planning | `frame-plandev` | Multi-step delivery planning with phases, verification, and handoff | Do you need a phased delivery plan that includes decisions, verification, and the next handoff? | If the main work is dependency structure, hand off to `frame-plantask`; if you are compressing existing notes into a brief, hand off to `frame-smeac`. |
| planning | `frame-plantask` | Dependency DAG design and validation | Is the task mainly to make dependencies, order, and validation steps explicit? | If you need a phased delivery plan or decisions about what happens next, hand off to `frame-plandev`; if you need to compress an existing plan into a brief, hand off to `frame-smeac`. |
| planning | `frame-smeac` | Brief compression from existing notes | Is the input already a plan, incident note, or discussion that needs to be compressed into a handoffable brief? | If a new phased plan is needed, hand off to `frame-plandev`; if the structure still needs explicit dependencies, hand off to `frame-plantask`. |
| thinking-check | `frame-first-principles` | Future-facing decomposition before action | Is the work still underspecified and in need of decomposition before any response? | If the question is already a testable claim, hand off to `frame-critical-review`; if the hidden assumptions are the issue, hand off to `frame-blind-spot`. |
| thinking-check | `frame-critical-review` | Current test of testable claims | Is there a claim, source set, or argument that can be checked right now? | If the issue is not yet a testable claim but an implicit assumption or avoidance, hand off to `frame-blind-spot`; if the judgment sounds inherited, hand off to `frame-inertia`. |
| thinking-check | `frame-blind-spot` | Trace of hidden assumptions and omissions | Are you looking for what is being assumed, avoided, or left unsaid rather than a claim that can already be tested? | If the issue has become a testable claim, hand off to `frame-critical-review`; if the judgment is inherited or habitual, hand off to `frame-inertia`. |
| thinking-check | `frame-inertia` | Inherited judgment or conventional choice audit | Is the question whether a decision is still justified or only being repeated by habit, authority, or metric fixation? | If the judgment should be justified from scratch, hand off to `frame-first-principles`; if there is a testable claim to check, hand off to `frame-critical-review`. |
| independent | `frame-cynefin` | Pre-classification of domain before a frame choice | Do you need to classify the domain first, before choosing among research, planning, experiment, or incident frames? | `Complex` points to `frame-experiments` when probing is required; `Complicated` points to `frame-research` or `frame-research-tactics` when comparison and hypothesis narrowing are enough; `Chaotic` points to `frame-distributed-incident-analysis` and then `frame-diag` for stabilization; `Clear` can proceed to `frame-plandev` or `frame-plantask`; `Disorder` should fall back to `frame-first-principles`. Do not auto-connect the next frame from `frame-cynefin`; keep the choice explicit. |
| independent | `frame-proofread-ja` | Japanese surface-quality review | Is the issue sentence-level Japanese quality, not argument validity or planning? | If the problem is really about whether the claim holds, hand off to `frame-critical-review`; if the issue is actually planning or decomposition, hand off to the appropriate planning or thinking frame. |

## Output contract

`command-route` must return structured output.

Required fields:

- `candidate_frames`
- `selected_frame`
- `needs_user_turn`
- `reason`
- `confidence`

Output guidance:

- `candidate_frames` contains the ranked alternatives.
- `selected_frame` is a single frame when the route is confident enough to proceed.
- `needs_user_turn` is `true` when the route needs more context or cannot choose confidently.
- `reason` explains the proposal briefly.
- `confidence` is a numeric score from `0.0` to `1.0` in `0.1` steps.
- `candidate_frames` is a ranked array of objects with `frame`, `confidence`, and `reason`.

## Confidence rule

- Confidence uses `0.0` to `1.0` in `0.1` increments.
- If the top two candidates differ by `0.2` or less, they are treated as effectively tied.
- Ties and low-confidence results should set `needs_user_turn=true`.

## Multi-candidate behavior

- When multiple candidates exist, the route separates the top candidate from alternates.
- The route may return several candidates even when it also selects one.
- If the route cannot separate candidates cleanly, it asks the user for more context.

## User-turn fallback

When `needs_user_turn=true`:

- the route returns a user-facing turn instead of proceeding to Gatekeeper;
- the user is asked for additional context;
- the additional context is routed back through the same `route:` session;
- routing continues until a single `selected_frame` is produced.

## Frame activation

When `selected_frame` resolves to a single frame:

- the hook loads the selected frame immediately in the same route turn;
- the selected frame becomes the next active routed mode before the turn exits;
- the route turn ends after the frame has been loaded.

## Input scope

The route may use:

- the text after `route:`;
- prior conversation context in the same session.

## Recursion guard

`command-route` must not propose `command-route` itself.
This avoids self-routing loops and black-hole behavior.

## Observability

The minimal record must show:

- that `route:` was invoked;
- that `command-route` made a proposal;
- which `frame-*` was ultimately selected.

The intent is to make the route path visible without requiring full semantic quality metrics in the MVP.

## Priority and interaction model

- `route:` is handled before `direct:`.
- `route:` is not a synonym for Gatekeeper input.
- The route path is a separate entry path for exploratory frame selection.

## Companion routing hints

Each `frame-*` skill may have a sibling `routing.md` file with a single fenced machine block.

Example:

```route-hints-v1
schema = "routing-hints/v1"
frame = "frame-plandev"
priority = 50
summary = "Multi-step delivery work with scope, phases, verification, and handoff."

[[prefer]]
phrase = "multi-step delivery"
aliases = ["phased implementation", "milestone planning"]
weight = 4

[[avoid]]
phrase = "one-off question"
aliases = ["simple lookup", "single answer"]
weight = -4

[[good_for]]
phrase = "handoff"
aliases = ["transition", "handover"]
weight = 2

[[bad_for]]
phrase = "root cause analysis"
aliases = ["bug triage", "incident diagnosis"]
weight = -2

[[signals]]
phrase = "scope"
weight = 1
```

Rules:

- the fence label must be `route-hints-v1`;
- the TOML body is the source of truth for lint and routing;
- `schema` must be `routing-hints/v1`;
- `frame` must match the parent skill directory name;
- `priority` is an integer from `0` to `100`;
- `priority` is the base score applied before section weights;
- each section entry must have `phrase` and `weight`;
- `aliases` is optional and must be a string array when present;
- `prefer` and `good_for` must use positive weights;
- `avoid` and `bad_for` must use negative weights;
- `signals` uses a weak positive weight.

## Implementation notes

The current implementation uses:

- a `route-hints-v1` fenced TOML block in each `routing.md`;
- parsed `prefer`, `avoid`, `good_for`, `bad_for`, and `signals` arrays of tables;
- a route-aware shortlist of candidate frames, ranked before prompt assembly;
- a dedicated routing lint that validates the block and field constraints;
- route telemetry for load, selection, fallback, and frame activation.

Further improvements can extend the hint schema or add more edge-case tests, but the core wiring is now in place.
