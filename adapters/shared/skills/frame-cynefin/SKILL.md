---
name: frame-cynefin
description: "Classify a problem by domain and choose the right next step for Clear, Complicated, Complex, Chaotic, or Disorder."
user-invocable: true
---

## Purpose

Use this frame when the correct response depends on the domain.
It helps decide whether to apply best practice, analysis, experimentation, stop-the-bleeding, or exploration.

## Activation

- User calls `/frame-cynefin` or `frame-cynefin:`
- Another SOP/frame needs help deciding whether the question is Complicated, Complex, Chaotic, or Disorder

## Domain cues

- Clear: known answer, repeatable action
- Complicated: analyzable, but not obvious
- Complex: learn by probing
- Chaotic: stabilize first
- Disorder: classify before acting

## Internal classification

Use these signals to classify the domain:

| Signal | Likely domain |
|---|---|
| The answer is already known and repeatable | Clear |
| A specialist could analyze it into a good answer | Complicated |
| You need to probe and learn from the result | Complex |
| Stop the harm first, analyze later | Chaotic |
| The question itself is not yet well formed | Disorder |

## Cardinality rules

Limit the number of hypotheses you keep active.

| Domain | Hypothesis count | Convergence |
|---|---|---|
| Clear | 1 | Converge immediately |
| Complicated | 2 to 3 | Converge after analysis |
| Complex | Multiple | Do not force convergence |
| Chaotic | 1 stabilizing action | Action before convergence |
| Disorder | 0 | Classify first |

## Landing formats

- Clear: one best next action with brief rationale
- Complicated: narrowed recommendation plus why the others were not chosen
- Complex: parallel hypotheses plus probe conditions
- Chaotic: one stabilizing action, then diagnose after stabilization
- Disorder: small questions that help classify the domain

## Boundary guidance

- Complicated and Complex are a normal boundary case
- If a question can only be answered by trying, treat it as Complex
- If a question should already have a best practice answer, treat it as Complicated
- Do not force false certainty just to produce an answer

## Adjacent frames

Use this classifier as a front-end only, then hand off explicitly. `Complex` points to `frame-experiments` when the next move is a bounded probe. `Complicated` points to `frame-research` or `frame-research-tactics` when comparison and hypothesis narrowing are enough. `Chaotic` points to `frame-distributed-incident-analysis` and then `frame-diag` for stabilization. `Clear` can proceed to `frame-plandev` or `frame-plantask` when the task is already understood. `Disorder` should fall back to `frame-first-principles`. Do not auto-connect the next frame from `frame-cynefin`; keep the choice explicit.

## Interaction with other frames

- Use `frame-first-principles` after `frame-cynefin` if the question can be decomposed safely
- Use `frame-experiments` when the right next step is to probe rather than to analyze
- Use `frame-inertia` if the answer looks inherited from convention or authority rather than reasoned

## Output structure

- Domain
- Reasoning
- Next step
- Residual uncertainty
