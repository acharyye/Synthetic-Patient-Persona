# External read for the 2026-11 review: market, regulation, money

**Run date:** 2026-11-18 · **Method:** [AUDIT_METHOD_2026-11.md](AUDIT_METHOD_2026-11.md) · **Internal findings:** [AUDIT_EVIDENCE_2026-11.md](AUDIT_EVIDENCE_2026-11.md)

`[M]` = measured, sourced, URL given. `[I]` = inference/judgement. Where evidence is thin it says so rather than filling the gap.

**Verification caveat, stated up front:** this is the weakest-verified part of the review. The research node hit a websearch rate limit mid-run and switched to primary sources (SEC filings, vendor pages, journals, GitHub API) — the better method, but it means the competitor sweep is **not exhaustive by construction**. Every competitor claim is single-sourced. A vendor not searched for could change the read.

## 1. The two negative controls — weak evidence, directionally useful

**Owner's objection on review (2026-11-19), accepted:** *"An academic repo nobody marketed and a six-week-old solo repo having few stars is the base rate, not proof that nobody would pay."* That is correct and it downgrades this section. What follows is stated with its real weight, because a plan that rests on it would be resting on nothing.

**`[M]` Trial Pathfinder** (Liu et al., *Nature* 2021, 592:512) encoded eligibility criteria, emulated trials under rule combinations, computed **Shapley values per criterion**, and suggested data-driven criteria — on **real** Flatiron data. MIT-licensed, on PyPI. **69 stars, last push Jan 2022.** → https://www.nature.com/articles/s41586-021-03430-5 · https://github.com/RuishanLiu/TrialPathfinder

There is also a registered clinical trial doing exactly this: NCT06314542, Monte Carlo + propensity matching + Shapley value per criterion on real-world lung-cancer criteria. → https://clinicaltrials.gov/ct2/show/NCT06314542

**`[M]` InSilicoTrial_MAS** (SergeyGer) — MIT, one engineer, v1.0.0, 240 tests, deterministic offline persona provider, bit-identical results across three execution engines proven by an equivalence test, per-patient inspectable records including "the persona's own account of the visit", reproducibility audit + lineage graph. Its own text: *"LLMs narrate patient experience only; medical decisions stay mechanistic"*; *"a trial-design decision-support tool: not clinical evidence, not a regulatory submission and not medical advice"*; *"bundled population priors… are illustrative and must be replaced with licensed reference data before any regulated use"*. Created 2 Oct 2026, 57 commits. **0 stars.** → https://github.com/SergeyGer/InSilicoTrial_MAS

**`[I]` What they do and do not show.**

*What they show,* and this is the honest extent: **engineering quality has not been anybody's constraint in this class.** Two independent solo convergences on the same artifact, philosophy and disclaimers; a *Nature* publication of the exact attribution method; three years of a widely-used deterministic synthetic-patient generator (Synthea: 3,470 stars, no revenue). None of these produced commercial traction. Whatever stopped them was not the code.

*What they do **not** show:* that nobody would pay. Low star counts on an unmarketed academic repo and a six-week-old solo repo are the **base rate** — most repos get few stars, and stars measure developer attention, not budget-owner intent. Trial Pathfinder's abandonment is arguably evidence about *academic incentive structures* (a *Nature* paper already paid for the work) rather than about market demand. And InSilicoTrial_MAS at six weeks old is simply too young to read either way.

**Consequence for the plan:** these controls motivate *testing* demand cheaply. They must not be used to *predict* the test's outcome, and the demand gate does not rest on them. The stronger independent support for "distribution, not engineering" is internal: 55.7% of commits went to instrument work while O3 (realism from data) sat at 0.0, and the priors are still `EXPERT_GUESS` on all 51 shipped marginals.

## 2. Competitive landscape

### 2.1 Premises that did not survive contact with sources

Six names in the original question are unverifiable or misattributed. Recorded because competitive intel feeding strategy shouldn't contain noise:

| Named | Finding `[M]` |
|---|---|
| "Halozee" | No such company in in-silico trials. Likely confusion with **Halozyme** (ENHANZE drug-delivery licensing — irrelevant) |
| "CyberPharma" | No credible in-silico-trial company by this name |
| "inSileco" | Real, but **environmental** data science in Québec (biodiversity, cumulative-effects) — https://insileco.io/en/about |
| "Emulate" | Emulate Inc is **organ-on-chip hardware** (>$200M raised, $82M Series E 2021) — not a software VCA — https://emulatebio.com/press/emulate-closes-82-million-series-e-financing |
| "Dreamlab Technologies" | The visible entity is a Swiss cybersecurity firm (CyObs/CySOC). **No** in-silico-trial evidence found — https://dreamlab.net/en/latest |
| "Trium / Protem" | Trium Analysis Online does digital biomarkers/actigraphy (ActiBelt), not protocol simulation; "Protem" returned nothing — https://trium.de/about |
| "Comarch" | Hospital/pharmacy IT portfolio; no trial-simulation product — https://www.comarch.com/healthcare/portfolio/ |
| "Bulb Capital" | Could not confirm as a funder of this category |
| "FDA 2024 draft guidance on in silico trials" | **Does not exist.** See §3 for the real anchors |
| "ASCT position" | Not found. ASCPT (MIDD Paired Meeting Program) and ICH are documented; ASCT isn't |
| "DARPA PSB / ARO persona-trajectory" | Unverifiable as named. DARPA BTO and its MBA programme are real, as are NATO STO "Human Digital Twin" proceedings — https://www.darpa.mil/about/offices/bto |

### 2.2 The incumbent that matters most

**`[M]` Medidata (Dassault Systèmes), Protocol Optimization — launched 29 May 2025 at ASCO.** Named capabilities: pressure-test design changes, benchmark the schedule of assessments, **mitigate dropout risk**, balance visit-level burden, digitise protocols to USDM. Data foundation: **42,000+ trials, 13M patients, ~2,300 customers, 1M+ registered users.** → https://www.3ds.com/newsroom/press-releases/medidata-debuts-protocol-optimization-asco-leveraging-ai-transform-study-experience · https://www.medidata.com/en/study-experience/protocol-optimization/

**`[M]` Its Patient Burden Index** scores **six dimensions** — pain, invasiveness, harmful exposure, duration, anxiety, item count — across **4,000+ clinical activities** including CAR-T, gene therapy and digital tools, with Low/Medium/High tiers, built over a year from literature review, cross-functional clinical expertise **and direct input from trial participants**. **Novo Nordisk integrated PBI into its internal protocol design tool** via Acorn AI, with joint research. → https://www.clinicalleader.com/doc/refining-the-patient-burden-index-a-data-driven-approach-to-protocol-optimization-0001

**`[M]` Medidata Study Feasibility** simulates over 38,000 studies / 41,000 sites and cites **43% of sites failing to enrol a single patient** and **up to 80% of studies missing enrolment goals**. → https://www.medidata.com/en/study-experience/study-feasibility/

