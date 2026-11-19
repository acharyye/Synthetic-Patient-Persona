---
type: Reference
title: External market, regulation and demand evidence (2026-11)
description: Competitors, regulatory anchors, prices and the demand science for persona simulation, as measured in the 2026-11 review — with the two negative controls that say distribution, not engineering, is the constraint.
tags: [market, regulation, competitors, demand, audit]
resource: ../../../docs/AUDIT_MARKET_2026-11.md
timestamp: 2026-11-18T00:00:00Z
---

# External market, regulation and demand evidence (2026-11)

**Measured 2026-11-18** for the [external review](../../../docs/AUDIT_METHOD_2026-11.md). Full brief with every URL: [docs/AUDIT_MARKET_2026-11.md](../../../docs/AUDIT_MARKET_2026-11.md). This file records only the load-bearing facts, because the brief is long and the OKF should be short.

## The two negative controls — weak evidence, and labelled as such

*Downgraded on the owner's 2026-11-19 review: an unmarketed academic repo and a six-week-old solo repo having few stars is the **base rate**, not proof nobody would pay. They show that engineering quality was not the constraint for anyone in this class. They cannot predict whether the demand gate passes, and the gate does not rest on them.*

| | What it is | Outcome |
|---|---|---|
| **Trial Pathfinder** (Liu et al., *Nature* 2021, 592:512) | Encoded eligibility criteria, emulated trials under rule combinations, computed **Shapley values per criterion** — on real Flatiron data. MIT, on PyPI | **69 stars, dead since Jan 2022** |
| **InSilicoTrial_MAS** | MIT, one engineer, 240 tests, bit-identical reproducibility across three engines, *"LLMs narrate patient experience only; medical decisions stay mechanistic"*, *"not clinical evidence, not a regulatory submission and not medical advice"* | **0 stars, ~6 weeks** |

**What they support:** engineering quality has not been the constraint for anyone in this class. **What they do not support:** that nobody would pay — stars measure developer attention, not budget-owner intent, and the demand gate deliberately rests on a conversation and a price request instead of on these two.

## Position in the regulatory framework

**ICH M15** (General Principles for MIDD) reached **Step 4 on 29 Jan 2026** — it supplies the vocabulary and process for asking what evidence a use requires; it blesses no tool. There is **no** "FDA 2024 draft guidance on in silico trials"; the real FDA anchors are the **Nov 2023 device CM&S credibility guidance (final)** and the **Jan 2025 AI draft guidance**.

An AbbVie biostatistics framework (arXiv 2611.10888, Nov 2026) sorts clinical digital twins into five levels by how much of the (X,T,Y) matrix is model-generated and places this project at **Level 5 — "rehearse the trial in silico before enrollment"**, concluding: *"Level 5 is most useful today for early exploration and Phase 2–3 design; regulatory use is context-specific"* and *"bottlenecks are data and validation, not compute."*

Its Level-5 guardrail names two obligations: **validate the generators against real data**, and **test conclusions for sensitivity to misspecification**. The second is already built (sensitivity over the ledger, CRN-paired flips, `sign_is_stable()`). The first has a pre-registered plan and no implementation — which makes the Synthea/customer-data work a regulator-facing obligation, not a nice-to-have.

**Cost to be more than ideation:** ~$5M–$30M and 2–5 years for one context of use (Unlearn needed >2.5 years and >$130M for **one** EMA qualification opinion, at Level 1). Not reachable for a solo MIT project.

## The three closest

| | Moat they have | What this project has that they don't |
|---|---|---|
| **Medidata** Protocol Optimization + **Patient Burden Index** (ASCO, May 2025) | 42,000 trials / 13M patients **fitted**; PBI over 4,000+ activities with **direct patient input**; Novo Nordisk co-development; 2,300 customers | Reproducible to the bit, seeded, event-sourced, offline, MIT — theirs is a cloud black box you cannot re-run, audit or air-gap. And **criterion-level Shapley** vs their protocol-level index |
| **QuantHealth** | $45M Series B (Aug 2026), ~$70M total, 8× sales growth in 2025, Sanofi/Pfizer/Lilly logos, 350M lives, ISO/SOC2 | A small **owned** graph, which is what permits constrained decoding and mechanical citation checking |
| **Prognica** Clinical Operations | Markets the **same pitch** — *"run the trial in simulation before you run it in people"* — at **$300K–5M programmes**, with the same honest admission: *"real screen-fail data needs EHR or claims access we do not have"* | ~1,000 tests and a real deterministic engine vs a build-time demo; exact Shapley vs a cost/protection ratio |

