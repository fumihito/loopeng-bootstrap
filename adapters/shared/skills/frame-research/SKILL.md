---
name: frame-research
description: "Research frame for external-source investigation, synthesis, and report-ready comparison."
user-invocable: true
---

## Purpose

Use this frame when the task is to compare, verify, and synthesize information from external sources.
It is for deep research only: public information, official documents, papers, standards, articles, vendor docs, and published examples.

Keep codebase analysis, implementation planning, and local repository change work out of scope.

## When to use

- You need source-backed comparison, not a single ungrounded answer
- Multiple positions, frameworks, or practices need to be weighed
- The question needs evidence, not just reasoning
- You may need to hand off the research result to another step

## Research discipline

- Prefer primary sources when available
- State when a source is secondary and what that limits
- Keep sources, findings, and interpretations distinct
- Call out contradictions between sources instead of smoothing them over
- Surface open questions instead of forcing closure

## Workflow

1. Define the research question and the boundary of the topic.
2. Search broadly enough to avoid a narrow or local maximum.
3. Compare sources, claims, and positions.
4. Identify the strongest competing interpretations.
5. Extract the practical implications or next actions.
6. Note what remains unresolved.

## When to invoke subframes

- Use `frame-research-tactics` when the research needs hypotheses and verification/falsification actions
- Use `frame-research-arch` when the research needs architecture options and tradeoffs
- Use `frame-first-principles` when the question needs decomposition before research can proceed
- Use `frame-cynefin` when the question may not yet be classifiable

## Notes to preserve from the distilled version

- Treat `research` as deep research, not code review or implementation planning
- Keep the possibility of a `diag`-style handoff in mind if the topic is actually about a failure or defect
- Let the research report remain source-driven rather than opinion-driven
- Do not skip competing viewpoints or opposite evidence

## Output structure

- Research question
- Source set
- Findings
- Competing interpretations
- Open questions
- Practical implications
- Next step

## Constraints

- Do not do implementation planning here
- Do not treat unsourced claims as conclusions
- Do not collapse disagreement into a single answer
- Do not hide unresolved uncertainty