**`[M]` Medidata Synthetic Control Arm** was supported by the FDA in Medicenna's Phase 3 rGBM registrational trial (Oct 2020), cutting prospective control patients by ~100 (~two-thirds). → https://www.3ds.com/newsroom/press-releases/medidata-synthetic-control-arm-supported-us-food-and-drug-administration-use-medicenna-therapeutics-corp-phase-3-registrational-trial-recurrent-glioblastoma

**`[M]` Its patient voice is real, not synthetic:** a Patient Insights Board of advocates and IDEO-led "Patient Insight Studios". → https://www.medidata.com/en/clinical-trial-products/patient-centric-clinical-trials/patient-engagement-and-insights/

**`[M]` Context:** Dassault reports Medidata Enterprise grew only **1% in 2025** (Moderna cut run-rate; industry study starts −7% YoY), indirect −5%. → https://investor.3ds.com/static-files/f19e5139-e37f-44dd-8986-49a073873758

### 2.3 Funded in-silico / VCA platforms

| Player | Claim | Money `[M]` |
|---|---|---|
| **QuantHealth** (Tel Aviv, 2020) | Protocol optimisation over I/E criteria, arms, control, endpoints; enrolment prediction; its own **Biomedical Knowledge Graph** (claims 100K drug data elements, 350M lives, 180K+ trials). ISO 27001, SOC 2 Type 2/3 | **$45M Series B, 4 Aug 2026** (Qumra Capital, Pitango HealthTech, **Sanofi Ventures**, Bertelsmann Healthcare, GC Ventures, NewHealth); ~$70M total; **"eightfold increase in sales during 2025"**; logos IQVIA, Sanofi, Astellas, Pfizer, Accenture, Lilly; published UC + cholesterol simulations — https://quanthealth.ai/ · https://www.axios.com/pro/health-tech-deals/2026-08-04/quanthealth-45m-simulate-clinical-trials-ai-drug-discovery |
| **Unlearn.AI** | Patient-level digital twins → PROCOVA → smaller control arms; up to 40% control-arm reduction in Alzheimer's case studies | **$50M Series C (Feb 2024, Altimeter)**, **>$130M total**; multi-year Merck KGaA collaboration; Fierce 2026 AI Innovation Award, Clinical Trial Design — https://www.businesswire.com/news/home/20240206806844/en/ |
| **Nova In Silico** (ex-Novadiscovery, Lyon) | QSP mechanistic models, digital twins, virtual populations; **jinkō** | Series A **€5M** (Debiopharm, Jan 2020), A2 **€2.5M** with **Sanofi investing** (Jan 2021) |
| **Valinor Discovery** (SF) | Probabilistic virtual cohorts from matched multi-omics; "a prediction service, not a consulting engagement" | **$13M seed, Dec 2025** (CRV, Harpoon, Amino Collective, Pelion) |
| **Sapien Labs** | Rebuilds ~half a control group from real records; psychiatry-first | Tiny: "Seeds 8 · Donors 1,500 · Trial patients 300" — https://sapien.bio/evidence |
| **Ebenbuild** (FR) | Twinhale, in-silico pulmonary drug delivery | **€2.3M EIC grant, Jul 2025** |
| **InSilicoTrials Technologies** (IT) | Virtual patient modelling for CROs | HanchorBio partnership — https://www.insilicotrials.com/ |
| **Certara** | **Trial Simulator** — seeded virtual populations, PK/PD, dose/schedule | **FY2025 revenue $418.8M (+9%)**, adj EBITDA $134.5M; sold its Regulatory & Medical Writing arm to Veristat Apr 2026 — https://www.certara.com/pressrelease/certara-reports-fourth-quarter-2025-financial-results-provides-full-year-2026-guidance/ |
| **Simulations Plus** | GAMBOOZ/SDM, Monolix/Simulx | **FY2025 $79.2M (+13%); software $45.8M (58%)**; Q4 software **−9% to $9.0M**; bought Lixoft for **$6M cash** (2020) |
| **Truveta** | Real-time trials with regulatory-grade external control arms | **~$1B valuation (Jan 2025), $415M raised**, 30 health systems, 120M+ patients; and NCT07674095 is a registered trial **assessing whether its dataset meets FDA fit-for-purpose requirements** for external controls |

### 2.4 The most literal copy of the pitch

**`[M]` Prognica Labs — Clinical Operations.** *"Run the trial in simulation before you run it in people."* 8 capability areas, **19 specialised agents**, **4,000 simulated runs**, *"0 single-point answers presented without a range."* Per-criterion eligibility with a cumulative funnel and counterfactual (*"Relaxing EXC-07 alone returns 18K patients"*); dropout by burden segment (low 86% / standard 74% / high 58% / travel >90min 51%) with modelled interventions (remote visits +7pts, travel reimbursement +4pts, window widening +3pts); Poisson arrivals with Gamma-fitted per-site rates, **Weibull dropout hazard**, P10/P50/P90 readouts, **power under simulated operating conditions**; RAG narrative *"cited to registry and literature records"*. → https://prognica.com/platform/clinical-operations

**It is honest in the same places SPP is honest:** *"All platform outputs are planning models, not regulatory submissions or clinical advice."* And the sentence that describes SPP's ceiling too: *"Retention factors are **typed heuristics drawn from the trial-methodology literature, not patient-level screen-fail rates** — real screen-fail data needs EHR or claims access we do not have."* Programme scale **USD 300K–5M across multiple years**. → https://prognica.com/industries/government-public-health

**`[I]` Caveat:** its dashboards are self-labelled build-time illustrations on a synthetic protocol, and it presents as a services shop with a platform layer. I could not verify shipping enterprise deployments. But the *marketing* is enough to end any novelty claim.

### 2.5 LLM persona simulators (the narration-side twins)

**`[M]` PersonaCite** (CHI 2026, arXiv 2601.22288) — agentic personas as "evidence-bounded research instruments": retrieves real voice-of-customer artefacts per turn, constrains responses to retrieved evidence, **abstains when data insufficient**, gives response-level source attribution. Closest architectural twin to SPP's narration layer, but customer research, and self-declared not a product. → https://arxiv.org/abs/2601.22288

**`[M]`** Also: TWIN-GPT (LLM digital twins for trials), VTHarness (arXiv 2611.05551, agentic virtual-trial protocol operationalisation + VTBenchmark), Artificial Clinic Intelligence (PMC12611047, cohort enrichment + "Virtual Intervention Permeability"). **`[M]` Synthea** (MITRE): Apache-2.0, **3,470 stars / 974 forks**, live since 2016, declared a **Digital Public Good**, grant-funded, **no revenue** — the null result for deterministic synthetic-patient OSS. → https://github.com/synthetichealth/synthea · https://www.digitalpublicgoods.net/r/synthea

