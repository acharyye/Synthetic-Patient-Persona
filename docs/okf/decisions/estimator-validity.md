---
type: Decision
title: Estimator validity is distribution-relative — adoption expires when a lever moves the text
description: The adopted is_circumstantial v2.2 was beaten by its predecessor on the v4 run's own text, because the segmentation lever changed the distribution it was validated on. Adoption carries a distribution stamp, and the per-run audit is what detects expiry.
resource: ../../../tests/eval/instrument_v2_gate.json
tags: [instrument, evidence, audit, decision]
timestamp: 2026-11-19T00:00:00Z
---

# Estimator validity is distribution-relative

**Decided 2026-08-25**, on the v4 run. Split out of
[a bar that cannot fail](gate-must-be-able-to-fail.md) on 2026-11-19: that file had been accumulating
one idea in several costumes, and this one is a decision of its own.

## Three failure modes, three mechanisms

| failure mode | what it looks like | mechanism that catches it |
|---|---|---|
| **motivated reading** | a prediction written after the numbers | **pre-registration** |
| **a dead instrument** | a metric that cannot fail — a bar supplied as a literal, a test whose two sides are both zero | **canaries** |
| **a true instrument dying quietly** | an instrument that *was* valid, still looks valid, and is no longer measuring what it measured | **per-run audits** |

The third was demonstrated on the v4 run, on its first exercise, and it is the least obvious of the
three because nothing is broken at any point.

`is_circumstantial` v2.2 was adopted on a held-out sheet at agreement 0.6939 / κ 0.3336, honestly
won. On the v4 run's own text it scores **0.5882 / +0.1765 — beaten by v2.1, the instrument it
replaced** — and under-counts the denominator by **12 of 29**. Nothing regressed. v2.2 is the same
code that won its gate. What changed is the text: its frames were validated on multi-clause segments,
and the SPLIT lever's entire purpose was to produce short single-claim ones.

**Estimator validity is distribution-relative. Any lever that changes the output distribution
silently re-opens every instrument validated on the old one.**

Two consequences, made structural rather than remembered:

- **Adoption is per-distribution, not permanent.** An instrument's validation carries a distribution
  stamp — prompt version and grain statistics — and **expires** when a lever moves them. v2.2's stamp
  is prompt v3, grain 1.80 / 0.567; it expired at prompt v4, grain 2.23 / 0.30.
- **The per-run audit is promoted** from *a check on the estimate* to *the mechanism that detects
  instrument expiry*. Without it, `state_coverage` 0.50 ships as the v4 figure with no indication the
  instrument had degraded on exactly the text it was measuring.

The uncomfortable generalisation: an experiment that changes what it measures can invalidate the
thing measuring it, and **the failure is silent by construction** — the instrument returns numbers of
the usual shape throughout.

## Standing consequence — 2026-11-18

The [2026-11 review](../concepts/verification-locus.md) froze further `is_circumstantial` revision
until a calibrated prior pack exists. The next lever changes the **population**, and no
customer-visible claim currently depends on the instrument, so re-validating it first would be
effort spent twice.

---
Related: [a bar that cannot fail](gate-must-be-able-to-fail.md), [instrument v2](../concepts/instrument-v2.md), [the v4 reading](../concepts/v4-reading.md), [pre-registration](../concepts/pre-registration.md)
