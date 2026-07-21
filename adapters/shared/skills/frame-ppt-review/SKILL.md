---
name: frame-ppt-review
description: "Review PowerPoint, Marp, Markdown, or plain-text presentation drafts for missing decision foundations. Use when a deck must clarify the decision, evidence, economics, estimates, and the minimum purpose-situation-means-result spine before design or rewriting."
user-invocable: true
---

## Purpose

Use this frame to decide whether a presentation draft contains the minimum
substance needed for a fact-based decision. Identify what is absent, ambiguous,
unsupported, or buried; then specify the smallest repair that would make the
decision easier to take.

Review the decision foundation, not visual polish. Do not reward a professional
layout for missing substance, and do not penalize a rough text draft when its
decision logic is complete.

## When to use

- Review a `.pptx`, Marp deck, Markdown outline, or plain-text presentation draft
- Find missing content before slide design, editing, or executive review
- Test whether a proposal supports a concrete decision with auditable numbers
- Separate decision-critical material from implementation detail and appendix material

## Input handling

Preserve a locator for every finding: slide number and title for PowerPoint or
Marp, and heading, paragraph, or line range for Markdown and plain text.

- For PowerPoint, inspect slide text, tables, charts, source labels, and speaker
  notes. Render slides when extraction loses chart meaning, spatial grouping, or
  other visual semantics.
- For Marp, inspect frontmatter, slide separators, headings, body content, notes,
  and source annotations.
- For Markdown or plain text, treat headings and coherent blocks as provisional
  slides. Do not require an existing slide boundary.
- If part of the input is unreadable, state the coverage limit. Do not issue a
  `ready` verdict from partial evidence.

Treat absence from the supplied artifact as `not stated`, not proof that the
underlying work was never done. Treat a claim without inspectable support as
`asserted`, not as fact.

## Workflow

### 1. Reconstruct the decision contract

Extract the following without improving or completing the author's argument:

- **Who:** Name the person or role authorized to decide. Keep the decision-maker,
  proposer, executor, beneficiary, and audience distinct.
- **What:** State the exact commitment requested: approve, reject, select,
  prioritize, fund, stop, or defer what. Record the options and timing when given.
- **Why:** State the decision criteria and why those criteria are valid for this
  decision. Do not substitute a generic problem statement or aspiration.
- **Evidence:** Link each material factual, causal, or predictive premise to its
  source, observation, or calculation.

Mark each field as `supported`, `asserted`, `ambiguous`, `not stated`, or
`contradicted`. Cite the artifact locator that justifies the mark. A title such
as “Proposal” or a closing “Please approve” does not by itself define What.
When the authorized decision-making person or body is named, mark Who as
`supported`; do not downgrade it merely because proposer, executor, beneficiary,
or audience roles are absent. Report those roles separately only when their
absence changes the decision or its feasibility.

### 2. Reconstruct the minimum decision spine

Reduce the draft to four elements:

1. **Purpose:** the outcome or decision the presentation exists to enable
2. **Situation:** relevant current facts, baseline, constraints, and uncertainty
3. **Means:** the proposed action and material alternatives, including doing
   nothing when it is a credible baseline
4. **Expected result:** the observable change expected from each live means,
   with timeframe and uncertainty

Flag a broken link when a means does not address the situation, a result does
not follow from the means, or the purpose cannot be judged from the result.
Treat detail beyond this spine as useful only when it changes the decision.

### 3. Audit cost and return on comparable terms

Find the decision-relevant costs and returns. Require both sides unless the
artifact explains why one side is genuinely inapplicable.

For each value, capture:

- amount and unit
- baseline and comparison case
- time horizon and timing of realization
- gross versus net treatment
- included and excluded items
- uncertainty, range, or scenario
- source or calculation path

Use the outcome unit appropriate to the domain. In a business context, connect
revenue and cost changes to gross profit or another explicitly justified value
measure. In a health context, connect intervention burden and cost to healthspan,
quality of life, functional ability, or another explicitly justified outcome.
Do not force unlike outcomes into money when the decision legitimately uses
multiple criteria; make the tradeoff visible instead.

Do not accept revenue alone as return, expenditure alone as cost, or percentages
without denominators and baselines. Flag mismatched units or horizons that make
options incomparable.

### 4. Audit estimates for third-party reproducibility

For every material effort, duration, price, cost, and return estimate, ask
whether a third party could reproduce or challenge it. Require:

- numeric value or honest range with unit
- quantity and rate decomposition where applicable
- assumptions and scope boundaries
- source, observed base rate, quote, benchmark, or calculation
- as-of date for time-sensitive inputs
- uncertainty or sensitivity for decision-changing assumptions

Classify each estimate as:

- **reproducible:** the artifact supplies enough basis to recalculate it
- **traceable:** a source is named but the calculation is incomplete
- **unsupported:** a number is present without a usable basis
- **missing:** the decision needs a number but none is supplied

