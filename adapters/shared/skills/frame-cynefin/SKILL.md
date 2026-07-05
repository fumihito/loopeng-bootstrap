---
name: frame-cynefin
description: "Classify the domain before choosing a response. Use when clear, complicated, complex, chaotic, or disorder are all live possibilities. The point is to match next action to the shape of the problem."
user-invocable: true
---

## Purpose

Use this frame when the correct response depends on the domain. It helps decide whether to apply best practice, analysis, experimentation, stop-the-bleeding, or exploration.
It classifies first; it does not solve the problem.

## When to use

- The problem itself is not yet well formed
- You need a domain label before choosing another frame
- Several response styles seem plausible

## Workflow

1. Check the domain cues.
2. Limit the active hypothesis count.
3. Match the landing format to the domain.
4. Keep the next frame choice explicit.
5. State residual uncertainty if the problem remains mixed.

### Domain cues

- Clear: known answer, repeatable action
- Complicated: analyzable, but not obvious
- Complex: learn by probing
- Chaotic: stabilize first
- Disorder: classify before acting

### Cardinality rules

| Domain | Hypothesis count | Convergence |
|---|---|---|
| Clear | 1 | Converge immediately |
| Complicated | 2 to 3 | Converge after analysis |
| Complex | Multiple | Do not force convergence |
| Chaotic | 1 stabilizing action | Action before convergence |
| Disorder | 0 | Classify first |

### Landing formats

- Clear: one best next action with brief rationale
- Complicated: narrowed recommendation plus why the others were not chosen
- Complex: parallel hypotheses plus probe conditions
- Chaotic: one stabilizing action, then diagnose after stabilization
- Disorder: small questions that help classify the domain

### Boundary guidance

- Do not force false certainty just to produce an answer
- If a question can only be answered by trying, treat it as Complex
- If a question should already have a best practice answer, treat it as Complicated

## Output

- Domain
- Reasoning
- Next step
- Residual uncertainty

## Exit

Hand off explicitly after classification. Do not auto-connect the next frame from this frame.

## Adjacent frames

- Use `frame-experiments` when the next move is a bounded probe.
- Use `frame-research` or `frame-research-tactics` when comparison and hypothesis narrowing are enough.
- Use `frame-distributed-incident-analysis` and then `frame-diag` when stabilization is needed.
- Use `frame-plandev` or `frame-plantask` when the task is already understood.
- Use `frame-first-principles` when the problem is still in disorder.
- Use `frame-inertia` when the answer looks inherited from convention or authority rather than reasoned.
