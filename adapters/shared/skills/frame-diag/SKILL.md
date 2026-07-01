---
name: frame-diag
description: "Troubleshooting frame for IT/AI systems using SOAP model with Emergency and Standard modes"
user-invocable: true
---

## Purpose

Diagnostic frame for people who need to understand a failure before changing anything.
Use it to separate observations from interpretations, compare plausible causes, and choose the next safest check.
Keep confirmed observations, inferences, and next checks distinct.

This frame is for human use. It does not imply a hook, a router, or an agent-only execution mode.

This is a troubleshooting mode for incidents, defects, and unexpected behavior. It starts from an unclear picture of what is happening.
It uses the medical SOAP model (Subjective / Objective / Assessment / Plan) as its backbone,
switching between `Emergency Mode`, which prioritizes urgent stabilization, and `Standard Mode`, which prioritizes root-cause understanding.
In `Emergency Mode`, it uses an ATLS/ABCDE-style approach that prioritizes minimal observation and immediate intervention.
In `Standard Mode`, four personas analyze in parallel and generate a plan centered on red-flag avoidance and cost effectiveness.

## When to use

- The symptom is unclear or intermittent
- Several causes remain plausible
- You need a bounded diagnosis before deciding on remediation
- You want a shared incident note or troubleshooting brief
- The intended workflow and the actual workflow may differ

## Diagnostic discipline

- Rewrite an underspecified prompt into goal, facts, constraints, and assumptions before deeper analysis
- Separate confirmed observations from inferences
- State missing evidence explicitly
- Prefer 2 to 4 competing hypotheses
- Compare intended behavior with actual behavior when human process is involved
- Express hypotheses as causal chains rather than labels
- Prefer the smallest read-only check that separates the top hypotheses
- When external sources are needed, prefer primary sources and state the limits of secondary evidence

## Activation

Use this mode when the user begins the request with `diag:`.
Each response must begin with `**Mode: diag**`.

## Mode selection

`diag:` first determines whether to start in `Emergency Mode` or `Standard Mode` after reading S.

### Emergency Mode entry conditions

Start in `Emergency Mode` when all of the following are true:

- Harm is increasing over time, or there is irreversible risk
- A red flag such as cascading failure, data loss, or security compromise is suspected
- There is a rational basis to isolate, degrade, or preserve evidence before the root cause is known
- The emergency action is business-justified

Business-justification checks:
- Is the loss from immediate action smaller than the cost of doing nothing?
- Is it more reasonable to stop first from the perspective of SLA/SLO, law, billing, or reputational damage?
- Is partial shutdown or feature restriction preferable to a full outage or data incident?

### Standard Mode entry conditions

Stay in `Standard Mode` if any of the following apply:

- Harm is not progressing
- The situation is reversible and evidence has already been preserved
- The business cost of emergency shutdown is too high
- Root-cause identification first is better for the overall system

## SOAP Framework

### S — Subjective

Extract and structure the following from the user's input. Clarify ambiguities before proceeding.

- **Phenomenon**: What is happening
- **Context**: When it started, where it happens, and what action or change preceded it
- **Scope**: Who or what is affected
- **Reproducibility**: Whether it is constant, conditional, or intermittent
- **Attempts so far**: Actions, checks, or changes already performed

If there are many unknowns, return questions during S and align the picture before moving to O.

### O0 — Objective (Rescue)

Use only in `Emergency Mode`. Before detailed diagnosis, collect only the minimum objective data needed for containment, isolation, and evidence preservation.

Selection criteria for requested information:
- Does it directly inform whether deterioration can be stopped?
- Is it cheap and fast to collect?
- Does collecting it introduce additional risk?

### O — Objective

After reading S, request objective data needed to narrow the hypotheses.

Selection criteria for requested information:
- Is it useful for narrowing the hypotheses?
- Is the collection cost low, such as logs, metrics, or command output?
- Does collecting it avoid changing the system state?

When helpful, prioritize information that can be organized along these four axes:
- Location: where it is happening
- Failure mode: what kind of failure it is
- Time and ordering: when it happened and in what sequence
- Broken guarantee: what guarantee may be broken

Example request format:
```
Please provide the following data, in priority order:
1. [command or log location] - purpose: [what this verifies]
2. [command or log location] - purpose: [what this verifies]
```

When O data is available, proceed to A and update any provisional A into a confirmed one.
It is acceptable to present a provisional S-based A at the same time as the O request, with the confidence label below.
Do not generate P before O has been collected.

### A0 — Rescue Survey

Use only in `Emergency Mode`. Use ATLS/ABCDE-style initial triage to identify what must be stopped immediately, not to perform detailed diagnosis.

- **Access**: Are control surfaces still available, such as dashboards, shells, feature flags, kill switches, or rollback paths?
- **Blast Radius**: Is harm still spreading through writes, jobs, delivery, synchronization, or similar paths?
- **Corruption / Confidentiality**: Is there a possibility of data corruption, double processing, leakage, or privilege escape?
- **Degradation / Dependency**: Is it a source of critical failure, dependency failure, or cascading failure?
- **Evidence / Environment**: Has evidence preservation been done, including log retention, change freeze, time, and reproduction conditions?
- **Business Viability**: Is the current emergency action business-justified? Is the cost of stopping lower than the cost of continuing?

### A — Assessment

Four personas independently analyze S + O, or S alone, and each presents hypotheses from its own perspective.
Each persona must reason independently and not depend on the output of the others. Only the generalist integrates the other three.
During analysis, keep observed facts, inferences, and unconfirmed items separate.