Never invent precision. Recommend a range, a probe, or a quote when evidence
cannot yet support a point estimate.

### 5. Test evidence fitness

Match evidence strength to claim importance and type. Prefer direct observations,
primary sources, official records, signed quotes, measured base rates, and shown
calculations. Check whether the evidence is relevant, current enough, and scoped
to the population or setting in the claim.

Separate three questions:

1. Is evidence cited or shown?
2. Does that evidence support the claim made?
3. Has the evidence itself been independently verified in this review?

Do not imply question 3 is complete unless the sources were actually inspected.
Prioritize verification of claims that could reverse the decision. When source
access is unavailable, name the verification gap and the exact evidence needed.

### 6. Remove decision-path noise

For every section or slide, ask: would removing this change the decision,
decision criteria, risk assessment, or confidence in the result?

- Keep the visible main path to purpose, situation, means, and expected result,
  preceded or followed by the explicit Who / What / Why decision contract.
  Embed decisive evidence, economics, assumptions, and risks inside the relevant
  four elements instead of expanding them into generic standalone sections.
- Move implementation mechanics, background history, exhaustive research,
  detailed calculations, and reference material to an appendix when they are
  useful for challenge or follow-through but not needed for the first decision.
- Flag duplication and detail that delays the decision without changing it.
- Preserve appendix traceability: point from a main-path claim to its support.

Do not prescribe a slide count. Compression is successful only if the decision
contract and its support remain intact. Do not add a risk, alternatives, or
background section by template habit; include only what could change this
decision, its criteria, or confidence in the expected result.

### 7. Prioritize the minimum repair

Assign each gap one severity:

- **Blocker:** the requested decision, authorized decision-maker, decisive
  criterion, comparison baseline, cost/return, or expected result cannot be
  understood well enough to decide
- **Major:** a decision-changing claim or estimate is unsupported, inconsistent,
  or not comparable
- **Minor:** the foundation exists, but placement, duplication, labeling, or
  appendix separation makes it harder to inspect

For each gap, propose the smallest addition, deletion, move, or verification
that closes it. Phrase repairs as content requirements, not invented copy. Name
the owner or source needed when the artifact cannot supply the answer.

## Readiness rule

Issue exactly one verdict:

- **Ready:** no Blocker or Major gaps remain; all decisive facts and estimates
  are supported or explicitly bounded; the main path is decision-minimal
- **Conditionally ready:** no Blocker remains, but named Major gaps can be closed
  by explicit conditions before commitment or execution
- **Not ready:** one or more Blockers remain, evidence coverage is materially
  unreadable, or the economics cannot be compared

Do not calculate a composite score. A high score can hide a veto condition.
Base the verdict on the most consequential unresolved gap.

## Output

Present:

1. **Verdict and decision at risk** — readiness, the decision as currently
   understood, and the highest-severity reason
2. **Decision contract** — Who / What / Why / Evidence with status and locators
3. **Decision spine** — Purpose / Situation / Means / Expected result, including
   broken or missing links
4. **Economics and estimate audit** — cost, return, horizon, assumptions,
   reproducibility, and comparability
5. **Prioritized gaps** — severity, missing element, decision impact, artifact
   locator, and minimum repair
6. **Main path versus appendix** — what to keep, move, condense, or remove
7. **Residual uncertainty** — unverified sources and the observation that would
   settle each decision-changing uncertainty

Use `not found in supplied artifact` when a search finds no evidence. Quote or
paraphrase enough nearby content to make each finding auditable. Distinguish
artifact evidence from reviewer inference.

## Exit

End when every required field has a status, every Blocker and Major gap has a
minimum repair, and the verdict follows from the evidence shown. Do not rewrite
the deck, fabricate missing numbers, or silently choose the decision. If the
user asks for revision, treat that as a separate editing step after this review.

## Adjacent frames

- Use `frame-critical-review` when the main task is independently testing a
  finished argument or its sources rather than locating presentation-foundation gaps.
- Use `frame-decision-making` when the evidence is available and the user needs
  to structure or revisit the commitment itself.
- Use `frame-smeac` when the substance is already complete and only needs
  compression into a handoffable brief.
- Use `frame-proofread-ja` when the remaining issue is Japanese surface quality.
- Use `frame-plandev` after a commitment when the work needs delivery phases,
  verification, and handoff.

## Operational contract

Review only what the supplied artifact and inspected sources establish. Keep
Who, What, Why, Evidence, Purpose, Situation, Means, Expected result, Cost, and
Return distinct even when the draft blends them. Require material numbers to
be reproducible or explicitly bounded, and preserve unit, baseline, timeframe,
assumptions, and source. Return a veto-based readiness verdict and prioritized
minimum repairs; do not use a score, rewrite automatically, or infer missing
facts from presentation polish.
