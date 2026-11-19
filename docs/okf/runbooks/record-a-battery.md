---
type: Runbook
title: Record a narration battery
description: Canary first, then record. How to run the live narration eval so the resulting bundle is evidence rather than a number.
resource: ../../../scripts/record_narration.py
tags: [runbook, narration, evidence, cassettes, ollama]
timestamp: 2026-08-24T00:00:00Z
---

# Record a narration battery

Runs the 30-case compliance battery against a live model and writes gated cassettes plus an
[evidence bundle](../concepts/v3-reading.md). Nothing here is needed for the offline suite — it
exists so first contact with a real model happens against a pipeline where malformed citations are
ungrammatical and bad recordings cannot persist.

## Prerequisites

| | |
|---|---|
| Model server | `ollama serve` running; `ollama pull qwen2.5:7b-instruct` |
| Model identity | read from `NARRATION_MODEL.params["model"]` in `assumptions.py`, pinned by **digest** at run time |
| Env | `SPP_LIVE=true PYTHONPATH=src` |

The run **refuses to start** if the digest cannot be resolved: a cassette that cannot name its
weights is not evidence about a model.

## 1. Canary — always first

```bash
SPP_LIVE=true PYTHONPATH=src python scripts/record_narration.py --canary --release v0.4
```

Scores the battery against deliberately degraded configurations (starved context, stripped
instructions, unconstrained ids, `strip_state_ids`) and **refuses to proceed unless the scores
fall**. An eval that cannot fail is not evidence.

Pass the **same `--release`** you will record under. The canary result is stashed at
`evidence/<release>/_canary.json` and the recording step reads it from there to stamp
`canary_sensitive` on the manifest. Skip it, or use a different release string, and the bundle
records `null` — a bundle that cannot say whether its instrument was sensitive.

Two things the canary prints that are findings, not noise:

- **`strip_state_ids` is not clean.** `f_recall` moves with it (0.5306 → 0.6939 in v0.4), and so
  does `f_recall_exclusive`. State ids displace graph citations for claims with no other citation
  path. Record it; do not read `state_coverage` as free of it.
- **"insensitive" has two causes.** The script disambiguates on the normal-config absolute scores:
  low scores everywhere is a *model* question, a vanished gap at high scores is an *instrument*
  question. Triage accordingly — do not adjust bars.

## 2. Record

```bash
SPP_LIVE=true PYTHONPATH=src python scripts/record_narration.py --record --release v0.4
```

Add `--rerecord` **after a `PROMPT_VERSION` bump**. The recorder refuses to append to recordings made
under a different prompt (`require_compatible`), and `--rerecord` says "start over" as a parameter
rather than by moving files aside. The previous cassette is archived to
`tests/cassettes/archive/` **after** every take is in hand, so a run that dies mid-battery leaves the
repository intact.

What happens, in order: the model is **warmed** (a cold load and a warm one give different output for
identical inputs — the run refuses rather than proceed against an unknown load state), the battery is
scored in **one generation pass** that feeds both the report and the cassette
([why](../decisions/one-generation-one-sample.md)), only gate-passing responses persist, failures go
to `<name>.quarantine.json`, and the bundle is written to `evidence/<release>/<timestamp>/`.

## 3. Read it — the protocol is pre-committed

Do **not** act on the aggregates before reading, in full:

1. the **5 sampled raw takes** printed at the end (seed-chosen, so not cherry-picked), then
2. **every** quarantine entry.

**No metric here catches degeneracy.** A model answering every question with one short factual
segment citing one correct fact scores `citation_validity` 1.0 and can clear recall on the easy
questions while being useless as a persona voice. `mean_segments_per_take`, `mean_response_chars`
and `single_segment_rate` support the eye; they do not replace it. The script warns when
`single_segment_rate` exceeds 0.5 — it was 0.57 in v0.4.

Bars are read from `tests/eval/pass_bars.json`, registered before any live run. A missed bar means
investigate; changing a bar is its own explicit commit.

## Outputs

| Path | What |
|---|---|
| `tests/cassettes/<name>.json` | gated recordings — only responses that passed the citation gate |
| `tests/cassettes/<name>.quarantine.json` | the compliance dataset: every rejection with its reason |
| `tests/cassettes/<name>.compliance.json` | report + verdict summary |
| `evidence/<release>/<timestamp>/` | the bundle: manifest, canary, compliance, 5 takes, quarantine, README |

The bundle has **no verdict yet** — that is a separate act. See
[Adjudicate a bundle](adjudicate-a-bundle.md).

---
Related: [Adjudicate a bundle](adjudicate-a-bundle.md), [Pre-registration](../concepts/pre-registration.md), [State-citation](../concepts/state-citation.md), [One generation, one sample](../decisions/one-generation-one-sample.md), [A bar that cannot fail](../decisions/gate-must-be-able-to-fail.md)
