---
type: Concept
title: Pre-registration — a prediction written after seeing the numbers is not a prediction
description: Expected shapes and pass bars are committed before the recording exists; amendments are legal only while nothing is recorded, and must be stated.
resource: ../../../protocols/
tags: [method, evidence, pre-registration, falsifiability]
timestamp: 2026-08-17T00:00:00Z
---

# Pre-registration

Before a battery is recorded, the **expected shape** and the **pass bars** are committed to the repo.
The rule is the point: *a prediction written after seeing the numbers is not a prediction.*

## What gets pre-registered

- `pass_bars.json` — the thresholds a reading must clear.
- The **expected shape** of a new measurement, including what would **falsify** the hypothesis
  behind it.

## The amendment rule

A pre-registered file may be amended **only while nothing is recorded yet**, and the amendment must
be **stated rather than slipped in**.

Worked example — the v3 shape was amended from three namespaces to four (`c98cb19`) *before* any v3
recording existed. The amendment was logged as an amendment, with its reasoning, precisely because
the file is pre-registered.

## Escape clauses are controls, not ceilings

When a hypothesis needs an escape clause, use a **control arm**, not a threshold number. A number is
arbitrary; a control discriminates.

In the v3 shape: graph-knowledge tags (`ae`, `tx`, `proc`) gained nothing from the new namespaces and
must stay **flat within 0.10**.

- Burden and mitigation recover **while controls hold** → the new ids did the work.
- **Everything rises together** → over-correction, however good the burden numbers look.
- `sym` is explicitly **not** a control — symptoms are simulated state, so citations there are
  legitimate and a rise with citations attached is correct.

## Second measurement, not repair

A re-record changes **exactly one declared variable** and holds everything else identical — same
weights (digest verified), same sampling, same battery, same bars. The earlier bundle stays untouched
as the comparison baseline and the new one writes beside it.

---
Related: [state-citation](state-citation.md), [Declare the environment, then enforce it in tiers](../decisions/environment-tiers.md)
