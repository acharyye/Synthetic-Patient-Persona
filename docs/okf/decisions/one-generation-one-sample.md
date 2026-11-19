---
type: Decision
title: One generation feeds both the report and the recording
description: Scoring and cassette-recording were two separate live passes over identical prompts, so archived aggregates described a sample that was never recorded. Now a single pass, via score(on_take=...).
resource: ../../../src/spp/narration/evaluation.py
tags: [evidence, cassettes, reproducibility, decision]
timestamp: 2026-08-24T00:00:00Z
---

# One generation feeds both the report and the recording

**Decided 2026-08-24**, after adjudicating the [v3 reading](../concepts/v3-reading.md).

## What was wrong

`record_narration.py --record` ran the battery **twice** against the live model: once inside
`score()` to produce `compliance.json`, and once again to capture raw exchanges for the cassette.
Same prompts, two samples.

Ollama at `temperature 0.0` with a fixed seed is nearly — not exactly — reproducible. In the v0.4
run **two of thirty takes drifted** between the passes. Replaying the committed cassette reproduces
`model_recall` and `f_recall` exactly, but gives `circumstantial_segments` 37 against the bundle's 39
and **`state_coverage` 0.5135 against the bundle's 0.5641**.

So the archived aggregates described a generation that exists nowhere, and the committed recording
described numbers nobody published. Each artifact looked like evidence for the other. This is the
same species as *[cassettes are recordings, not goldens](../concepts/state-citation.md)*: an
artifact that replays a claim it was never the basis for.

Two smaller faults rode along:

- The recording pass always passed `repair=None`, so it recorded **first attempts** while the report
  scored **retried** ones. A take repaired on its second attempt was archived broken. (No take was
  retried in v0.4, so this did not fire — it was waiting.)
- `score()` did not catch the recorder's context-overflow exception, so an overflow aborted the
  scoring pass before the quarantine path below it could ever run. That path was unreachable code.

## What was decided

**One generation pass.** `score()` takes `on_take(prompt, raw, check)` and calls it once per case
with the **final** attempt; the recorder consumes it. The report and the cassette are the same sample
by construction, and a live run costs half the model calls — which also halves the exposure to the
adapter timeout that cost a recording on 2026-08-23.

The exception was consolidated onto the library's own `ContextOverflow`; the script's near-identical
private copy is gone.

Pinned by `TestScoringAndRecordingSeeTheSameSample` in `tests/test_narration_compliance.py`, which
asserts one call per case, that the handed-over take renders to what was scored, and that a retried
case hands over the **repaired** take.

## The v0.4 bundle is not retro-fixed

It records what happened. `evidence/v0.4/20260823T170152+0000/NOTE.md` states the discrepancy, both
figures, and that the adjudication branch is unchanged because both readings miss the floor. The next
bundle is reproducible from its own cassette; that one is not, and says so.

---
Related: [The v3 reading](../concepts/v3-reading.md), [pre-registration](../concepts/pre-registration.md), [a bar that cannot fail](gate-must-be-able-to-fail.md)
