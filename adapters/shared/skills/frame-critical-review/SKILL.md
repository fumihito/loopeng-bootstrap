---
name: frame-critical-review
description: "Test claims, sources, and arguments for validity. Use when a finished document needs evidence-based review rather than a rewrite. The point is to compare grounds, warrants, and counterarguments before revising."
user-invocable: true
---

## Purpose

Use this frame when the question is not just whether a document is readable, but whether the argument holds. It maps claims, checks evidence, generates the strongest counterargument, and suggests how to strengthen the synthesis.

## When to use

- You have a finished document, claim set, or source bundle to review
- The issue is whether the argument stands up to evidence
- You need critique plus a path to stronger synthesis

## Workflow

1. Map the main claims.
2. Classify each claim type.
3. Verify factual or technical claims against sources.
4. Generate the strongest plausible antithesis.
5. Scan for blind spots.
6. Propose revisions and synthesis hints.
7. For each major challenge, state what observation would settle it.
8. If the claim survives, say so and explain why.

## Thesis map

For each claim, note:

- Claim
- Grounds
- Warrant
- Backing
- Qualifier
- Existing rebuttal
- Missing element

## Antithesis

For each major claim, generate the strongest plausible counterargument and the evidence needed to decide between them. Do not stop at a straw man.

## Blind spot scan

Check for:

- missing assumptions
- ambiguous definitions
- over-broad scope
- causal / correlational confusion
- unhandled counterexamples
- missing alternatives
- missing operational costs or failure modes

The boundary with `frame-blind-spot` is whether the issue is a testable claim. If there is no claim yet, surface the assumption or omission first. If the target survives scrutiny, say that it survived and why.

## Source priority

1. Primary source
2. Official documentation or official code
3. Direct tests / release notes / changelog
4. Secondary source only when primary sources are unavailable

If the primary source is missing, say so explicitly.

## Synthesis hint

Do not end with critique alone. Offer what to narrow, qualify, add, preempt, or synthesize more strongly.

## Output

- Thesis map
- Verification table
- Missing antitheses
- Blind spots
- Improvement proposals
- Synthesis hints
- Residual uncertainty

## Exit

End when the strongest counterarguments and evidence checks are on the table, or state the remaining uncertainty and its settling condition.

## Adjacent frames

- Use `frame-wall` when the argument may be downstream of a bad frame rather than a weak claim.
- Use `frame-blind-spot` when the issue is hidden assumptions, avoided alternatives, or an inference chain that is not yet a testable claim.
- Use `frame-proofread-ja` when the issue is sentence quality, notation, or readability rather than argument validity.
- Use `frame-first-principles` when the claim set is still too underspecified and needs decomposition before it can be reviewed.
