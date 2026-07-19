---
name: frame-research
description: Compare external sources and grade each claim on an evidence hierarchy. Use when published evidence, documents, or citations are the main input and claims must be weighted by evidence strength, not source count.
user-invocable: true
---

## Purpose

Use this frame when the task is to compare, verify, and synthesize information from external sources. It is for deep research only: public information, official documents, papers, standards, articles, vendor docs, and published examples.

Every claim carried forward must be graded on the evidence hierarchy below. The output is not "what sources say" but "what the evidence supports, at what strength, and what would change it."

Keep codebase analysis, implementation planning, and local repository change work out of scope.

## When to use

- You need source-backed comparison, not a single ungrounded answer
- Multiple positions, frameworks, or practices need to be weighed
- The question needs evidence, not just reasoning
- Claims must be weighted by evidence strength, not counted by how many sources repeat them

## Evidence hierarchy

Assign each source an initial level. This is an EBM-style pyramid adapted for technical and general research domains: study-design categories are replaced by source-type categories.

| Level | Category | Typical sources |
|-------|----------|-----------------|
| E1 | Systematic synthesis | Systematic reviews, meta-analyses; formally balloted standards (ISO, IETF Standards Track, final NIST publications); syntheses whose method for collecting and weighing sources is stated |
| E2 | Peer-reviewed or normative primary | Peer-reviewed papers; the authoritative party's normative documentation (specification, reference docs) for questions about that party's own artifact |
| E3 | Non-reviewed primary | Preprints; first-party engineering blogs and postmortems; official changelogs, source repositories; talks by the implementers |
| E4 | Secondary analysis | Reputable journalism; third-party benchmarks, surveys, and textbooks without a stated systematic method |
| E5 | Opinion and anecdote | Personal blogs, forum posts, single testimonials, marketing material |

## Modifiers

Adjust the initial level by at most one step per factor, and state which modifier was applied:

Downgrade when:

- Conflict of interest: the source benefits from the claim being believed
- Staleness: the source predates changes in a fast-moving topic
- Indirectness: the evidence answers an adjacent question, not the one asked
- Unresolved contradiction with sources at the same or higher level

Upgrade when:

- Independent convergence: two or more unaffiliated sources at the same level agree
- Direct verifiability: the claim is backed by an inspectable artifact (code, data, reproducible steps) that was actually checked

## Grading rules

- A claim inherits the level of the weakest source it necessarily depends on.
- Level orders confidence within a question; relevance is decided first. An E5 firsthand bug report can outweigh an E2 specification for "does implementation X actually do Y" — the spec answers "what X should do."
- Grade after reading the source, never from the domain name or venue alone.
- Never fabricate a level to fill a gap. If no source above E4 exists for a key claim, that absence is itself a finding.

## Workflow

1. Define the research question and topic boundary.
2. Search broadly enough to avoid a narrow local maximum.
3. Grade each source: initial level, applied modifiers, resulting level.
4. Compare claims and positions, weighted by evidence level — do not let ten E5 sources outvote one E2 source.
5. Identify the strongest competing interpretations and the evidence differential between them.
6. Extract the practical implications or next actions.
7. Note what remains unresolved, flagging any conclusion that rests only on E4/E5 evidence.

## Grading discipline

- Keep sources, findings, and interpretations distinct
- Call out contradictions instead of smoothing them over; record the levels on each side
- Surface open questions instead of forcing closure
- For each unresolved contradiction, name the evidence that would settle it and at what level it would need to arrive

## When to invoke subframes

- Use `frame-research-tactics` when the research needs hypotheses and verification/falsification actions
- Use `frame-research-arch` when the research needs architecture options and tradeoffs
- Use `frame-first-principles` when the question needs decomposition before research can proceed
- Use `frame-cynefin` when the question may not yet be classifiable

## Output

- Research question
- Source set, each entry with: initial level, modifiers applied, resulting level
- Findings, each tagged with the evidence level of its supporting basis
- Evidence profile: for each key claim, the highest level supporting it and the highest level contradicting it
- Competing interpretations, with the evidence differential between them
- Open questions, including claims supported only at E4/E5
- Practical implications
- Next step, including what higher-level evidence would upgrade or settle the weakest key claim

## Exit

End when the source-backed comparison is decided at a sufficient evidence level to hand off, or state the unresolved contradictions, the level of evidence on each side, and the next source — and level — to seek.
If this session produced a deliverable goal or verification conditions, you can hand it to the autonomous loop (when installed) by stating the request in a plain, prefix-less message.

## Adjacent frames

- Use `frame-research-tactics` when the source comparison has to become hypotheses, verification, and falsification actions.
- Use `frame-research-arch` when the question is about architecture options and their tradeoffs rather than source comparison.
- Use `frame-experiments` when the answer requires a real probe with a bounded blast radius.
- Use `frame-first-principles` when the problem is still too underspecified to compare sources cleanly.
