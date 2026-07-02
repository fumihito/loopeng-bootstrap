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
