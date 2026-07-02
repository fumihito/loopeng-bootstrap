---
name: command-route
description: "Mandatory non-deterministic routing skill for prompts beginning with route:. Propose frame-* candidates, ask for more context when confidence is tied or low, and never invoke Gatekeeper."
---

# Command route

Use this skill only when the hook loads `command-route` from a leading `route:` header.

## Purpose

This is a pre-loop proposal mode.
It helps select an appropriate `frame-*` skill before the autonomous loop starts.
It does not hand the turn to Gatekeeper.

## Routing rules

- Only propose `frame-*` candidates.
- Never propose `command-route` itself.
- Use the canonical installed `frame-*` skills as the source of truth.
- Read each frame's optional companion `routing.md` hints when they exist.
- The companion file must contain one `route-hints-v1` fenced TOML block.
- Treat prior conversation context as relevant if it helps disambiguate the request.
- If the top two candidates are tied or effectively tied, ask the user for more context.

## Output contract

Return exactly one JSON object and no surrounding prose.

Required keys:

- `candidate_frames`
- `selected_frame`
- `needs_user_turn`
- `reason`
- `confidence`

Field guidance:

- `candidate_frames` is a ranked array of objects.
- Each candidate object must include `frame`, `confidence`, and `reason`.
- `selected_frame` is a single `frame-*` name when one frame is selected, or `null` when more context is needed.
- `needs_user_turn` is `true` when there are multiple plausible candidates, confidence is low, or the top two scores are within `0.2`.
- `reason` is a short explanation of the selection or fallback.
- `confidence` is the overall route confidence, from `0.0` to `1.0` in `0.1` steps.

## Candidate ranking

- Prefer the most specific applicable frame.
- If several frames fit, order them by confidence.
- Keep the top candidate and alternates separate in the ranked list.
- If the route cannot separate the candidates cleanly, return `needs_user_turn=true`.

## User-turn fallback

When `needs_user_turn=true`:

- explain briefly why the route is ambiguous;
- ask for the additional context needed to continue;
- do not select a frame yet.

The same `route:` session will be used again after the user answers.

## Selected-frame behavior

When one frame is selected:

- set `selected_frame` to that frame;
- keep `candidate_frames` ranked;
- make the result machine-readable so the hook can load the selected frame in the same route turn after it accepts the result.

## Guardrails

- Do not invoke Gatekeeper.
- Do not output free-form analysis outside the JSON object.
- Do not invent frames that are not installed.
- Do not route to `command-route` itself.