## The pain, priced

Phase III substantial amendment **$535K** median · per screen failure **$3,500–$7,200**, with **>50%** of screened patients failing in an oncology audit · replacing a dropout **~$19,533**, ~30% dropout, ~80% of trials miss enrolment timelines · per day of delay **~$40K** direct, **~$800K/day** unrealised sales (Tufts CSDD).

**One avoided Phase III amendment, or ~70 avoided screen failures, pays for a decade of a $25–75K subscription.** The tool need not be evidentially right to be economically rational — that is the commercial argument, and it is stronger than any regulatory one. It names the buyer: whoever owns the amendment and screen-failure budget, i.e. **ClinOps / study startup / trial design at mid-size biotech**, not regulatory affairs.

## The demand science, in one line each

- **Pew, 30 Sep 2026** (~300 questions, 3 replicated waves): mean absolute error **12.4 pp**, >15 pp on 28% of questions, nearly half had an option no AI respondent chose, stereotype pile-on, knowledge inflated (52% human vs 98% synthetic), and **the model choice changed the answer**.
- **Bisbee et al., *Political Analysis* 2024**: variance drastically too small, subgroups distorted, **several regression coefficients wrong-signed**.
- **Park et al. 2024 (Stanford)**: 83–86% fidelity — but from **two-hour interviews with 1,052 real people**. The opposite of skipping humans.
- **"Persona Collapse"** (arXiv 2604.24698): distinct profiles converge into a narrow behavioural mode.
- **ICC/ESOMAR Code 2025, NIQ, NN/g, Roundtable**: the industry converged on *augment, don't replace*, and a synthetic-research vendor pivoted to **bot detection**.

**What this means here:** constrained decoding answers **fabrication only** — it does nothing for variance collapse, representativeness or wrong-signed relations, and may worsen collapse by narrowing the response space. The **deterministic core is the stronger defence and is undersold**: the engine decides, the LLM speaks, so a model swap changes the words and not one outcome — structural immunity to Pew's central finding. Therefore the claim is not "interview a synthetic patient" but *"every assertion traces to a stated assumption, so the room argues about the assumption instead of the anecdote."* The moment it is sold as patient insight, Pew applies.

## Monetisation, the two that fit one person

1. **Wind-tunnel-as-a-service** (PyMC Labs / Physiomics shape) — sell the analysis: **$15–50K per protocol review** or $5–15K/mo retainer, ~$300–600K/yr solo ceiling. Zero procurement, zero regulatory burden, and it generates the case studies.
2. **Open-core + fitted-prior subscription** (GrowthBook shape: MIT core, 8,610 stars, $23.1M raised, 3,000+ companies) — charge for **fitted** packs, the hosted/versioned/air-gap runtime, the citation corpus. **$25–75K/yr**, $0.5–2M ARR ceiling.

**Reject:** a pack marketplace (literature packs are reproducible by anyone; two sides need two people), benchmark-as-business (LMArena worked because frontier labs needed a **referee** and millions supplied votes), and relicensing (MongoDB/Elastic/Redis/HashiCorp all spawned forks; the threat is not a fork, it is a competitor out-datering you — **the defensible asset is the fitted corpus and the validation evidence, not the code**).

**Terminal outcomes, realistically:** a $1–10M capability tuck-in (Lixoft $6M, Yabble ~£4.5M) · a sustainable ~$300–600K/yr consultancy with a loved OSS core · or a public good with 3,000+ stars and no revenue (Synthea: 10 years, Digital Public Good, grant-funded). Large-business deterministic simulation took 25–40 years, a general-purpose engine, and usually a regulator naming it the standard (Certara, HeartFlow, Schrödinger, ESI→Keysight).

## Where the evidence is thin

Six names in the original premise were unverifiable or misattributed (Halozee, CyberPharma, inSileco, Emulate-as-software, Dreamlab-in-silico, Protem, Comarch, Bulb Capital) and **the "FDA 2024 in-silico draft guidance" does not exist**. No evidence was found of persona simulation as a purchased category in health systems, insurance or HR. Category market-size reports are mutually inconsistent ($3.6B–$8.5B for in-silico trials) and should not be shown to a board — the audited public-company numbers are the honest TAM evidence. The competitor sweep is **not exhaustive by construction**: the research pass hit a websearch rate limit and worked from primary sources.

---
Related: [verification belongs where it is consumed](../concepts/verification-locus.md), [the review method](../../../docs/AUDIT_METHOD_2026-11.md), [the evidence file](../../../docs/AUDIT_EVIDENCE_2026-11.md)
