---
type: Concept
title: is_circumstantial v2 — an instrument correction, scored on its own
description: The is_circumstantial lineage v1 → v2 → v2.1 → v2.2. v2.2 is the scoring instrument, adopted on held-out blind labels on 2026-08-25, shown expired on v4 text the same day, and frozen since the 2026-11 review.
resource: ../../../src/spp/narration/circumstantial.py
tags: [v3, state-citation, metric, instrument, finding]
timestamp: 2026-11-19T00:00:00Z
---

# `is_circumstantial` v2 — an instrument correction, scored on its own

> **Current status (2026-11-19).** `evaluation.py` scores with **v2.2**. The sections below are the
> record of v2 as it was written, in order, and two of them describe states that no longer hold:
> *"Validation is blind, and is not done"* was true before the first labels arrived, and *"v2 is
> adopted"* was true for a few hours.
>
> | version | fate |
> |---|---|
> | v1 | shipped through v0.4; κ −0.0484 on the first blind sheet. Kept in the module, unused by scoring. |
> | v2 | won the first sheet (κ 0.3113), then scored κ 0.0000 held out. Never wired in. |
> | v2.1 | won its held-out sheet (κ 0.3182); **failed adoption on the canary** — it zeroed the state-lever fixture. |
> | v2.2 | adopted on a sheet held out from every instrument (0.6939 / κ 0.3336). Beaten by v2.1 on v4 text (0.5882 vs 0.6765). |
>
> Why v2.2's adoption expired: [estimator validity](../decisions/estimator-validity.md). No further
> revision is planned until a calibrated prior pack exists.

**Built 2026-08-25**, after [reading the uncovered segments](state-coverage-denominator.md) showed
that about half the v0.4 miss was the denominator rather than the model.

## The definition, from principle

> A segment is circumstantial iff it asserts something **only this persona's own state could
> support**. Operationally: first person, **and** carrying at least one content term that appears in
> this persona's `P-`/`B-`/`J-` fact texts and in **none** of the graph facts the case was offered.

The subtraction is the whole rule. A term the graph can support is ambiguous evidence, so it is not
evidence — `transport` in both a persona's `B-transport_fragile` and a retrieved mitigation fact
leaves the vocabulary. First-person grammar alone does not qualify either, which is the v1 rule this
replaces.

It was derived from `PROFILE_FIELDS` and the offered-fact contract, **not** from the segment texts it
will be scored on. That ordering is the point: a classifier tuned until it agrees with a reading of
the run it will score is fitted, not defined.

## The number, and why it is not a result

| instrument | `state_coverage` | numerator / denominator |
|---|---|---|
| v1 (shipped, pre-registered) | **0.5135** | 19 / 37 |
| v2 (under review) | **0.6000** | 18 / 30 |

Both from the same committed cassette, zero model calls. **v2 lands exactly on the pre-registered
floor of 0.6.** That is a coincidence and it is reported as one — a metric that arrives precisely at
its own bar after being rewritten is the single most suspicious shape a number can have, and it is
the reason this is labelled an *instrument correction under review* rather than a pass.

**v0.4 is unchanged.** It was adjudicated under v1, which is what the shape file registered, and
nothing here revises it.

## What v2 does well and what it does not

**Its drops are clean.** The 15 segments v1 counted and v2 does not are the clinical-claim class:
metformin fasting tests, salbutamol tremor, inhaled-corticosteroid side effects, ramipril
monitoring. Each cites the graph fact that supports it, and no state fact could. Exactly what the
definition says should leave.

**It keeps the real miss.** *"I think it would be tough, especially with my transport situation"* —
kind `feeling`, no ids — is circumstantial under both.

**Its additions are the open question.** v2 counts 8 segments v1 did not, mostly `feeling` segments
about symptoms and goals: *"I feel pretty tired most days"*, *"I really want to stay well enough to
look after my family"*. Some are incidental token matches rather than claims about the state fact
that supplied the term. And **symptoms are not in `PROFILE_FIELDS`**, so a symptom claim has no `P-`
id available — counting it enlarges the denominator with segments that cannot be covered. That is a
coverage finding to log, not a rule to bend.

## Validation is blind, and is not done

`state_coverage` under v2 is **not adopted**. `tests/test_circumstantial_v2.py::TestNotWiredIn`
asserts `evaluation.py` does not import it, so the metric cannot change by accident.

