---
name: frame-smeac
description: "Check whether an order, plan, or handoff note is organized as a complete Five Paragraph Order (SMEAC). Use when an AI agent must audit Situation, Mission, Execution, Administration and Logistics, and Command and Signal for coverage, separation, coherence, and actionability."
user-invocable: true
---

## Purpose

Use this frame to audit an existing order or plan against the Five Paragraph
Order. Determine whether each paragraph is present, belongs in the right
paragraph, and is usable by the person who must act on it. This is a
structural and operational check, not a general summary or a request to make
the prose shorter.

Treat the source as evidence. Do not silently supply facts, invent assignments,
or mark a paragraph complete because it merely contains a related keyword.

## When to use

- An existing order, plan, or handoff note must be checked against SMEAC.
- The question is whether all five paragraphs are organized and usable.
- Missing, misplaced, contradictory, or non-actionable content must be surfaced.

## Five Paragraph Order checklist

Check all five paragraphs separately. Use these names even when the source uses
different headings.

1. **Situation** — Relevant context and conditions: opposing or external
   factors, friendly/supporting actors, stakeholders, environment, constraints,
   assumptions, and known uncertainty. Separate facts from assumptions and
   identify information that can change the plan.
2. **Mission** — A concise statement of who will do what, when, where, and why.
   The task, purpose, responsible actor, scope, timing, and desired outcome
   must be identifiable without reconstructing them from later paragraphs.
3. **Execution** — How the mission will be accomplished: intent, concept of
   operations, tasks by actor or element, sequence and timeline, coordinating
   instructions, control measures, decision points, and contingencies. Tasks
   need an owner and a usable completion condition where the source permits one.
4. **Administration and Logistics** (or **Sustainment**) — Resources and
   support required to execute: personnel, supplies, equipment, transport,
   maintenance, medical or safety support, services, resupply, and foreseeable
   failures or shortages. State who provides critical support and when it is
   available.
5. **Command and Signal** — Who is in charge and how coordination occurs:
   command relationships, succession or escalation, authorities, locations or
   channels, communication methods, reporting cadence, required reports,
   contact paths, and fallback/backup methods (for example, a PACE plan when
   relevant).

## Workflow

1. Define the review object, intended audience, mission, time horizon, and
   source boundary. If any are absent, record that limitation before judging
   completeness.
2. Extract evidence and place each statement in one primary paragraph. Flag
   cross-cutting statements and statements under the wrong heading; do not
   count duplicated text as additional coverage.
3. For each paragraph assess:
   - **Coverage:** Is the required information present?
   - **Separation:** Is it in the right paragraph and distinguishable from
     assumptions, rationale, or another paragraph's content?
   - **Coherence:** Does it agree with the mission and the other paragraphs?
   - **Actionability:** Can the intended actor use it to decide or act?
4. Mark each paragraph `complete`, `partial`, `missing`, `contradictory`, or
   `not applicable`. Use `not applicable` only with a reason; a missing
   fallback, owner, or timing detail is not automatically N/A.
5. Run a cross-paragraph check: every execution task should support the
   mission; each critical task should have required support; command authority
   should match task ownership; timing, locations, resources, and reporting
   instructions should not conflict.
6. Report the smallest corrective action for each defect. Reorganize or rewrite
   only when requested or when the task explicitly asks for a corrected order.
   Label every inserted item as a proposal or assumption, never as source fact.

## Output

Return a compact audit with this structure:

1. **Review scope and limitations** — source, audience, mission/time boundary,
   and missing context.
2. **Five-paragraph assessment** — one row or subsection for each paragraph,
   including status, evidence/location, coverage, and specific gaps or
   misplacements. Do not merge the five rows.
3. **Cross-paragraph findings** — contradictions, broken dependencies, missing
   ownership/support/timing, and duplicated or misplaced information.
4. **Verdict** — whether the order is organized as a usable Five Paragraph
   Order, with the reason and residual uncertainty. A complete verdict requires
   all applicable paragraphs to be coherent and actionable.
5. **Correction queue** — prioritized, concrete fixes. If a corrected order is
   requested, provide it after the audit and label non-source additions.

## Exit

Finish when all five paragraphs have an explicit status, evidence, and gap
assessment, and the cross-paragraph check is complete. If a new plan must be
designed, hand off to planning after reporting the audit.

## Adjacent frames

Do not confuse this audit with validating whether the mission is wise, lawful,
or factually true; flag those as separate review needs. Do not turn an
incomplete order into a confident plan by filling gaps.

- Use `frame-first-principles` when the review object or objective is too
  ambiguous to define.
- Use `frame-critical-review` when the main question is claim or evidence
  validity rather than order organization.
- Use `frame-plandev` or `frame-plantask` when a new plan or dependency graph
  must be designed after the audit.
- Use `frame-smeac` again after correction to verify coverage and consistency.

## Operational contract

This is a checking contract. Always inspect all five paragraphs explicitly,
show evidence for each status, and preserve uncertainty. A short summary may
appear only after the paragraph-by-paragraph audit. Never claim that the source
is a complete SMEAC merely because it is concise, has five headings, or uses
military terminology.