### 2.6 The three closest, and where SPP genuinely differs `[I]`

| | Has that SPP doesn't | Where SPP differs, honestly |
|---|---|---|
| **Medidata + PBI** | 42,000 trials / 13M patients **fitted**; PBI validated over 4,000+ activities **with direct patient input**; USDM digitisation; 2,300 customers; SOC2-grade procurement | SPP is **reproducible to the bit, seeded, event-sourced, offline, MIT**. Medidata is a cloud black box on proprietary data: you cannot re-run its answer, audit its hazard, or air-gap it. SPP does **criterion-level Shapley** ("this line cost these people"); Medidata emits a protocol-level burden *index* and a risk ranking. SPP has cited in-character interviews; Medidata has real advocates in workshops |
| **QuantHealth** | ~$70M, 8× sales growth, Sanofi/Pfizer/Lilly logos, ISO/SOC2, a 350M-life moat, its own KG | SPP's graph is *small and owned*, which is what permits constrained decoding and mechanical citation checking. QuantHealth's optimiser is a recommender over a proprietary model; SPP's is an auditable engine. But QuantHealth has the thing SPP fundamentally lacks: **real patient-level data** |
| **Prognica** | Same pitch, same honesty, plus 19 agents, distributions, power-under-simulation, budget sensitivity, **$300K–5M pricing** | SPP has ~1,000 tests and a real deterministic engine vs a build-time demo; **exact** Shapley vs a cost/protection ratio; constrained-decoding citations vs RAG narrative. **Neither has fitted priors** |

