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

- **The runner** — `scripts/run_synthea.py` takes a jar and an expected sha256, refuses a mismatch,
  and writes the MANIFEST whose `purpose` decides whether an export may feed a target.

## What does not exist

Anything that writes a `SYNTHEA_CALIBRATED` entry into a pack. All 51 pack marginals are still
`EXPERT_GUESS`: the calibration run has been read, and nothing has been adopted.

## The calibration run — 2026-11-26

Registered parameters: `-p 1000`, seed 20260827, floor n = 50. The jar was amended on the record to
sha256 `1f3db1eb…` after Synthea's mutable tag was re-published, and the structural check was
repeated on the new jar first (same columns, same enum values, no code description changed).

1178 patients generated, 178 deceased excluded, 1000 living. Records: type 2 diabetes **62**, COPD 17,
breast cancer 9, rheumatoid arthritis 3, heart failure 1. **Only type 2 diabetes clears the floor.**

| type 2 diabetes entry | Synthea | prior | tolerance | verdict |
|---|---|---|---|---|
| age (mean) | 62.3 | 62.0 | 4.0 | within |
| sex = female | 0.532 | 0.48 | 0.06 | within |
| hypertension | 0.645 | 0.70 | 0.2 | within |
| obesity | 0.742 | 0.60 | 0.2 | within |
| CKD | 0.258 | 0.35 | 0.2 | within |
| diabetic neuropathy | 0.323 | 0.30 | 0.2 | within |
| diabetic retinopathy | 0.145 | 0.25 | 0.2 | within |
| **dyslipidemia** | 0.177 | 0.65 | 0.2 | **disagrees** |
| **cardiovascular disease** | 0.516 | 0.30 | 0.2 | **disagrees** |
| depression, stage, adherence, dx delay, literacy | — | | | not sourced |
| on metformin / empagliflozin / semaglutide / insulin glargine | 0.435 / 0 / 0 / 0 | | | rate only |

**The two disagreements, investigated.** Dyslipidemia is a care-map artifact in both directions: the
map counts only "Hyperlipidemia" (17.7%), while 98% of the diabetic records carry
"Hypertriglyceridemia" because Synthea's metabolic-syndrome module routes every diabetic through that
state. Neither 0.18 nor 0.98 is a population rate. Cardiovascular disease reads 0.516 against a prior
near published estimates; ischemic heart disease alone is 48% of the records. Recommended reading:
decline both. Not yet confirmed by the owner.

**A format question the table raises.** A pack's comorbidities are one marginal with one provenance
covering every name, so adopting hypertension while declining dyslipidemia needs per-name provenance
the pack format cannot express today.

## What the first, 113-patient export showed

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

The owner reads the table and decides, per entry, what is adopted. Then a producer that writes those
entries with `kind: synthea_calibrated`, the jar hash and the seed — which first needs the per-name
provenance question answered.

---
Related: [verification belongs where it is consumed](verification-locus.md), [pre-registration](pre-registration.md)
