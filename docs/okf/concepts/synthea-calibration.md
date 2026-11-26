---
type: Concept
title: Synthea calibration — what it is for, what exists, what the first real export showed
description: Synthea is a calibration source for the prior packs with known synthetic provenance, never quotable. The loader joins a real export into patient records; the derivation and the calibration runs do not exist yet.
resource: ../../../tests/eval/synthea_targets.json
tags: [synthea, priors, provenance, calibration]
timestamp: 2026-11-26T00:00:00Z
---

# Synthea calibration

Synthea generates synthetic patients from published statistics and clinical care maps. Wiring it in
moves a pack entry from *a number someone typed* to *a number traceable to a named synthetic
population*. It does **not** make the entry quotable: `SYNTHEA_CALIBRATED` is a provenance **kind**,
not a higher confidence, and only `CUSTOMER_DATA_FITTED` crosses the quotable line.

## What is registered

`tests/eval/synthea_targets.json` holds the commitments, all made before the loader existed:

| | |
|---|---|
| May calibrate | age, sex, comorbidities, medication membership (stage was withdrawn 2026-11-26) |
| May not | health literacy, adherence, diagnostic delay, social determinants, goals, constraints |
| Sample size | n ≥ 50 per entry; below it the entry stays `EXPERT_GUESS`, marked "Synthea n too small" |
| Deceased | excluded from derivation and counted |
| Adoption | diff before adopt — a difference beyond the entry's own tolerance is investigated, and may be declined per entry |
| Medication ladder | membership only; order is Synthea's protocol assumption, not a population fact |
| Jar | pinned by sha256, never by tag |

## What exists

- **The loader** — `src/spp/ingest/synthea_loader.py`. Joins on the `PATIENT` id only, excludes the
  deceased, treats a condition as active only while unstopped, and attributes a medication to a
  condition only through its `REASONCODE`. `load_synthea()` returns `SyntheaPatient` records (sourced
  fields only) plus a `LoadReport`; `load_from_synthea()` returns `PatientDNA`.
- **The code map** — `data/synthea/code_map.json`, by code, built from the real export.
- **Fixtures** that break wrong joins, and **one real export** (113 patients, seed 11) used for
  structure only.
- **Five keep-modules**, never executed.

- **The derivation** — `src/spp/ingest/synthea_derive.py`, run by
  `scripts/derive_synthea_marginals.py`. It prints the Synthea-vs-prior table and writes nothing. The
  sample-size floor, each entry's tolerance and the target list are read from where they were
  registered. An export whose MANIFEST declares a structural run, or that has no MANIFEST, yields a
  table marked FEEDS NO TARGET in which no row can agree or disagree.

## What does not exist

A calibration export, and anything that writes a `SYNTHEA_CALIBRATED` entry into a pack. All 51 pack
marginals are still `EXPERT_GUESS`.

## Why there is no calibration run yet

The registered run names jar sha256 `018ad7f0…`. Synthea publishes its jar at a mutable tag, and on
2026-11-25 that tag was re-published with sha256 `1f3db1eb…`. The registered bytes are not on the
development machine, so the run cannot execute as written. Two options are recorded in
`synthea_targets.json` (`jar_drift`): recover the pinned jar, or amend the registration to the new
hash and repeat the structural run first, since the fixtures and code map were verified against the
old jar.

## What the real export showed

Read by the loader on 2026-11-19 from the 113-patient structural export:

| | |
|---|---|
| Patients | 113 generated, 13 deceased excluded, 100 living |
| Records | 11 — type 2 diabetes 6, breast cancer 3, COPD 2, heart failure 0, rheumatoid arthritis 0 |
| Active condition rows, all living patients | 940, of which 182 map to pack vocabulary |
| Active condition rows, record patients only | 184, of which 47 map |
| Active medication rows | 249, of which 8 map to a pack ladder drug |

Three readings follow.

1. **Most unmapped condition rows are not clinical.** The top unmapped codes are full-time
   employment, "medication review due", stress and education level — social findings and encounter
   bookkeeping that Synthea writes into `conditions.csv`.
2. **Stage is not sourced.** The packs' early / moderate / advanced ladder has no Synthea
   counterpart. Registered 2026-11-26: stage stays `EXPERT_GUESS` until a derivation rule is
   registered for it.
3. **Synthea's drug vocabulary is not the packs'.** Its type 2 diabetes care map dispenses metformin
   and a human insulin mix; the pack ladder's empagliflozin, semaglutide and insulin glargine do not
   occur at all. 14 of 20 ladder drugs across the five packs have no row. For medication membership
   this is the "Synthea disagrees" case the adoption rule anticipates, and for most rungs the honest
   outcome is likely to be *declined*.

## Next

Type 2 diabetes only, from the registered flat run (`-p 1000`, seed 20260827): the one condition
that clears n = 50 without keep-runs. Then the Synthea-vs-prior table, read under the adoption rule.

---
Related: [verification belongs where it is consumed](verification-locus.md), [pre-registration](pre-registration.md)