**Where SPP is inferior, bluntly `[I]`:** ① every number it produces is unfitted — *a seeded simulation of wrong priors is precisely wrong, reproducibly, and fast, and reproducibility is not correctness*; ② no procurement story (no SOC 2, no ISO, no 21 CFR Part 11, no validation package — GxP validation alone runs **$100K–$500K with 15–25% annual maintenance** `[M]` https://checkthat.ai/brands/veeva-systems/pricing); ③ the Shapley claim is weaker than the literature's, since Trial Pathfinder attributed criteria on *real* outcomes and SPP attributes them in a synthetic world — a downgrade in evidentiary weight dressed as an upgrade in granularity; ④ the narration layer inherits every documented LLM validity failure (§5); ⑤ distribution.

## 3. Regulation: what actually exists

**`[M]` The real anchors:**

| Instrument | Status |
|---|---|
| **ICH M15, General Principles for MIDD** | **Step 4 adopted 29 Jan 2026**; FDA availability notice 3 Jun 2026; EMA Step 5. Harmonised framework for assessing MIDD evidence + an assessment-table template — https://database.ich.org/sites/default/files/ICH_M15_Step4_Final_Guideline_2026_0129.pdf · https://www.federalregister.gov/documents/2026-06-03/2026-11112/ |
| **FDA CM&S credibility guidance (devices)** | **Final, 17 Nov 2023** — the basis of VICTRE and HeartFlow-type submissions — https://fda.gov/media/175363/download |
| **FDA AI draft guidance (drugs/biologics)** | **Draft, Jan 2025** — credibility tied to **context of use** — https://www.fda.gov/media/167973/download |
| **FDA/EMA "Guiding Principles of Good AI Practice"** | **Jan 2026**, joint — https://www.fda.gov/about-fda/artificial-intelligence-drug-development/guiding-principles-good-ai-practice-drug-development |
| **EMA QoNM** | Voluntary pathway; **PROCOVA qualification opinion final Sept 2022**; the only precedent for an ML trial-design method being qualified — and it qualifies a *Level-1 prognostic adjustment*, not a synthetic trial — https://www.ema.europa.eu/en/documents/regulatory-procedural-guideline/qualification-opinion-prognostic-covariate-adjustment-procovatm_en.pdf |
| **FDA externally-controlled-trials guidance** | Sponsors must **finalise the protocol before initiating**, including ECA selection and analysis — https://www.fda.gov/media/164960/download |
| **EU MDR simplification proposal** | **Dec 2025**, explicitly referencing in-silico — https://www.p05.org/in-silico-development-in-the-medical-device-industry/ |
| **FDA single-trial default / "plausible mechanism"** | Makary & Prasad, *NEJM* 18 Feb 2026; real-time-trials pilot (AstraZeneca, Amgen); RFI docket closed 24 Nov 2026 |
| **NICE PMG36** | Demands *"full documentation and justification of structural assumptions and data inputs"* — https://www.nice.org.uk/process/pmg36/chapter/economic-evaluation-2 |

**`[M]` The framework that places SPP precisely.** An AbbVie biostatistician's Nov 2026 paper (arXiv 2611.10888) sorts clinical digital twins into five levels by how much of the (X, T, Y) trial data matrix is model-generated, and puts SPP's approach at **Level 5 — "fully synthetic patients and responses: can the trial be rehearsed in silico before enrollment?"** Its findings:

- *"As the share of model-generated information increases, the inferential weight placed on the model grows and **regulatory maturity generally declines**."*
- Level-5 guardrail: *"The rehearsal is only as good as its assumptions. Errors in ĝ and f̂ **compound**, so the generators should be **validated against real data** and the conclusions tested for sensitivity to misspecification."*
- Verdict: *"**Level 5 is most useful today for early exploration and Phase 2–3 design; regulatory use is context-specific.**"*
- Credibility should scale with **model influence × decision consequence**; four recurring questions: drift/transportability, estimand alignment (ICH E9(R1)), compounding error, data quality/provenance.
- **"Bottlenecks are data and validation, not compute"** — despite NVIDIA–Lilly's up-to-$1B investment (Jan 2026) and Roche's 3,500+ Blackwell GPUs (Mar 2026): *"such capacity… makes the workflow feasible but does not establish clinical validity."*
- Contrast: Level 1 (PROCOVA) is the only qualified level because *"randomization and observed outcomes anchor the inference… a poorly predictive score costs efficiency but not validity."*

→ https://arxiv.org/html/2611.10888v1

**`[I]` Read this as a licence and a boundary.** The Level-5 guardrail names exactly two obligations: validate the generators against real data, and test conclusions for sensitivity to misspecification. SPP already has the second (sensitivity analysis over the ledger, CRN-paired flips, `sign_is_stable()`). **It has a pre-registered plan for the first and no implementation.** So the plan's Goal 2 is not a nice-to-have; it is the regulator-facing obligation the field's own framework states, and the one thing that makes "not regulatory evidence" a chosen boundary rather than an unmet requirement.

### 3.1 What it costs to be more than ideation

**`[M]` Measured proxies:** Unlearn needed **>2.5 years and >$130M** to obtain **one** EMA qualification opinion, for a Level-1 method. HeartFlow needed **~15 years, 625+ peer-reviewed publications, a $364M IPO at ~$2.8B, ~$176M FY2025 revenue, and is still loss-making** — for a *diagnostic*, with a reimbursement code as the payoff (FFRCT = 98% of revenue as of 31 Dec 2025; 400,000+ patients assessed) → https://www.sec.gov/Archives/edgar/data/1464521/000146452126000042/htfl-20251231x10k.htm. ARPA-H funds institutional digital-twin work at **up to $38M over 5 years, milestone-gated, explicitly requiring computational validation in the first three years before any clinical trial** (UVM CIRCLE/ReSCUED, Oct 2026) → https://www.healthcareitnews.com/news/arpa-h-awards-uvm-38m-icu-digital-twin-ai · https://arpa-h.gov/explore-funding/awards/4722, and **$19M** to Northeastern (UPGRADE). EMA QoNM is described by applicants as complex with "substantial challenges" → https://www.valueinhealthjournal.com/article/S1098-3015(24)04490-5/fulltext

**`[I]` Judgement:** one context of use, one method: **$5M–$30M and 2–5 years**, with material probability of ending at a letter of support rather than a qualification. For a one-person MIT project this is not a reachable bar and attempting it is the wrong move.

### 3.2 Is "not regulatory evidence" a shield or a cage?

**Both — and which one it is depends entirely on whether the priors get fitted.**

**Shield, genuinely `[I]`:** it removes SPP from the Part 11 / M15 assessment-table / QoNM treadmill; it makes the tool purchasable as *software* rather than *evidence* (a faster procurement); it inoculates against the category's biggest failure mode (overclaiming); and it is the **same line both closest analogues chose** — InSilicoTrial_MAS and Prognica, verbatim above. Choosing it puts SPP in correct company.

**Cage, also genuinely `[I]`:** the moment the deliverable is *"drop this criterion, it costs you 18K patients"*, the buyer is asked to make a decision with money and patient safety attached, and absent regulatory standing the output is **advocable, not decisive** — input to a committee that can be overridden by its own real screen-fail data. Level-5 tools that can't be adjudicated get demoted to slideware.

**`[I]` The uncomfortable read:** today the framing is partly a **euphemism for the absence of validation**, and owners should assume sophisticated buyers notice. It becomes a true shield only if SPP either (a) fits its priors to real data — converting "unfitted guess, reproducibly" into "validated estimate, reproducibly", which is the actual moat — or (b) retreats deliberately into niches where evidentiary weight is not the product: design consensus, protocol communication, auditability.

**`[I]` Who pays for auditability at Level 5:** internal protocol-review documentation and amendment defence; medico-legal/label-defence trails; academic and HTA transparency (NICE PMG36); air-gapped or data-sovereign sponsors (EU/Japan/China systems that cannot send protocols to a US cloud); and **medical devices**, where FDA's 2023 CM&S guidance genuinely applies and in-silico evidence has real precedent (VICTRE's ~3,000 free digital breast models with FDA analysis in *PLOS Computational Biology*; orally-inhaled generic bio-waivers → https://www.fda.gov/media/187992/download). **The device lane is the one place "reproducible, offline, auditable" is a compliance asset rather than a philosophical preference.**

## 4. Who pays, and how much

### 4.1 The pain, priced `[M]`

| Cost | Figure | Source |
|---|---|---|
| Phase II substantial amendment | **$141,000** median | https://pubmed.ncbi.nlm.nih.gov/30227022/ |
| Phase III substantial amendment | **$535,000**; up to ~3 months delay, up to ~$1M unplanned | same · https://wcgclinical.com/insights/navigating-protocol-amendments-understanding-the-growing-burden |
| Mean cost per amendment | **$453,932**; **76%** of trials now amend (57% in 2015) | https://appliedclinicaltrials.com/view/protocol-amendments-costly-solution |
| **Per screen failure** | **$3,500–$7,200** | https://clinitiative.com/research-briefs/protocol-complexity-screen-failure |
| Screen-failure rate | **>50%** of screened patients fail in an audit of 15 randomised oncology studies; 21–26% across three cancer centres | https://clinicalfuture.substack.com/p/the-screening-failure-problem · https://antidote.me/blog/why-are-so-many-referrals-lost-before-screening-really-begins |
| Dropout | **~30%** drop out; **replacing one costs ~$19,533**; **~80%** of trials miss initial enrolment timelines | https://woodleytrialsolutions.com/news/how-to-reduce-costly-delays-in-clinical-trials |
| Per day of delay | **~$40,000** direct (Phase III ~$55,716); **~$800,000/day** unrealised prescription sales (Tufts CSDD 2024, 645 approvals) | https://csdd.tufts.edu/sites/default/files/2025-02/Aug2024%20Day%20of%20Delay%20White%20Paper%20Final.pdf |
| Per randomised patient | **$59,500**; pivotal median **$48M per approved drug** (IQR $20M–$102M) | https://www.cell.com/iscience/fulltext/S2589-0042(23)02666-4 · https://pmc.ncbi.nlm.nih.gov/articles/PMC7295430/ |

**`[I]` The ROI argument, which is stronger than any regulatory argument:** one avoided Phase III amendment ($535K) or ~70 avoided screen failures ($245K–$500K) pays for a decade of a $25K–$75K subscription. **The tool does not need to be right in evidentiary terms to be rational in economic terms.** It also names the buyer: whoever owns the amendment and screen-failure budgets — **ClinOps / trial design / study startup at mid-size biotech**, not regulatory affairs.

### 4.2 What comparable software costs `[M]`

| Tier | Signal |
|---|---|
| Enterprise clinical platform | Veeva FY2026 revenue **$3,195.3M**, 1,552 customers; median ACV **$188,460–$211,872** (range $90,720–$501,612); Vault Clinical $500–$2,400/user/yr; 50–100-user year-1 TCO $514K–$2.2M — https://ir.veeva.com/news/news-details/2026/Veeva-Announces-Fourth-Quarter-and-Fiscal-Year-2026-Results/default.aspx · https://www.vendr.com/marketplace/veeva-systems |
| Per-study EDC | $10K (Phase I/academic) → $50K (mid) → $150K–$500K+ (global Phase III) — https://www.clincapture.com/edc-software-cost-in-2026/ |
| Pharmacometrics seats | Certara max **~$41,000** — https://vendr.com/buyer-guides/certara |
| Services-led | Prognica **$300K–5M across multiple years** |
| Micro-SaaS, same job | TrialVibe **pay per budget, from $25** — https://www.trialvibe.com/ |
| Persona-research SaaS | Synthetic Users **from $12,500/yr** (unlimited seats, $40–63/interview); Yabble from under $800/month; Heatseeker from $55,000/yr; Lakmoos €10,000 pilot; Aaru ~$0.08/simulation; Atypica from $20/month |
| Independent pharma consultants | **$200–$300/hr** solo R&D, **$350/hr** ClinOps contract; medians $150–$200/hr |
| Med-ed per-seat | Shadow Health **$99/student lifetime** |

### 4.3 Buyer personas, ranked `[I]`

| Persona | Budget line | Deal size | Verdict |
|---|---|---|---|
| **Mid-size biotech ClinOps / study-startup / trial design** | amendment + screen-failure budgets | $25–75K/yr, or $15–50K per protocol review | **Best first buyer.** Buys software, not evidence. Fast procurement, attributable pain, reproducibility is a real differentiator vs Medidata |
| **Medical-device sponsors** | CM&S credibility pathway is *real* here | $50–300K | The **only** segment where reproducible/offline/auditable is a compliance asset. Highest value, most underserved |
| **CROs** (feasibility / design-consensus units) | billable model | $50–250K/yr or rev-share | Real, but they want to white-label and own the priors. Slow. Also the lane Medidata bundles away |
| **Med-ed** (nursing, USMLE/NCLEX) | market simulation **$1.9B (2025) → $6.7B (2033)**; virtual-patient simulation **$900M → $2.55B** | $50–300/student/yr institutional | Architecture maps cleanly (LLM virtual patient + fact graph + citations *is* a graded virtual patient) and there is a **proven exit path** (i-Human → Kaplan 2018; Shadow Health → Elsevier Dec 2020). But the buyer wants assessment and clinical reasoning, not protocol attribution — a separate product |
| **Payers / HTA** | NICE PMG36 documentation duty | tender-shaped, unpredictable | Long cycle, low return, high reputational leverage |
| **Patient-advocacy orgs** | do fund R&D (PCORI engagement awards, Novartis publishes PO funding) | $5–50K grants, sporadic | Sympathetic, broke, slow. **Not a revenue base**; good for a named-fiduciary narrative |
| **Health-system experience design / insurance / HR** | — | — | **Thin.** Searched specifically and found **no evidence of persona simulation as a purchased category**. Do not build a plan on it |

### 4.4 Non-dilutive money `[M]`

| Programme | Amount |
|---|---|
| **NIH SBIR/STTR Phase I** | **up to $306,872** (6–12 mo); SBA guideline $323,090; **NINDS up to $700K**; NIA up to $300K or $500K for Alzheimer's — https://beta.nih.gov/programs/small-business-programs/project-structure · https://sbir.org/nih/nih-sbir-program-faqs |
| **Phase II** | **up to $2,045,816** (2 yr); SBA guideline $2,153,927; NINDS $3M |
| TABA | $6,500 Phase I / **$50,000** Phase II — https://grants.nih.gov/grants/guide/notice-files/NOT-OD-26-075.html |
| **EIC Accelerator 2026** | **up to €2.5M grant** + €1–10M EIC Fund equity; grant-only route available. Deadline **4 Nov 2026**; 35 selected 16 Nov 2026; 38 in June 2026 totalling €90M — https://eic.ec.europa.eu/news/european-innovation-council-selects-35-deep-tech-companies-its-accelerator-support-2026-11-16_en |
| **Wellcome** | Early-Career Awards ~£400K; Innovator Awards: Digital Technologies (2026) |
| **ARPA-H** | $19M–$38M, but institutional and milestone-gated — not a lone OSS maintainer |

**`[I]` Grant read:** **SBIR Phase I ($300–700K) is the single best fit** — non-dilutive, no equity, and it funds exactly the thing SPP lacks (fitting priors to real data via a data partnership). It requires US small-business status and a real commercialisation plan, which is a commitment. **EIC Accelerator grant-only (€2.5M)** is the best non-US route.

### 4.5 VC appetite 2025–26: bifurcating `[M]`

- **Digital health venture activity is at a decade low in deal count: 228 deals in Q2 2026, −36% QoQ**, two-thirds below the 688-deal peak; total quarterly equity **−24% QoQ to $5.7B**, concentrating into mega-rounds (Isomorphic Labs' $2.1B). *"Investors are backing drastically fewer digital health startups, pulling back from broad early-stage bets."* → https://hitconsultant.net/2026-07-30/cb-insights-q2-2026-state-of-digital-health-report/
- **Median sizes rising:** seed **$3.0–3.3M** regardless of sector; companies that reached Series A had raised **$4.0–7.0M** seed → https://www.jpmorgan.com/content/dam/jpmorgan/documents/cb/insights/banking/commercial-banking/cb-insights-banking-startup-insights-report-h1-2026.pdf
- **The persona-simulation lane is the exception — it is overheated:** **Simile** $100M Series A (Feb 2026, Index Ventures, with Bain Capital Ventures, Fei-Fei Li, Andrej Karpathy) then **$200M at $2B (Jul 2026, Greenoaks)**; **Aaru** $50M+ Series A (Dec 2025, Redpoint; $1B *headline*, **ARR under $10M**, Accenture invested Mar 2025); **Listen Labs** $69M Series B at $500M (Jan 2026) then **Salesforce agreed to acquire, ~$2B reported** (Sep 2026); **Conveo** $50M (Sep 2026); **Outset** $51M; **Strella** $18M (Bessemer, Oct 2025); **Keplar** $3.4M (Kleiner Perkins); **Artificial Societies** ~$4.9M (Point72 Ventures, YC W25); **Fairgen** $8M.
- **Fund formation is not the constraint:** Bessemer closed **$5.75B** in one raise ($1.75B seed/early, $4B growth).
- **a16z's stated bio-health thesis is pointedly not this:** *"AI will have the greatest impact on life sciences and health when it can succeed at specialist tasks like diagnoses and medical procedures."* → https://a16z.com/ai-at-the-intersection-the-a16z-investment-thesis-on-ai-in-bio-health/

**`[I]` VC read:** the money is in *generic* behavioural simulation for marketing/product decisions and in *real-human* AI interviewing — **not** clinical trial design, which gets funded as biosimulation/pharmacometrics at far lower multiples. Note what Simile is buying: **panel-scale real human interview data** (a Gallup partnership, two-hour interviews per person) — the opposite of SPP's small-owned-graph approach. **A solo maintainer with MIT code, no revenue and unfitted priors is not fundable in the 2026 clinical market.** Plan accordingly rather than hoping.

## 5. The demand science — read this before pitching "interview a patient"

| Finding | Source `[M]` |
|---|---|
| **Pew Research Center, 30 Sep 2026 — the largest independent test.** ~300 questions, 3 replicated waves (Claude Opus 4.6, extended profile + expert reflection): **average absolute error 12.4 pp**; **>15 pp on ~28% of questions**; individual answers differing by 20/30/40+ points. Worst subgroups: Republicans 16.1pp, Black adults 15.1, Hispanic 13.9. **Nearly half the questions had at least one answer choice no AI respondent selected.** Stereotype pile-on: 97% of Hispanic adults "follow the World Cup" (actual 43%); 95% of Republicans favourable to Israel (58%); 86% of Democrats think billionaires are bad (45%). Knowledge inflated: First Amendment correct-answer rate **52% human vs 98% synthetic**; NATO 56% vs 99%. Humans chose "not sure" **~4× more often**. **Model choice changes the answer** — GPT-5.1 described a more extreme public, Claude Opus 4.6 a more middle-of-road one: *"A reader of either result would be misled, but in different directions."* Verdict: *"AI polling is not a replacement for rigorously surveying real humans… these results differ in ways that are often unpredictable."* | https://www.pewresearch.org/data-labs/2026-09-30/can-ai-stand-in-for-human-survey-takers-not-really/ |
| **Bisbee et al., *Political Analysis* 2024** — synthetic means looked plausible but **variance was drastically too small**, subgroups distorted, and **several regression coefficients came out wrong-signed** ("the kind of error that reverses a business decision"); no agreed accuracy standard; results shift with prompt wording and, over three months, with the model | https://www.cambridge.org/core/journals/political-analysis/article/synthetic-replacements-for-human-survey-data-the-perils-of-large-language-models/B92267DC26195C7F36E63EA04A47D2FE |
| **Park et al. 2024 (Stanford), "Generative Agent Simulations of 1,000 People"** — the optimistic anchor *and* its catch: agents built from **two-hour interviews with 1,052 real individuals** matched people's own GSS answers **83–86%** as well as the people matched themselves two weeks later, vs **74%** for demographics-only. **The fidelity came from rich per-person real human data — the opposite of "skip the humans."** | https://arxiv.org/abs/2411.10109 · https://hai.stanford.edu/policy/simulating-human-behavior-with-ai-agents |
| **Wang, Morgenstern & Dickerson, *Nature MI*** — LLMs "harmfully misrepresent" demographic groups; identity flattening | https://www.nature.com/articles/s42256-025-00986-z |
| **HBS (Brand, Israeli, Ngwe)** — LLM willingness-to-pay "sometimes comparable… but often inaccurate and in some cases wrong-signed"; **fine-tuning did not fix new categories or between-segment differences**; LLMs are a **supplement, not a substitute** | https://papers.ssrn.com/abstract=4395751 |
| **"Persona Collapse", arXiv 2604.24698** — agents each assigned a distinct profile **converge into a narrow behavioural mode**; LLM responses "cluster into classes, unlike human responses that uniformly fill the entire space" | https://arxiv.org/pdf/2604.24698 |
| **NeurIPS 2025 position paper, "LLM Generated Persona is a Promise with a Catch"** — calls for *"a rigorous and systematic science of persona generation"* | https://papers.neurips.cc/paper_files/paper/2025/file/5fc150b75e8b509735564de16bc3527b-Paper-Position_Paper_Track.pdf |
| Also: **PNAS** on validity of LLM-generated social data (10.1073/pnas.2538145123); **"Six Fallacies in Substituting LLMs for Human Participants"** (2025); **"AI cannot replace human participants in behavioral research"** (PNAS 2026); **Prolific** — directional/exploratory use only, and increased persona fidelity **did not close the gap**; **CMU 2025** on ethical concerns; **CHI 2025 "Simulacrum of Stories"** (19 qualitative researchers) | linked in method file |
| **Industry bodies converge on "augment, don't replace":** ICC/ESOMAR Code 2025 defines a person distinctly from *"a synthetic, virtual/digitally created persona or entity"* and requires synthetic personas be clearly notified; Bain; NIQ ("trustable only when the supplier has data validating accuracy"); GreenBook/IDX; MRS; Kantar | https://standards.esomar.org/assets/documents/icc-esomar-code-2025.pdf · https://nielseniq.com/global/en/insights/education/2024/the-rise-of-synthetic-respondents/ |
| **The counter-market is real:** **Roundtable** started with synthetic humans and **pivoted to "Proof of Human" bot-detection**, claiming up to ~30% of B2B survey responses can be AI-generated; **NN/g** and **MeasuringU** are openly sceptical of synthetic users for critical decisions | https://roundtable.ai · https://www.nngroup.com/articles/synthetic-users/ |
| **Vendor self-validation, best available:** Aaru reports 2,993 questions, mean TVD 7.62%, MAE 3.53% (Sep 2026) — self-reported, not peer-reviewed, but the most specific accuracy number any vendor has offered, and **better than Pew's 12pp**. The discrepancy is unresolved | https://aaru.com/publications/population-simulation-at-the-replication-floor-research |
| **Incumbent demand signal:** Qualtrics' 2025 survey — **71% of researchers agreed synthetic responses will exceed half of data collection within three years** (vendor-sponsored, directionally telling). Medidata's 2026 State of AI claims **90.5% of organisations use or plan to use AI for protocol design and optimisation** (vendor-published) | https://www.qualtrics.com/articles/news/ai-to-drive-massive-changes-to-market-research-in-2025-qualtrics-report-says/ |

### 5.1 What this means for SPP specifically `[I]`

1. **SPP's citation constraint answers *fabrication*, and only *fabrication*.** Constrained decoding makes an invented `F999` ungrammatical. It does nothing for variance collapse, persona collapse, subgroup distortion, wrong-signed relationships, or the stereotype pile-on — and it may make variance collapse **worse** by narrowing the response space further. Be precise about this in the pitch, because a technical evaluator will ask.
2. **The deterministic core is the stronger defence and it is undersold.** Pew's killer finding is *"the model you use can change the answers you get."* SPP's architecture forbids the LLM from making decisions at all — the event-sourced engine decides, the LLM only speaks — so a model swap changes the words and not a single outcome. That is **structural immunity to the model-swap criticism**, and it is the one claim in §5 that SPP can make without hedging.
3. **So the honest product claim is not "interview a synthetic patient."** It is *"interview a persona whose every assertion is traceable to a stated assumption, so a room full of stakeholders argues about the assumption instead of the anecdote."* That is a **design-consensus and communication** product and it survives every criticism above. The moment it is sold as "patient insight", Pew and Bisbee apply and SPP loses.
4. **Non-pharma demand outside consumer/policy/UX research is thin,** and I searched for it specifically. Note **FishDog** sells "medical panels" from ~340,000 synthetic Americans built from US Census/ACS microdata — a non-clinical vendor reaching into SPP's adjacency **from below, with census grounding SPP doesn't have** → https://fish.dog/about

## 6. Monetisation

### 6.1 Structural facts

**`[M]` MIT already gives away everything except trademark, support and speed.** Every relicensor (MongoDB 2018, Elastic 2021, HashiCorp 2023, Redis 2024, Sentry, Cockroach, Confluent, MariaDB, n8n) spawned a community fork or OSI alternative; Elastic and Redis **reverted** by adding AGPLv3 back. → https://opensourcelicenserisk.com/research/state-of-relicensing-exposure-2026/

**`[I]` The fork threat is inverted here.** SPP's risk is not AWS forking it; it is Medidata/QuantHealth shipping the same features atop a data moat SPP cannot fork. **Relicensing protects against the wrong enemy. The defensible asset is the fitted prior corpus + citation graph + validation evidence, not the code.**

### 6.2 Model by model

| Model | Precedent `[M]` | Ceiling for SPP | Verdict `[I]` |
|---|---|---|---|
| **Open-core + hosted SaaS** | **GrowthBook** — MIT core, open-core enterprise tier in the same image, **8,610 stars**, **$23.1M raised**, $22.6M Series A (Jun 2025, Nava), "3,000+ companies" | **$0.5–3M ARR** solo; ~$20M with a team | **Best structural fit.** Charge for fitted packs, the hosted/versioned/air-gap runtime with per-run audit exports, the citation corpus. Sells what buyers can't self-host |
| **Per-seat enterprise SaaS** | Veeva $188–212K median ACV; Certara ~$41K seat | $25–75K/yr per sponsor | Works, but needs SOC2/Part 11 posture SPP lacks; $100–500K to reach |
| **Domain-pack marketplace** | UK Biobank charges only **cost-recovery** (£500 student tier, £40 starter credit); Truveta/Flatiron/IQVIA monetise patient-level data SPP doesn't have | $5–50K/condition/yr; low-six-figure ceiling | **Weak as a business, strong as a moat.** Literature packs are reproducible by anyone; packs only command money if fitted to licensed data. And a two-sided market needs two people |
| **Services / consulting** | **PyMC Labs** ("core libraries free"), Physiomics, Metrum; pharma independents $200–350/hr | **$250–600K/yr solo** (billable-hours ceiling), non-scalable | **Highest immediate cash, lowest friction.** The tool is the differentiator; the invoice is the analysis. How the closest methodological peers actually monetise |
| **Benchmark / dataset play** | **LMArena**: OSS Berkeley → $100M seed (a16z + UC) → **$1.7B four months after product launch** → **$100M ARR nine months after commercial launch**. But Synthea, VICTRE, MIMIC/PhysioNet: widely used, **zero revenue**, grant-funded | $0–500K/yr + reputational optionality | **Only works with an urgent referee role.** Frontier labs needed a referee for model choice; trial-design teams don't urgently need referees for each other, and there's no crowd to supply votes. A trial-design benchmark is a **public good**, not a business — and a very good one |
| **Dual / non-commercial licence** | Elastic/HashiCorp/Redis pattern | marginal | Adds friction for the academics who are SPP's only current distribution channel |
| **Trade sale / acqui-hire** | **Lixoft → $6M cash**; **Yabble → ~£4.5M**; **Gretel → NVIDIA >$320M** (30–40 people); Datagen shut after $70M; Synthesis AI shut/absorbed at $17M; i-Human → Kaplan; Shadow Health → Elsevier; **Streamlit → Snowflake $650.8M recorded / ~$800M reported**; W&B → CoreWeave ~$1.4B est. | **$1–10M** if a strategic wants the citation/reproducibility layer | **The realistic exit shape.** Bimodal: $4.5–6M capability tuck-ins vs $320M–1.7B for teams with revenue and scale. SPP is in the first cluster **unless it acquires data** |

### 6.3 The two that fit a solo maintainer `[I]`

**#1 — Wind-tunnel-as-a-service (PyMC Labs / Physiomics shape).** Sell the *analysis*, not the licence: a protocol review returning a reproducible flip table, per-criterion attribution and a burden-ranked amendment-risk memo, at **$15–50K per protocol** or a **$5–15K/month retainer**. Zero procurement friction, zero regulatory burden, immediate cash, and it **generates the case studies #2 needs**. Ceiling ~$300–600K/yr for one person. Also the only model where "not regulatory evidence" costs nothing, because you're selling an opinion, not a system of record.

**#2 — Open-core with a fitted-prior + citation subscription (GrowthBook shape).** Core engine, event sourcing, CRN pairing, Shapley and the narration constraint layer stay MIT and readable. Charge for (a) **fitted** prior packs — the thing that converts Level 5 from "rehearsal" to "estimate"; (b) the hosted, versioned, air-gap-capable runtime with per-run audit exports; (c) the citation corpus with provenance. Anchor **$25–75K/yr** (above Yabble's <$800/mo, near Certara's ~$41K seat, far below Veeva's $188K ACV). 10–30 ClinOps/design-consensus accounts → **$0.5–2M ARR**. Solo-sustainable to ~$1M; beyond that needs a data-licensing partner and an engineer.

**Sequencing `[I]`:** #1 first (cash + evidence + named protocols), #2 second (productise what you repeated), grants in parallel (SBIR Phase I to fund the prior-fitting — the only durable moat). **Do not chase a marketplace, a benchmark-as-business, or relicensing.**

## 7. Adjacent proof points: what it actually took

### 7.1 Deterministic simulation → large business: decades, people, a general engine `[M]`

| Case | Outcome | What it took |
|---|---|---|
| **ESI Group** | → **Keysight, ~€1.15B** (Jun 2023) | ~40 years, ~700 people, automotive/aerospace breadth |
| **COMSOL** | ~$109–112M revenue, ~600 employees, private, founded 1986 | 39 years, general-purpose multiphysics |
| **Schrödinger** | FY2025 **$255.9M total, $199.5M software**, 74% software GM, positive adj EBITDA targeted by YE2028 | 25 years, **>$1B raised**, physics engine + drug-discovery services |
| **Certara** | **$418.8M FY2025, $134.5M adj EBITDA** | Built **by acquisition**, not organically; PBPK became a *standard* because **regulators named it** |
| **Simulations Plus** | $79.2M FY2025, **$45.8M software**, 28% adj EBITDA margin, FY2026 guidance **0–4% growth** | Public, profitable and **flat** — the honest ceiling for clinical simulation software |
| **HeartFlow** | $364M IPO at ~$2.8B, ~$176M FY2025, **still loss-making** | ~15 years, **625+ publications**, a reimbursement code, FDA clearance |

**`[I]` Pattern:** deterministic simulation becomes a *large* business only when (a) the engine is general-purpose, (b) it took 25–40 years, and (c) usually a **regulator or a reimbursement code names it the standard**. SPP's engine is one workflow, one person, explicitly not regulatory. On this evidence **SPP-as-a-large-business is not a live path**, and any plan built on it is a fantasy.

### 7.2 Small rigorous OSS → real outcome: the honest ledger `[M]`

| Case | Outcome | Lesson |
|---|---|---|
| **Streamlit** | → Snowflake, **$650.8M recorded**; 3-person team | Best-case OSS: a *general-purpose developer primitive* bought for **distribution**, not code. SPP is a vertical workflow — structurally harder |
| **W&B** | → CoreWeave, completed 5 May 2025, ~$1.4B est. | Infrastructure-scale workflow lock-in |
| **LMArena** | Berkeley OSS → **$1.7B in 4 months**, **$100M ARR in 9** | The benchmark play works — but only because frontier labs needed a **neutral referee** and millions supplied votes |
| **GrowthBook** | MIT core, 8,610 stars, $23.1M raised, 3,000+ companies | **SPP's best structural template** for MIT-core + enterprise edge |
| **Synthea** | 3,470 stars, 10 years, Digital Public Good, grant-funded, **no revenue** | **The null result, in SPP's exact category** |
| **Trial Pathfinder** | *Nature* 2021 + MIT on PyPI → **69 stars, abandoned Jan 2022** | **Most damning datum available.** Publishing the method in *Nature* did not produce adoption. Prestige ≠ distribution |
| **InSilicoTrial_MAS** | MIT, solo, 240 tests, same disclaimers → **0 stars in ~6 weeks** | SPP's twin, independently converged, going nowhere |
| **PyMC → PyMC Labs** | OSS core, consulting as the business | **The sustainable solo/small-team shape** |
| **Posit (RStudio)** | OSS → PBC, never sold | The shape where the OSS *is* the moat; needs founder appetite |
| **Lixoft / Yabble** | **$6M cash** / **~£4.5M** | **The floor**: rigorous niche scientific software exits for single-digit millions |
| **i-Human → Kaplan; Shadow Health → Elsevier** | — | Med-ed virtual patients have a **real, repeated exit path** to publishers — the one adjacent lane with a proven buyer |

**`[I]` Distilled.** The OSS projects that became something shared one of: (1) a general-purpose primitive with explosive developer adoption (Streamlit, GrowthBook, W&B); (2) a **referee/benchmark role with urgent demand and a crowd to feed it** (LMArena); (3) a **named standard conferred by a regulator** (Certara/Simcyp, HeartFlow's code, VICTRE); (4) a **publisher/incumbent buying capability** (Kaplan, Elsevier, YouGov, Snowflake, Keysight).

SPP has none today. It has (2)-shaped *aesthetics* without a referee role, and it could plausibly reach (4). It structurally cannot reach (1) — it is a vertical workflow — and reaching (3) costs $5–30M and 2–5 years.

**`[I]` Therefore the highest-return move is not more engineering.** It is (a) fit the priors to real data through one licensed partnership, and (b) **manufacture a referee role**: publish the first reproducible, seeded, benchmarked protocol-wind-tunnel comparison across condition families with per-criterion attribution and open flip tables, positioning SPP as the neutral ground truth the closed platforms cannot claim because their engines are closed. That is the LMArena move adapted — not a leaderboard, a **reproducibility standard** others are measured against. It is also the only strategy in this brief a single maintainer can execute.

## 8. Where the evidence is thin — flagged, not papered over

1. **"FDA 2024 draft guidance on in silico trials" — does not exist** as searched. Real anchors in §3.
2. **Halozee, CyberPharma, inSileco, Emulate-as-software, Dreamlab-in-silico, Protem, Comarch-trial-simulation, Bulb Capital** — unverifiable or misattributed (§2.1).
3. **ASCT position** — not found; ASCPT and ICH are documented.
4. **DARPA PSB / ARO persona-trajectory** — could not verify as named.
5. **Health-system experience design, insurance, HR/employee-experience persona spend** — searched, found **nothing**. Treat as unsupported demand, not an untapped market.
6. **Prognica's traction** — self-labelled build-time illustrations; no verified enterprise deployments.
7. **Medidata's 90.5% and Qualtrics' 71%** are vendor-published. Directional, not independent.
8. **Category market-size reports are low quality and mutually inconsistent:** in-silico clinical trials variously **$3.6B (2024) → $5.6B (2030)** (Grand View), **$3.95B → $6.39B (2033)**, **$8.51B by 2035**; medical simulation **$1.9B → $6.7B**; virtual-patient simulation **$900M → $2.55B**. **Do not put any of these in front of a board.** The audited public-company numbers (Simulations Plus $45.8M software; Certara $418.8M; Schrödinger $198M software ACV) are the honest TAM evidence.
9. **Aaru's self-reported MAE 3.53% vs Pew's 12.4pp** is an unresolved discrepancy — the field is moving fast, and the vendor number may be right about its own narrow claim while Pew is right about the general one.
10. **Conflicting Synthetic Users pricing** ($12,500/yr own page vs ~$2–27/interview third-party). Vendor page used as primary.
11. **The competitor sweep is not exhaustive** — the research node hit a rate limit and worked from primary sources. §2.4's list is what I found, not what exists.

## 9. Bottom line `[I]`, stated plainly

1. **Rewrite the differentiation claim.** The three-part combination isn't unprecedented, it's *un-sold*. "Nobody does this" loses to a 60-second search. Argue instead: *"the closed platforms can't be re-run, audited, or air-gapped; the open ones have no data and no distribution. We are the only one that is reproducible **and** cited."*
2. **The one real gap is data, and the internal evidence for that is stronger than the external.** ~1,000 tests and five releases in eight weeks did not produce a fitted prior; O3 sits at 0.0 while 55.7% of commits went to instrument work; all 51 shipped marginals are `EXPERT_GUESS`. Prognica's admission — *"real screen-fail data needs EHR or claims access we do not have"* — describes SPP's ceiling too. **An SBIR Phase I ($300–700K) or EIC grant-only (€2.5M) to fit priors against one licensed real dataset is the highest-value action available**, and the only thing that converts Level 5 from rehearsal to estimate. (Corrected on review: this claim previously leaned on the §1 negative controls, which are weaker than stated there. It does not need them.)
3. **Keep "not regulatory evidence" — stop treating it as a virtue.** It is correct (the field's own framework puts Level 5 there) and it is a real shield against the treadmill. It is also currently a euphemism for unfitted priors. It earns trust only once the priors are fitted; before then it reads as a hedge.
4. **Monetise consulting-first, product-second.** $15–50K per protocol review now; open-core later at $0.5–2M ARR solo ceiling. Reject the marketplace, the benchmark-as-business, and relicensing.
5. **Realistic terminal outcomes:** (a) **$1–10M capability tuck-in** for the citation-and-reproducibility layer (Lixoft/Yabble shape); (b) **sustainable ~$300–600K/yr consultancy** with a loved OSS core (PyMC Labs shape) — most likely and most livable; (c) **public good, 3,000+ stars, no revenue** (Synthea shape); (d) Streamlit/LMArena scale requires a general-purpose primitive or a manufactured referee role — available only if deliberately built, and it is the one option a solo maintainer can execute without new funding.
6. **The device lane is the underrated opening.** FDA's 2023 CM&S guidance is *final*, in-silico device evidence has precedent (VICTRE, inhaled-generic bio-waivers), the EU MDR Dec 2025 simplification references in-silico, and "reproducible, offline, auditable" is a **compliance asset** there rather than a philosophy. SPP's T2D/COPD/breast-cancer/RA/HF packs are drug-trial shaped; a device-shaped repositioning of the same engine is the one route where the framing and the architecture both pay.
