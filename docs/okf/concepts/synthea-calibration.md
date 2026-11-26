---
type: Concept
title: Synthea calibration — what it is for, what exists, what the first real export showed
description: Synthea is a calibration source for the prior packs with known synthetic provenance, never quotable. The loader joins a real export into patient records; the derivation and the calibration runs do not exist yet.
resource: ../../../tests/eval/synthea_targets.json
tags: [synthea, priors, provenance, calibration]
timestamp: 2026-11-19T00:00:00Z
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
| May calibrate | age, sex, stage, comorbidities, medication membership |
| May not | health literacy, adherence, diagnostic delay, social determinants, goals, constraints |
| Sample size | n ≥ 50 per entry; below it the entry stays `EXPERT_GUESS`, marked "Synthea n too small" |
| Deceased | excluded from derivation and counted |
| Adoption | diff before adopt — a large disagreement is investigated, and may be declined per entry |
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

## What does not exist

The marginal derivation, the calibration runs, and anything that writes a `SYNTHEA_CALIBRATED` entry
into a pack. All 51 pack marginals are still `EXPERT_GUESS`.

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
   counterpart. The target list permits calibrating it, but that needs a registered derivation rule
   first; the loader leaves it empty and says so in `fields_not_sourced`.
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