The protocol is the must/may authoring protocol: labels authored against the state dumps, then the
classifier scored against the labels — never the reverse. A blind rating sheet for all 53 segments
exists (hash-shuffled, texts only, no citations, kinds or classifier verdicts). **The author of the
classifier has read the segments and is therefore a contaminated rater** — an independent pass is
required, not optional.

Only once labels exist does the sequence continue: adopt v2 on the strength of the labels, rescore
v3 under it, publish both numbers side by side as an instrument correction, and only then
pre-register v4 against the corrected baseline.

## Validation result — blind labels, 2026-08-25

53 segments rated from text alone by an independent rater who saw no persona, citation, kind or
classifier verdict. Tallies: 38 `y!` (circumstantial and coverable), 6 `y?` (circumstantial, nothing
in the schema could cover it), 8 `n`, 1 `?`. Segment 18 abstained and is excluded from scoring —
52 scored. Five decision rules were committed by the rater before scoring, so disagreements are
adjudicable against a stated boundary rather than argued per segment.

| instrument | agreement | Cohen's κ | TP | FN | FP | TN |
|---|---|---|---|---|---|---|
| v1 (shipped) | 0.6154 | **−0.0484** | 30 | 14 | 6 | 2 |
| v2 (under review) | **0.6923** | **0.3113** | 29 | 15 | 1 | 7 |

**v2 is adopted: it beats v1 on both, which is the pre-registered comparative criterion.** v1's κ is
*below chance* — on this labelled set its agreement is what a coin achieves given the class balance,
which is the finding kappa was pre-registered to expose. Restricted to coverable segments the two
instruments score **identical** raw agreement (0.6957) and κ 0.0359 against 0.3347: the clearest
possible demonstration that raw agreement alone would have decided this wrong.

v2 buys its win almost entirely in precision — 6 false positives down to 1 — at no cost in misses.

## The named limitations

The clustering clause fires, and cleanly: **all 15 of v2's misses fall into three classes, none
unclustered.**

| class | n | segments | why |
|---|---|---|---|
| **own regimen** | 8 | 01, 03, 11, 13, 21, 42, 44, 51 | *"I take salbutamol PRN and tiotropium"* asserts the persona's own medication state (`P-medications`). The drug name appears in both the state fact and the offered graph facts, so the subtraction removes it and the assertion becomes invisible. |
| **shared circumstance term** | 5 | 04, 10, 19, 34, 46 | *"my work schedule"*, *"public transport"* — the mitigation facts carry the same terms, so the subtraction removes exactly the words that carry the circumstance. |
| **uncoverable** | 2 | 33, 43 | the `y?` population; expected, and the reason the metric splits. |

Both real classes are **one mechanism**: the subtraction cannot distinguish *asserting possession or
experience of a thing* from *asserting a clinical property of that thing*, and it discards the shared
term in both directions. Named here, **not patched** — editing the classifier until it stops missing
these segments would be fitting it to the labels it was validated against, and the next definition
needs its own blind rating, not this one.

## The number the correction actually produces

| denominator | `state_coverage` | |
|---|---|---|
| v1 instrument (shipped, pre-registered) | 0.5135 | 19/37 |
| v2 instrument | 0.6000 | 18/30 |
| **human labels, coverable only** | **0.5263** | **20/38** |

`schema_gap_rate` = 6/44 = **0.1364**.

**The instrument correction does not rescue the v0.4 miss.** Against the label-validated denominator
`state_coverage` reads 0.5263 and still misses the 0.6 floor — closer to v1's number than to v2's.
v2's 0.6000 was an artifact of its own over-aggressive subtraction: a denominator of 30 where the
truth is 38. So **v2 over-reports coverage by about seven points**, and that bias has a known
direction, which is the most useful thing a named limitation can have.

The suspicious coincidence resolves as a coincidence. The miss survives the fix.

## What still needs deciding

The floor. 0.6 was registered against v1 semantics; it does not transfer, and 0.6 under v2 semantics
is not 0.6 under the gold denominator given the +7pt bias. Setting the bar is a judgement call and
belongs in its own commit before any v4 run, per
[the gate](../../../tests/eval/instrument_v2_gate.json).

The own-regimen semantics are a second decision, to be made **once, in the gate record**: does
"I take X, and it can cause Y" belong in the coverage denominator? The labels say yes. If the answer
changes the classifier, that classifier needs fresh blind labels.

---
Related: [what the uncovered segments actually are](state-coverage-denominator.md), [The v3 reading](v3-reading.md), [pre-registration](pre-registration.md), [a bar that cannot fail](../decisions/gate-must-be-able-to-fail.md)
