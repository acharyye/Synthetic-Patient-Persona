---
type: Concept
title: What the uncovered circumstantial segments actually are
description: state_coverage missed its floor, and the verdict called it relabelling. Reading all 18 uncovered segments shows 1 is relabelling; ~9 are denominator false positives and ~8 are compound segments grounded on their mitigation half.
resource: ../../../tests/cassettes/narration_battery.json
tags: [v3, state-citation, metric, finding]
timestamp: 2026-08-25T00:00:00Z
---

# What the uncovered circumstantial segments actually are

**Read 2026-08-25**, offline, over the committed cassette — 30 takes, no model run. The
[v3 reading](v3-reading.md) shipped with one thing unexplained: `state_coverage` under its floor
means some circumstantial segments carry no `P-`/`B-`/`J-` id, and the adjudication branch named the
cause as *"the segments were relabelled rather than grounded"*. That phrase was never measured. This
is the measurement.

## The shape of the miss

Replaying the cassette gives `state_coverage` 0.5135 over **37** circumstantial segments, so **18**
carry no state id. Of those 18:

| | count | |
|---|---|---|
| cite graph facts only (`F-`), kind `factual` | **17** | grounded, on the other namespace |
| cite nothing, kind `feeling` | **1** | the v2 pathology, in full |
| had no state id available to cite | **0** | never "had none to offer" |

**Not one of the 18 is an uncited factual claim.** Citation validity is 1.0 and this is what that
means segment by segment.

## Reading the 17

Classification below is a **human read** of the segment texts, not a metric. Counts are approximate
at the boundary because some segments are compound.

**~9 are denominator false positives.** The claim is clinical, and the first person is grammar
rather than circumstance: *"For the metformin, I need to do fasting blood tests"* (`F067`, `F001`),
*"Ramipril can make me feel dizzy and give me a dry cough"* (`F126`, `F127`, …). There is no state
fact that would justify these, and the graph fact they cite is the right one. `is_circumstantial`
catches them on first person plus a factual marker, which its own docstring says is deliberate — it
*"errs toward INCLUDING, which grows the denominator and makes the bar harder rather than easier"*.
That choice is sound and it is also most of this miss.

**~8 are compound segments, grounded on the wrong half.** *"I work shifts, so weekday daytime
appointments are hard for me. Evening and weekend clinic slots or remote visits by video could
help"* cites `F042`, `F043` — the mitigations — and nothing for *I work shifts*, which is
`P-employment`. The circumstance and the mitigation share a segment, the model cited one of them,
and the scorer cannot split a sentence. This is a genuine state-citation miss, and it is a
**segmentation** problem as much as a citation one.

**1 is relabelling.** *"I think it would be tough, especially with my transport situation."* — kind
`feeling`, `fact_ids` empty, a transport circumstance asserted and uncited. Exactly the v2 pathology
the axis was built to detect. One instance in 37.

## What this changes, and what it does not

**The v0.4 verdict stands.** `state_coverage` missed its floor on both readings and the run takes
the same branch. Nothing here revises a pre-registered bound, and
[the shape file is not edited](pre-registration.md) — an expectation revised after seeing results is
not an expectation.

**The stated mechanism does not stand.** "Relabelled rather than grounded" describes 1 of 18
uncovered segments. The other 17 are cited and valid; they cite graph facts where the metric expects
state facts. A reader who takes the branch label at face value would go looking for a labelling
pathology that is not there.

**The metric needs a denominator that separates the two.** A first-person clinical claim and a
first-person circumstantial claim are different objects, and `is_circumstantial` cannot currently
tell them apart. That is a change to the instrument, so it belongs in the **next** pre-registration
rather than in this one — and it is now the first thing a v4 shape file has to decide.

## Reproducing it

Replay the cassette through `score()` and filter `is_circumstantial(seg.text)` for segments whose
`fact_ids` contain no `is_state_id`. No model, no network; the cassette is committed.

---
Related: [The v3 reading](v3-reading.md), [state-citation](state-citation.md), [pre-registration](pre-registration.md), [one generation, one sample](../decisions/one-generation-one-sample.md)
