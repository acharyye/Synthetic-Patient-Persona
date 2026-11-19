---
type: Concept
title: The v3 reading — recovery without state citation
description: The v0.4 battery recovered burden and mitigation with the controls flat, but state_coverage stayed under its floor. The verdict, and why the branch's stated cause does not match this run.
resource: ../../../evidence/v0.4/20260823T170152+0000/adjudication.json
tags: [v3, state-citation, evidence, finding]
timestamp: 2026-08-24T00:00:00Z
---

# The v3 reading — recovery without state citation

**Recorded 2026-08-23** against `qwen2.5:7b-instruct@845dbda0ea48`, prompt v3, 30/30 takes accepted,
0 quarantined. Bundle: `evidence/v0.4/20260823T170152+0000/`. Adjudicated 2026-08-24 by
`scripts/adjudicate_bundle.py`, which reads the arms out of
[the pre-registered shape](pre-registration.md) and transcribes no threshold.

## The verdict

**RECOVERY WITHOUT STATE CITATION.** Twelve of thirteen arms passed; `state_coverage` missed.

| arm | observed | bound | |
|---|---|---|---|
| `recovery.burden` | 0.700 | 0.6–0.95 | PASS |
| `recovery.mitigation` | 0.933 | 0.8–1.0 | PASS |
| `control.ae` / `.tx` / `.proc` | 1.0 / 1.0 / 1.0 | within 0.1 of v2 | PASS |
| **`state_coverage`** | **0.564** | **floor 0.6** | **MISS** |
| `feeling_floor` | 0.167 | floor 0.1 | PASS |
| `f_recall_holds_independently` | 0.531 | floor 0.5 | PASS |
| `holds_from_v2` (5 metrics) | — | — | PASS |

The v2 collapse did recover: burden 0.400 → 0.700, mitigation 0.443 → 0.933, and the graph-knowledge
controls did not move with them. That is the hypothesis in
[state-citation](state-citation.md) surviving its own controls.

## What the branch says, and what this run actually shows

The registered tree attaches one cause to this branch: *the segments were relabelled rather than
grounded.* **That cause is not what happened here**, and the difference matters more than the verdict.

Relabelling would look like circumstantial claims marked `feeling` and carrying no ids. Of the 18
uncovered circumstantial segments in the committed cassette, **17 are marked `factual` and carry
graph citations**; exactly one is an uncited `feeling`. The model is not dodging the contract.

The actual shape is a **one-family-per-segment citation habit**. Where a segment fuses a personal
circumstance with a graph fact, the graph fact takes the citation slot and the `P-` id is dropped:

> "I take anastrozole and tamoxifen, so I need to go for regular check-ups…" — cites `F158, F164, F004`,
> not `P-medications.anastrozole`.

> "I work shifts, so weekday daytime appointments are hard for me." — cites `F042, F043`,
> not `P-constraints.works-shifts-so-weekday-daytime`.

The canary corroborates this from the other side: under `strip_state_ids`, **`f_recall` *rises*** from
0.531 to 0.694. Removing one id family gives the other more room. The two families are competing for
citation slots, not for the model's willingness to cite.

So the reading is: the ids exist, the model uses them (`state_citation_share` 0.336), and the miss is
a budgeting behaviour rather than an evasion. The next prompt iteration is about a fused segment
citing **both** families — but per [pre-registration](pre-registration.md) that is a separate change,
never made in the same breath as reporting a result against the file it would edit.

## Caveats that travel with these numbers

- **Recall is not comparable to v0.1/v0.3.** Those graded flat retrieval-derived id sets; v3 grades
  authored must/may groups with alternation. `f_recall` is the graph-recall reading for v3.
- **State ids are ~64% of the enum by construction**, so a rise in state citation is partly volume.
- **57% of takes are a single segment.** No metric catches degeneracy; the five sampled takes were
  read and are not degenerate, but that is a sample.
- **`state_coverage` is 0.564 or 0.514 depending on which sample you read** — see
  [one generation, one sample](../decisions/one-generation-one-sample.md). Both miss the floor, so
  the branch is the same either way; the headline figure is not precise to three digits.
- **`context_overflow_rate` was not measured in this run.** It read 0.0 and PASSED because `grade()`
  supplied a literal. Treat it as unevaluated for v0.4.

## The stated mechanism was later measured, and mostly did not hold

The branch label says the segments were *relabelled rather than grounded*. Reading all 18 uncovered
segments on 2026-08-25 shows that describes **1** of them; 17 are cited and valid, on graph ids where
the metric expects state ids. See
[what the uncovered segments actually are](state-coverage-denominator.md). The verdict and the
branch are unchanged — the floor was missed on both readings — but the cause named in the label is
not the cause in the data.

---
Related: [what the uncovered segments actually are](state-coverage-denominator.md), [state-citation](state-citation.md), [pre-registration](pre-registration.md), [one generation, one sample](../decisions/one-generation-one-sample.md)
