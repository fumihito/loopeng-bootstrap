---
name: frame-research
description: "Compare external sources and synthesize what they support. Use when published evidence, documents, or citations are the main input. The point is to separate source-backed conclusions from unresolved gaps."
user-invocable: true
---

## Purpose

Use this frame when the task is to compare, verify, and synthesize information from external sources. It is for deep research only: public information, official documents, papers, standards, articles, vendor docs, and published examples.

Keep codebase analysis, implementation planning, and local repository change work out of scope.

## When to use

- You need source-backed comparison, not a single ungrounded answer
- Multiple positions, frameworks, or practices need to be weighed
- The question needs evidence, not just reasoning

## Workflow

1. Define the research question and topic boundary.
2. Search broadly enough to avoid a narrow local maximum.
3. Compare sources, claims, and positions.
4. Identify the strongest competing interpretations.
5. Extract the practical implications or next actions.
6. Note what remains unresolved.

## Research discipline

- Prefer primary sources when available
- State when a source is secondary and what that limits
- Keep sources, findings, and interpretations distinct
- Call out contradictions instead of smoothing them over
- Surface open questions instead of forcing closure

## When to invoke subframes

- Use `frame-research-tactics` when the research needs hypotheses and verification/falsification actions
- Use `frame-research-arch` when the research needs architecture options and tradeoffs
- Use `frame-first-principles` when the question needs decomposition before research can proceed
- Use `frame-cynefin` when the question may not yet be classifiable

## Output

- Research question
- Source set
- Findings
- Competing interpretations
- Open questions
- Practical implications
- Next step

## Exit

End when the source-backed comparison is clear enough to hand off, or state the unresolved contradictions and the next source to seek.

## Adjacent frames

- Use `frame-research-tactics` when the source comparison has to become hypotheses, verification, and falsification actions.
- Use `frame-research-arch` when the question is about architecture options and their tradeoffs rather than source comparison.
- Use `frame-experiments` when the answer requires a real probe with a bounded blast radius.
- Use `frame-first-principles` when the problem is still too underspecified to compare sources cleanly.
