---
type: Index
title: References
description: External sources — Hetionet, Synthea, regulators, and the 2026-11 market review.
tags: [references, index]
timestamp: 2026-11-18T00:00:00Z
---

# References

External sources — Hetionet, Synthea, dashboards, tickets.

| File | Description |
|---|---|
| [external-2026-11.md](external-2026-11.md) | Market, regulation, prices and the demand science as measured in the 2026-11 review, with the two negative controls. |

## External sources without a concept file

Kept here rather than as files because they are stable identifiers, not project knowledge. The rule for this folder: a reference earns its own file when there is something to *decide* about it.

| Source | What it is |
|---|---|
| **Hetionet v1.0** | CC0. 2.25M edges; the persona-relevant metaedge slice is **47,031 nodes / 277,997 edges**. Loaded by `python -m spp.ingest.kg_loader`. **Not the default grounding path** — the owned `data/knowledge/core.json` is. Docker maps host ports **7475/7688**, not 7474/7687. |
| **Synthea** | `synthetichealth/synthea`, Apache-2.0, 3,470 stars, a declared Digital Public Good, grant-funded. The jar comes from the **mutable** `master-branch-latest` tag, so it is pinned by `jar_sha256` in `data/synthea/structural_seed11/MANIFEST.json`, never by the tag. |
| **ICH M15** | General Principles for Model-Informed Drug Development — **Step 4, 29 Jan 2026**. Supplies the framework for asking what evidence a use requires; blesses no tool. https://database.ich.org/sites/default/files/ICH_M15_Step4_Final_Guideline_2026_0129.pdf |
| **FDA CM&S credibility guidance** | Devices. **Final, 17 Nov 2023** — the basis of VICTRE and HeartFlow-type submissions. There is **no** "FDA 2024 draft guidance on in silico trials". https://fda.gov/media/175363/download |
| **AbbVie Level-5 framework** | arXiv 2611.10888 (Nov 2026) — five levels of clinical digital twins by how much of the (X,T,Y) trial matrix is model-generated. Places this project at **Level 5** and names its two obligations. https://arxiv.org/html/2611.10888v1 |
| **Pew Research Center, 30 Sep 2026** | The largest independent test of AI survey respondents: ~300 questions, 3 replicated waves, **12.4 pp mean absolute error**. https://www.pewresearch.org/data-labs/2026-09-30/can-ai-stand-in-for-human-survey-takers-not-really/ |
| **Trial Pathfinder** | Liu et al., *Nature* 2021, 592:512 + MIT on PyPI. The exact Shapley criterion-attribution method, on real data. **69 stars, abandoned Jan 2022** — the negative control on prestige. |
| **InSilicoTrial_MAS** | MIT, solo, 240 tests, same philosophy and disclaimers. **0 stars in ~6 weeks** — the negative control on the concept. |

Conventions: [../SCHEMA.md](../SCHEMA.md) · Template: [../_TEMPLATE_concept.md](../_TEMPLATE_concept.md) · Entry point: [../index.md](../index.md)
