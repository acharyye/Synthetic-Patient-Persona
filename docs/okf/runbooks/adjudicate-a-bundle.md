---
type: Runbook
title: Adjudicate an evidence bundle
description: Read an archived bundle against the arms registered before it existed — a pure read over compliance.json, reproducible without a model run.
resource: ../../../scripts/adjudicate_bundle.py
tags: [runbook, narration, evidence, pre-registration]
timestamp: 2026-08-24T00:00:00Z
---

# Adjudicate an evidence bundle

Recording a run and reading a run are **separate acts**. The verdict is a pure function of
`compliance.json`, `quarantine.json` and `tests/eval/v3_expected_shape.json` — no model involved — so
anyone who doubts a written `adjudication.json` can delete it and reproduce it exactly.

## Run it

```bash
PYTHONPATH=src python scripts/adjudicate_bundle.py --release v0.4
```

Or name a bundle directory explicitly:

```bash
PYTHONPATH=src python scripts/adjudicate_bundle.py evidence/v0.4/20260823T170152+0000
```

It prints the arm-by-arm report, writes `adjudication.json` into the bundle, and re-renders the
bundle README so its reading protocol gains a fifth step.

**Exit status is the branch of the pre-registered tree**: `0` only for `RECOVERY`, non-zero
otherwise, so a shell cannot silently record a miss as a success. That is a **report, not a gate**.

## Reading order matters

The verdict is written **last and read last**. A reader who meets it first goes through the raw takes
looking for it, which is the failure the reading protocol exists to prevent. The bundle README
enforces the order: canary → takes → quarantine → aggregates → adjudication.

## When an arm misses

An arm below its bound means **investigate**. The one thing it must never mean is editing
`v3_expected_shape.json` in the same breath — an expectation revised after seeing the number is not
an expectation. See [pre-registration](../concepts/pre-registration.md).

Amendments are legal only while nothing is recorded, and they are recorded *in* the adjudication with
their date and reason. Two live in the v0.4 bundle: the four-namespace split, and the explicit
`state_coverage` denominator fixed before any v3 recording existed.

## What v0.4 read

`OVER-CORRECTION`. The recovery arms landed inside their bounds (burden 0.70, mitigation 0.9333) and
all three controls stayed flat at 1.0 — but `state_coverage` read 0.5641 against a floor of 0.6, so
the tags recovered **without the state ids being cited**: relabelled, not grounded. Full reading:
[the v3 reading](../concepts/v3-reading.md).

---
Related: [Record a battery](record-a-battery.md), [The v3 reading](../concepts/v3-reading.md), [Pre-registration](../concepts/pre-registration.md), [One generation, one sample](../decisions/one-generation-one-sample.md)
