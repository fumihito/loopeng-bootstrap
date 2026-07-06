---
name: frame-axis
description: "Decompose an overloaded term into independent axes, checking known frameworks first. Use when one word carries conflicting meanings, especially before it drives a decision or incentive. The point is to stop arguing about the word, not create a gamed target."
user-invocable: true
---

## Purpose

Use this frame when a single abstract word (quality, trust, safety, elegance,
alignment, and so on) is being used to mean several different things at
once, and disagreements about it never converge because people are really
disagreeing about different axes. The frame does not define the concept; it
finds the small number of independent dimensions that explain the
disagreement — the way the Kano model splits "quality" into must-be,
performance, and attractive dimensions instead of treating quality as one
scale. It also treats a specific failure mode as a first-class concern: any
axis derived here can later be adopted as a metric or incentive, at which
point Goodhart's Law applies (a measure that becomes a target stops being a
good measure). The frame does not claim to eliminate that risk — no
derivation method can — but it structurally reduces it by preferring known
tension-pair architectures and by forcing evaluation-bound axes to name a
guardrail counterpart.

## When to use

- Two people use the same word and keep talking past each other
- A decision keeps stalling because "it depends what you mean by X"
- A single score or checklist for X feels like it is hiding a real trade-off
- You suspect the word is doing the work of several different judgments
- The resulting axes may end up driving a decision, an evaluation, or an
  incentive, and you want to know that risk up front

## Workflow

1. Name the overloaded concept and collect 4-6 concrete cases where people
   disagreed about it, or where it was applied inconsistently.
2. Framework check: before inventing anything, check whether the shape of
   the disagreement matches a known framework (see the library below). If
   one matches closely, adapt its axes rather than re-derive from scratch;
   note the match and where it does not quite fit.
3. If no framework matches, propose candidate axes from the collected
   cases: for each disagreement, ask what independent variable would
   explain it if held apart from the others.
4. Orthogonality check: for every pair of candidate axes, look for a real
   or plausible case where they move in opposite directions. If no such
   case exists, the two axes are one axis; merge them.
5. Anchor check: for every surviving axis, name a concrete high-end and
   low-end example. An axis with no nameable anchor is not yet real;
   either sharpen it or drop it.
6. Usage check: for each surviving axis, decide whether it is diagnostic
   only (for understanding this conversation) or evaluation-bound (it may
   inform a decision, score, or incentive). Every evaluation-bound axis
   must be paired with a named guardrail counter-axis — the thing that
   would visibly get worse if this axis alone were optimized. If no
   plausible counterpart exists, say so explicitly as a residual risk
   rather than proceeding without one.
7. Residual check: try to place each of the original disagreements onto
   the surviving axes. If a disagreement does not land anywhere, either
   add an axis for it or report it as irreducible residue — do not
   force-fit it.
8. Map the actual question the user brought onto the axis coordinates and
   state what that placement implies for the decision.

### Framework library (check before deriving from scratch)

| Situation shape | Closest framework | What it already gives you |
|---|---|---|
| "Meets expectations" vs "delights beyond expectations" is being conflated | Kano model / Herzberg two-factor theory | Must-be / performance / attractive (Kano); hygiene vs motivator (Herzberg) |
| Need an exhaustive, non-overlapping breakdown, no inherent tension | MECE / issue tree | Mutually exclusive, collectively exhaustive sub-drivers |
| A system's quality attributes trade off against each other | ATAM utility tree / quality attribute scenarios | Explicit attribute-vs-attribute trade-off tree |
| An organizational capability is being described | VRIO / McKinsey 7S | Value/Rarity/Imitability/Organization; hard vs soft elements |
| A strategic position changes over time | Wardley Mapping | Visibility to user vs evolutionary maturity |
| The concept risks collapsing into one gamed metric | North Star Metric + guardrail metric / DORA Four Keys / Balanced Scorecard | Deliberately paired axes: optimizing one alone visibly degrades its counterpart |

This library is a set of candidates, not a forced fit. If the situation
does not resemble any row, say so and proceed to step 3 rather than
stretching a framework to cover it.

### Axis-count guidance

| Surviving axes | Reading |
|---|---|
| 1 | The word was not multi-dimensional after all; say so and stop — this is a valid, useful finding |
| 2-4 | Typical decomposition; proceed |
| 5+ | Likely under-merged; re-run the orthogonality check before proceeding |

### Boundary guidance

- Axes are a modeling choice for this conversation, not a claim about the
  concept's true structure. Say this explicitly in the output.
- Diagnostic axes (understanding only) do not need a guardrail
  counterpart. Evaluation-bound axes (may inform a decision, score, or
  incentive) always do — this is the frame's primary Goodhart-resistance
  mechanism, and it is a property of intended use, not of clever
  derivation. No derivation method makes an axis immune to gaming once it
  becomes a target; naming the counterpart only makes the gaming visible
  sooner.
- Do not let the frame become a scoring system unless the user asked for
  one; the goal is clarity, not a new dashboard.
- If every candidate axis fails the anchor check, the real problem may be
  that no one has a concrete case in mind at all — hand off to
  `frame-first-principles`.

## Output

- The overloaded concept
- Framework match, if any (which row of the library, and where it does not
  quite fit), or "derived from an original tension structure"
- Surviving axes, each with a definition and a high/low anchor example
- Axes considered and merged or dropped, with reason
- For each axis: diagnostic-only or evaluation-bound; if evaluation-bound,
  its named guardrail counter-axis, or an explicit note that none was found
- Residual disagreement not explained by any axis, if any
- The original question mapped onto axis coordinates
- What that mapping implies

## Exit

Stop once every original disagreement is either placed on an axis or named
as residue, the axis count has passed the orthogonality and anchor checks,
and every evaluation-bound axis has a named counterpart or an explicit
residual-risk note. State the modeling-choice caveat before handing off.

## Adjacent frames

- Use `frame-cynefin` when the axis in question is "how knowable is the
  right answer here", not the content of the disagreement itself.
- Use `frame-blind-spot` when the disagreement might be hiding an unstated
  commitment rather than a genuine second dimension.
- Use `frame-first-principles` when no one can produce a concrete case for
  any candidate axis.
- Use `frame-critical-review` once an axis position is being asserted as a
  factual claim that needs checking against evidence.
