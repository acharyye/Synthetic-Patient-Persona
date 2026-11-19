---
type: Concept
title: The v4 reading — the lever worked and the floor was missed
description: The v0.5 battery under prompt v4 (one claim per segment). Compounds fell and state and graph citation rose together, but gold-semantics coverage on the audited slice read 0.556 against a floor of 0.6.
resource: ../../../evidence/v0.5/20260825T123023+0000/adjudication_v4.json
tags: [v4, state-citation, evidence, finding]
timestamp: 2026-11-19T00:00:00Z
---

# The v4 reading — the lever worked and the floor was missed

**Recorded 2026-08-25** against `qwen2.5:7b-instruct@845dbda0ea48`, prompt v4, 30/30 takes accepted,
0 quarantined. Bundle: `evidence/v0.5/20260825T123023+0000/`. Seventeen arms were
[pre-registered](pre-registration.md) in `tests/eval/v4_expected_shape.json` and pushed before the
prompt change existed. Both clauses of the verdict are part of it; neither stands alone.

## The lever worked

Prompt v4 asks for one claim per segment — an instruction, not a schema change, so every structural
guarantee carried over untouched.

| | v3 (v0.4) | v4 (v0.5) |
|---|---|---|
| `single_segment_rate` | 0.567 | 0.300 |
| `mean_segments_per_take` | 1.80 | 2.23 |
| `state_coverage`, v2.2 estimator on both | 0.4419 | 0.500 |
| `f_recall_exclusive` | 0.4615 | 0.5897 |
| `model_recall` | 0.5862 | 0.6724 |

State and graph citation rose **together**, which is the displacement finding's direct test: at v3
the two competed for one segment's citations.

## The floor was missed

Gold-semantics coverage on the audited slice: **0.556 against 0.6** — 10 apt-citing segments of 18
coverable, from blind labels. The slice held 4 `sym` takes and 0 burden takes of 15, which sized the
miss and does not excuse it. For the same reason `schema_gap_union` (0.379 on the slice) is **not
adjudicable** against an arm registered at population level.

## Which `state_coverage` is which

Six values are live across the surfaces. None is wrong; each belongs to an instrument.

| value | run | instrument |
|---|---|---|
| 0.5641 | v0.4 | the bundle's own aggregate (v1 classifier, first sample) |
| 0.5135 | v0.4 | v1 classifier replaying the committed cassette |
| 0.5263 | v0.4 | blind human labels, coverable segments |
| 0.4419 | v0.4 | v2.2 estimator |
| 0.500 | v0.5 | the bundle's aggregate (v2.2 estimator) |
| 0.556 | v0.5 | blind human labels on the audited slice |

**The floor is answered at gold semantics only** — 0.5263 at v0.4 and 0.556 at v0.5. Comparing
0.4419 with 0.500 is right for the lever's effect and wrong for quoting either run.

## What the factual-fraction table says at v0.5

| tag | v0.3 | v0.4 | v0.5 |
|---|---|---|---|
| burden | 0.400 | 0.700 | 0.900 |
| mitigation | 0.4433 | 0.9333 | 0.850 |
| ae *(control)* | 0.9333 | 1.0 | 0.900 |
| tx / proc *(controls)* | 1.0 / 0.900 | 1.0 / 1.0 | 1.0 / 1.0 |
| sym | 0.0 | 0.0 | 0.0 |

Mitigation fell 0.08 from v0.4, and `ae` sits **exactly on** its 0.10 control bound. `sym` at zero
across four runs is uninformative rather than satisfied: no bar distinguishes the two.

## What the audit found beside the arms

- **The adopted instrument expired.** v2.2 was beaten by v2.1 on this run's own text — see
  [estimator validity](../decisions/estimator-validity.md).
- **Gap-citing is systematic**: 4 of 14 state-citing segments cite the causally nearest id (the drug
  that causes a symptom, the condition that produces it). `state_citation_aptness` 0.913 → 0.714, in
  the direction registered before the run.
- **Identical claim shapes are intermittently grounded** — one medication list cites, another of the
  same shape does not. The next lever is citation reliability, not schema expressiveness.
- Zero `B-`/`J-` citations in the slice; `P-constraints.*` ids cited; a persona quoting its own
  adherence parameter ("about 77% of the time").

None of these five has a task. Instrument and narration work is frozen until a calibrated pack exists.

---
Related: [The v3 reading](v3-reading.md), [state-citation](state-citation.md), [estimator validity](../decisions/estimator-validity.md), [instrument v2](instrument-v2.md)