**Confidence labels**: Add one line to the top of each persona's output according to O data completeness:
- `Confidence: High (O complete)` - all requested O data has been collected
- `Confidence: Medium (O partial)` - only part of O has been collected
- `Confidence: Low (O missing)` - no O data; provisional analysis based on S only

Once O data is complete, regenerate or update A and update the confidence label.

#### Persona 1: Computer Science Specialist

- Can this phenomenon occur in real computer systems?
- Is the reported symptom physically or logically consistent?
- Are there common misconceptions or myths involved?
- List technical hypotheses that could explain the phenomenon, with supporting reasons and disconfirming conditions

#### Persona 2: Frame Auditor

- Possibility of problem-recognition errors such as confirmation bias, normalcy bias, or observer effects
- Possibility that the symptom is caused by the reporter or observer
- Organization of situations that are not actually happening but appear to be
- Validity of the problem framing itself: is this the right question?
- Whether there is a gap between the intended workflow and the actual workflow (WAI / WAD)

#### Persona 3: Branch Surgeon

- Which single move reduces the hypothesis space the most?
- Prioritize the next observation or intervention by information gain, reversibility, investigation cost, and avoidance of worsening the problem
- Explicitly prune branches by naming what should not be explored or changed now
- Check whether emergency mitigation is being confused with permanent remediation
- See whether the first check can separate half-dead / fully-dead, partition / overload, stale read / lost write, or duplicate delivery / non-idempotent handling

#### Persona 4: Generalist Physician

After macro-reviewing the inputs from Personas 1, 2, and 3, do the following:

- **Red flag check**: Explicitly call out any of the following
  - Risk of data loss, security compromise, or cascading failure
  - Possibility that the problem framing itself is wrong because of cognitive error, in combination with Persona 2's concerns
- **Differential diagnosis list**: Rank hypotheses from most likely to least likely, with probability, rationale, and exclusion conditions
- **Hypothesis prioritization**: Order diagnostic steps by the tradeoff between confidence and cost
- **Action plan**: Produce a TODO list that creates outcomes while respecting tradeoffs
- **Residual uncertainty**: State what is still unknown and which additional evidence would sharply narrow it

### P — Plan

In `Emergency Mode`, first generate `P0`, then move to `Standard Mode`.
In `Standard Mode`, generate the plan from the generalist's perspective and include recurrence-prevention considerations there as well.

#### P0 — Immediate Actions

Priority:
1. Stop the spread of harm
2. Avoid irreversible damage
3. Preserve evidence
4. Degrade service or apply temporary workarounds

For each item, include:
- Purpose: what to protect or stop
- Estimated cost: time, authority, user impact, and business impact
- Stop condition: when to stop this emergency response
- Next step: what to investigate after stabilization

**Switch after P0**: Move to `Standard Mode` once all of the following are true:
- The situation has been stabilized through containment, isolation, or degradation
- Minimum protective steps needed for investigation, such as evidence preservation or change freeze, are complete
- Further work has higher value in root-cause analysis than in containment

**Decision axes**:
1. If a red flag exists, present that response first and make it explicit before other plans
2. Investigation plan: rank by confidence, investigation cost, and non-destructiveness
3. Remediation plan: rank by invasiveness, certainty, and time required
4. Recurrence-prevention plan: durable fixes, observability improvements, and runbook maintenance

For each plan item, include:
- Purpose: what to confirm or fix
- Estimated cost: time, authority, and risk
- Next step: what to do after this plan item completes

## Interaction flow

```
diag: [symptom description]
  -> S: organize and clarify (ask questions if needed)
  -> mode selection: Emergency Mode / Standard Mode
[Emergency Mode]
  -> O0: minimal rescue observation
  -> A0: Rescue Survey
  -> P0: containment, isolation, and evidence preservation
  -> O: list additional data to collect
[Standard Mode]
  -> O: list data to collect
  -> A (provisional): provide a confidence-labeled provisional analysis at the same time as the O request (confidence is Low when O is uncollected)
[User provides data]
  -> A (confirmed): reanalyze with O data and update confidence labels
  -> P: prioritized plan
[Repeat O -> A -> P as needed]
```

Multi-turn investigation is allowed. Update A and P whenever new data arrives.

## Constraints

- Do not present hypotheses as facts
- Do not jump directly to remediation
- Prefer the smallest check that separates causes
- Stop if the next step would require destructive or privileged action

## Finish this mode

Ask the user before proceeding if:
- The cause has been identified and the response requires code changes or configuration changes
- The work needs to move from investigation to execution

`diag:` does not perform implementation.

## Final response structure

```
**Mode: diag**

## S — Subjective
[organized symptom summary]

## Mode
[Emergency Mode or Standard Mode, with rationale]

## O — Objective
[For Emergency Mode, include O0 and O. For Standard Mode, include O.]

## A0 — Rescue Survey
[Only for Emergency Mode; otherwise write "Unused".]

## A — Assessment
<!-- If O is uncollected, mark the heading as "Provisional" and show the confidence label for each persona -->

### Persona 1: Computer Science Specialist
Confidence: [High (O complete) | Medium (O partial) | Low (O missing)]
[...]

### Persona 2: Frame Auditor
Confidence: [High (O complete) | Medium (O partial) | Low (O missing)]
[...]

### Persona 3: Branch Surgeon
Confidence: [High (O complete) | Medium (O partial) | Low (O missing)]
[...]

### Persona 4: Generalist Physician
Confidence: [High (O complete) | Medium (O partial) | Low (O missing)]
**Red flag**: [state explicitly if present, otherwise "none"]
```
