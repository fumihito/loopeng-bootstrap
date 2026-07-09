---
name: frame-decision-making
description: "Structure a commitment decision: dry facts, means scored on will/can/must, and pre-committed decision points. Use when something must be decided or revisited under real constraints. The point is to decide with tripwires, not narratives."
user-invocable: true
---

## Purpose

Use this frame when a commitment must be made, or an existing commitment must
be revisited. It produces exactly three sections: an unnarrated statement of
the situation, an enumeration of means with modal scoring, and the observable
points at which the decision must be re-examined. It structures the decision;
the user makes it.

The first section is deliberately dry. Narrative is how bad situations get
laundered into acceptable ones before anyone decides anything; this frame
blocks that at the input stage, not the output stage.

This is not a planning frame. It does not turn a chosen commitment into
phases, dependencies, or a handoff package. It isolates the commitment question
before any delivery shape is chosen.

## When to use

- A choice must be committed to and resources are real and scarce
- An earlier commitment shows strain and needs re-examination
- Options exist but nobody has separated obligation, capability, and intent
- A decision keeps being deferred without a named next decision point

## When NOT to use

- The work already has a chosen commitment and needs phases, verification, and handoff -> `frame-plandev`
- The task is to make dependencies and ordering explicit -> `frame-plantask`
- The input is already a plan or note that needs compression -> `frame-smeac`
- The choice is a technical design space to narrow -> `frame-research-arch`
- The problem itself is not yet well formed -> `frame-first-principles` or `frame-cynefin`
- The decision needs a live probe before it can be made -> `frame-experiments`

## Workflow

### Section 1 - Situation (facts, unnarrated)

1. List facts only. A fact is observable or verifiable, and each entry names
   its source or observation channel. One fact per line.
2. Banned in this section: evaluative adjectives, opportunity reframing
   ("this is really a chance to..."), narrative causality ("because morale
   was low..."), euphemism, and any sentence whose subject is a feeling.
3. Mandatory sublists - each present even when empty, with `none found
   after search` stated explicitly:
   - **Inconvenient facts**: facts that weaken the currently favored option
     or the requester's stated preference. An explicit search is required at
     minimum.
   - **Resource facts**: time, money, people, attention actually remaining.
     Hoped-for resources are not facts.
   - **Irreversibility facts**: what is already spent, lost, or foreclosed.
     Sunk items are listed and then flagged decision-irrelevant unless they
     change future option availability.
   - **Unknowns**: what is not known, each with the rough cost of learning it.
4. Interpretations are quarantined: allowed only in a separate list marked
   `interpretation`, never interleaved with facts.

### Section 2 - Means (will / can / must)

1. Enumerate the means. `do nothing` and `defer with a date` are always
   first-class entries.
2. For each means: expected outcome (base case, with a probability estimate
   where honest), dominant failure mode, reversibility, and cost drawn only
   from Section 1 resource facts.
3. Score each means on three independent modalities:
   - **must** - is it forced by a constraint (legal, contractual, survival,
     hard deadline)? If yes, name the constraint.
   - **can** - is it feasible with Section 1 resource facts alone?
   - **will** - is there a named owner who commits to executing it?
4. Surface the modal conflicts explicitly:
   - must AND NOT can -> escalation item: the constraint or the resources
     must change; the decision cannot absorb this silently.
   - must AND NOT will -> ownership gap: name it; an unowned obligation is a
     drift generator.
   - will AND can AND NOT must -> discretionary: test it against the scarcest
     resource fact before keeping it on the list.
   - will AND NOT can -> a wish. Park it outside the decision.

### Section 3 - Next decision points

1. For each means still alive after Section 2, define decision points:
   - **event tripwires**: observable + threshold + pre-committed response
     set (continue / adjust / abort). The observable must be something
     Section 1 shows is actually measurable.
   - **calendar reviews**: listed separately; a calendar review is not a
     substitute for a tripwire.
2. Identify the **point of no return**: the last decision point before the
   leading means becomes irreversible. State it as a date or an event.
3. A means for which no tripwire can be defined is flagged
   `un-adjustable in practice` - that is itself decision-relevant.
4. Pre-commit the responses now, while unemotional; do not leave "we will
   decide when we see it" as a plan.

## Output

- Section 1: facts with sources; the four mandatory sublists; quarantined
  interpretations
- Section 2: means table with outcome, failure mode, reversibility, cost,
  will/can/must, and the modal-conflict callouts
- Section 3: tripwires with pre-committed responses, calendar reviews, the
  point of no return, and any un-adjustable flags

## Exit

The frame prepares the decision; the user owns it. If a recommendation is
given, it must cite Section 1 facts, carry its strongest counter-case, and
name the tripwire that would prove it wrong. A deferral is a valid exit only
with a named next decision point - deferral without one is drift, and the
frame says so. Do not restate the situation more optimistically at exit than
Section 1 stated it at entry.

## Adjacent frames

- Use `frame-plandev` when the commitment has already been made and the work needs phases, verification, and handoff.
- Use `frame-plantask` when the issue is dependency order rather than the commitment itself.
- Use `frame-smeac` when the material already exists and only needs compression into a brief.
- Use `frame-research-arch` when the task is to narrow architecture choices rather than commit.
- Use `frame-experiments` when the next move is a bounded live probe before deciding.
- Use `frame-cynefin` when the domain still needs pre-classification before any decision frame fits.
- Use `frame-first-principles` when the problem is still too fuzzy to define the decision cleanly.
