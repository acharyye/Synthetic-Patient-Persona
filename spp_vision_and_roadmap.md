# Synthetic Persona Platform — Next-Gen Vision & Technical Roadmap

Design/simulation product. Not a medical decision tool, not a regulatory evidence system. Everything below is engineering and product design for stakeholder simulation and scenario stress-testing.

---

## 1. Product vision

**One-line pitch:** A wind tunnel for experience design. Before you run a real study, workflow, or program on real people, you run it against a grounded, explainable synthetic population and see where it breaks.

**The category you're creating:** "Simulation-driven design review." Today teams stress-test *software* with load tests and *UX* with 5-person usability studies. Nobody stress-tests a *protocol/journey/workflow* against a realistic population before committing. That's the gap.

**Three product promises (these are your differentiators — protect them):**

1. **Explainable, not vibes.** Every persona response traces back to profile fields, graph facts, and named heuristics. Competitors doing "LLM roleplay personas" can't show their work. You can. The explainability layer *is* the product.
2. **Population-level + individual-level in one tool.** Zoom from a 5,000-persona attrition funnel down to "why did persona #3412 drop at visit 4" and get a coherent answer at both altitudes.
3. **Offline-first and reproducible.** Same seed → same cohort → same simulation result. This makes it usable in privacy-sensitive orgs (automotive, pharma, gov) and makes results defensible in design reviews.

**Anti-vision (what to refuse to become):** a chatbot skin over GPT that "pretends to be a patient." The moment behavior is just LLM improvisation, you lose reproducibility, explainability, and the enterprise story.

---

## 2. Core architectural principle: simulate with models, narrate with LLMs

This is the single most important design decision.

- **Deterministic simulation core** decides *what happens*: eligibility outcomes, burden accumulation, dropout events, state transitions. Pure Python, seeded RNG, no LLM calls. Fully testable, fully reproducible.
- **LLM narration layer** explains *how it feels*: interview answers, focus-group dialogue, qualitative complaints. The LLM is constrained by the simulation state and graph facts — it verbalizes decisions the core already made; it never makes them.

Consequences:
- Simulations run in seconds on a laptop with zero LLM calls (LLM only needed for interview/panel modes).
- A persona can never "hallucinate" a decision inconsistent with its state.
- You can regression-test the core exactly, and eval the narration layer separately for faithfulness.

---

## 3. Target architecture (modular, offline-first)

```
┌─────────────────────────────────────────────────────────┐
│  Surfaces: Cohort Studio · Scenario Lab · Interview Room │
│            Report Builder · Assumption Ledger UI         │
├─────────────────────────────────────────────────────────┤
│  API layer (FastAPI) — thin, versioned, async jobs       │
├──────────────┬──────────────────┬───────────────────────┤
│ Cohort Engine│ Scenario Engine  │ Persona Agent Runtime  │
│ (generation, │ (rule DSL,       │ (state machine, goals, │
│  correlation,│  burden, events, │  barriers, dropout     │
│  calibration)│  counterfactuals)│  hazard, narration)    │
├──────────────┴──────────────────┴───────────────────────┤
│ Knowledge Layer: typed graph + GraphRAG + provenance     │
├─────────────────────────────────────────────────────────┤
│ Foundation: event store · seeded RNG service ·           │
│ schema registry · assumption ledger · local LLM adapter  │
└─────────────────────────────────────────────────────────┘
```

### 3.1 Foundation layer (build first, everything depends on it)

- **Event-sourced persona state.** A persona is an initial profile + an append-only event log (screened, enrolled, visit_completed, burden_accrued, barrier_triggered, dropped_out). Current state is a fold over events. This gives you replay, time-travel debugging, counterfactual forking, and audit trails for free.
- **Seeded RNG service.** One RNG hierarchy: `master_seed → cohort_seed → persona_seed → event_seed`. Any sub-simulation reproducible in isolation. Log seeds in every output artifact.
- **Schema registry with versioning.** Pydantic models + explicit `schema_version`, migration functions between versions. Cohorts saved a month ago must still load.
- **Assumption ledger.** Every heuristic in the system (adherence model, priors, burden weights, dropout hazards) is a registered, versioned object with: name, formula/params, source ("expert guess" / "published aggregate" / "tuned"), confidence tag, and changelog. Rendered in the UI and stamped into every exported report. This converts your current caveats section from a liability into a feature.
- **Local LLM adapter.** One interface (`generate`, `generate_structured`) with backends: Ollama (llama/qwen local), vLLM, and a null/offline backend returning template-based fallbacks. Structured outputs enforced via JSON schema + retry-with-repair.

### 3.2 Cohort Engine

- **Correlated trait sampling.** Replace independent per-field priors with a dependency structure — a small Bayesian network or Gaussian copula over key fields (age ↔ comorbidity count ↔ medication count ↔ mobility ↔ digital literacy ↔ caregiver support). Independence is the #1 realism killer in synthetic populations; correlation structure is cheap and high-impact.
- **Prior packs.** Priors as data, not code: versioned YAML/JSON bundles per condition/population, loaded through the assumption ledger. Enables community/customer-supplied packs later and makes the domain pluggable (patients today; drivers, employees, customers tomorrow — same engine).
- **Calibration harness.** Given a target marginal distribution (published aggregate stats, customer's own anonymized aggregates), fit prior parameters so simulated marginals match, report divergence (KS distance per field), and record the calibration run in the ledger. Explicitly labeled "distribution matching, not findings."
- **Cohort diffing.** First-class operation: compare two cohorts (different seeds, priors, calibrations) field-by-field. Needed for trust and for the counterfactual story.

### 3.3 Scenario Engine

- **Rule DSL v2.** Keep parsed-not-executed. Extend the safe language with: temporal predicates (`within_last(months=6)`), set operations, missing-data semantics (unknown ≠ false; three-valued logic with an explicit policy), and rule metadata (rationale, owner, tag). Compile to an AST, evaluate against profiles. Property-based tests (Hypothesis) on the parser/evaluator are mandatory.
- **Attrition attribution beyond sole-reason.** Keep sole-reason; add Shapley-style attribution: for each failing persona, marginal contribution of each rule across rule-subset orderings (sampled, not exhaustive). Output: "Rule 7 is responsible for 34% of total attrition; relaxing it alone recovers 210 personas." This is a killer demo.
- **Burden model v2.** Burden as a structured vector, not a scalar: time, travel, procedural discomfort, cognitive load, financial, scheduling friction. Per-event burden accrual over the journey timeline. Persona-specific burden *sensitivity* derived from profile (a working single parent weights scheduling friction 3×). Aggregate score kept for ranking, vector kept for explanation.
- **Timeline simulation.** Scenarios become event schedules (visits, tasks, waiting periods), not just rule sets. The engine walks each persona through the schedule, accruing burden, rolling dropout hazards, triggering barriers. Output: per-persona event logs + population survival curves.
- **Counterfactual lab.** Fork a completed simulation at any point, mutate the scenario (drop visit 3, make visit 5 remote, relax rule 7), replay with identical seeds, diff outcomes. Because of event sourcing + seeded RNG, the diff isolates the *design change* from noise. This is the "wind tunnel" moment — the core product experience.

### 3.4 Persona Agent Runtime

- **Persona = state machine + utility model + narration.**
  - *State machine:* journey stages (unaware → screened → active → completed/dropped) with guarded transitions driven by simulation events.
  - *Goals/constraints/barriers:* explicit typed lists derived from profile at generation time (goal: "manage condition without disrupting work"; constraint: "no car, 40-min transit to site"; barrier: "low trust in institutions"). These feed both the dropout hazard model and the narration prompts.
  - *Dropout hazard:* per-persona hazard function combining accumulated burden vector × sensitivity weights × barrier triggers × adherence trait. Simple discrete-time hazard model; every coefficient lives in the assumption ledger.
- **Grounded narration.** Interview prompt = persona profile + current state + relevant event log slice + graph-retrieved facts + strict instructions ("you may only reference facts in context; if asked something outside your knowledge, say you don't know"). Post-generation faithfulness check: extract claims from the answer, verify each against context, flag/regenerate on violation.
- **Panel mode (differentiator).** Multi-persona focus group: 5–8 personas + a moderator agent discuss a proposed design. Moderator ensures turn-taking and probes disagreements. Output: transcript + auto-extracted themes with persona attribution ("3 of 6 personas flagged travel burden; all three share low mobility + no caregiver"). Nobody else has grounded multi-agent focus groups with per-statement provenance.
- **Longitudinal memory.** Personas remember prior interviews within a project (stored in the event log). Re-interviewing after a design change yields consistent, evolving responses — "evolving agents" delivered concretely.

### 3.5 Knowledge Layer

- **Typed property graph with provenance.** Every node/edge carries `source`, `confidence`, `as_of`. Ontology kept small and owned: Condition, Stage, Treatment, Procedure, Requirement, Barrier, Resource. Resist the urge to ingest a giant external ontology early — a small graph you fully understand beats a big one you don't.
- **GraphRAG v2, retrieval contract.** Retrieval returns `(facts[], paths[], confidence, sources[])` — a typed object, not text soup. Narration cites fact IDs; the UI can render "this answer used facts F12, F17 via path P3." Retrieval quality gets its own eval set (query → expected facts).
- **Graph as constraint source.** The graph doesn't just inform chat — it constrains generation (valid stage/treatment combinations per condition) and rule evaluation (rule references a Procedure node → burden model pulls that procedure's attributes). One knowledge substrate, three consumers.

### 3.6 Analytics & Reporting

- **DuckDB as the analytics substrate.** Event logs → Parquet → DuckDB. Funnels, survival curves, burden distributions, subgroup slices all become SQL. Fast, embedded, offline, zero infra.
- **Standard report artifact.** One exportable report (HTML + PDF) per simulation run: scenario summary, cohort description, attrition funnel with attribution, burden breakdown, survival curves, top persona quotes (with provenance links), full assumption ledger snapshot, seeds. This is what champions forward to their boss — design it like a product, not a printout.
- **Sensitivity analysis.** One-click: perturb each ledger assumption ±X%, re-run, rank assumptions by outcome impact ("results are robust to adherence heuristic; highly sensitive to travel burden weight"). Turns "your heuristics are made up" from an attack into a dashboard.

---

## 4. Technical choices (opinionated)

| Concern | Choice | Why |
|---|---|---|
| Core language | Python 3.12, strict typing, Pydantic v2 | Existing codebase; typing is the API contract for AI-assisted coding |
| Simulation core | Pure functions + event sourcing, no I/O | Testability, replay, counterfactuals |
| RNG | `numpy.random.Generator` hierarchy from named seeds | Reproducibility guarantee |
| Analytics | DuckDB + Parquet | Embedded, offline, fast |
| Graph | Start: NetworkX + SQLite persistence; upgrade path: Kùzu (embedded graph DB) | Offline-first; avoid Neo4j server dependency |
| LLM | Ollama (Qwen2.5/Llama3.x class) via adapter; cloud backend optional and off by default | Offline-first promise |
| API | FastAPI + async job queue (simulations as jobs with progress) | Long-running sims need job semantics |
| Frontend | Single-page app (React/Vite) talking to the API; or start with FastAPI + HTMX if you want to defer frontend complexity | Ship Scenario Lab fast |
| Testing | pytest + Hypothesis (DSL), golden-file regression sims, faithfulness evals for narration | Three distinct test surfaces |
| Packaging | Monorepo, `uv`, one `spp` package with subpackages matching modules above | AI-coding friendly |

---

## 5. Evaluation strategy (three surfaces, tested differently)

1. **Simulation core — exact testing.**
   - Golden scenarios: ~20 canonical (cohort, scenario) pairs with committed expected outputs; any diff is a reviewed change.
   - Property tests: eligibility monotonicity (relaxing a rule never decreases eligible count), burden non-negativity, hazard bounds, event-log fold determinism.
   - Metamorphic tests: doubling cohort size ≈ preserves rates; permuting persona order changes nothing.

2. **Statistical face validity — distribution testing.**
   - Marginals of generated cohorts vs. prior-pack targets (KS distance thresholds in CI).
   - Correlation structure sanity: sign checks on key trait pairs.
   - Calibration harness convergence tests.

3. **Narration layer — faithfulness evals.**
   - Claim-extraction + context-verification pipeline as an automated eval (target: >95% claims grounded).
   - Consistency evals: same question asked 5× to same persona/seed → semantically consistent answers.
   - Persona-coherence rubric scored by LLM-as-judge (does the answer reflect stated goals/barriers?), with a small human-reviewed anchor set to validate the judge.
   - Cross-persona discrimination: answers from personas with different profiles should be distinguishable by a classifier; if not, narration is generic mush.

4. **Product-level regression.** Every release re-runs the golden scenarios + a fixed panel-mode session and diffs the exported reports.

---

## 6. UX direction

Three rooms, one workbench:

- **Cohort Studio.** Configure priors/prior packs, generate, inspect. Persona cards (profile, goals, barriers, provenance of each field), distribution charts, cohort diff view. Aesthetic: instrument panel, not dashboard-template — this tool's credibility is visual.
- **Scenario Lab.** Rule editor with live per-rule attrition preview as you type (this interaction alone sells the product), timeline builder for event schedules, burden heatmap, attribution waterfall, counterfactual fork-and-diff view with side-by-side survival curves.
- **Interview Room.** Chat with a persona (state + cited facts visible in a side panel — every claim clickable to its source), or run panel mode with live transcript and theme extraction.
- **Everywhere:** the assumption ledger is one click away; every number can answer "why?"

Design principle: **provenance is the aesthetic.** The UI should make "grounded and explainable" *visible* — citations, seeds, ledger versions rendered as first-class UI elements, not buried in tooltips.

---

## 7. Phased roadmap

**Phase 0 — Harden the core (1–2 weeks of focused work).**
Foundation layer: event sourcing, seed hierarchy, schema versioning, assumption ledger (backend), LLM adapter with null backend. Port existing eligibility/burden onto it. Golden scenario suite + property tests. *Exit: same seed → byte-identical simulation output; CI green.*

**Phase 1 — Realism (2–3 weeks).**
Correlated sampling (copula/BN), prior packs, goals/constraints/barriers derivation, dropout hazard model, timeline simulation. *Exit: population survival curves that a domain reviewer calls "plausible-shaped," with every coefficient in the ledger.*

**Phase 2 — The wind tunnel (2–3 weeks).**
Counterfactual fork-and-diff, Shapley attrition attribution, burden vector v2, sensitivity analysis. *Exit: the killer demo — change one rule, see recovered personas and shifted survival curve, with attribution.*

**Phase 3 — Grounded voices (2–3 weeks).**
GraphRAG v2 retrieval contract, grounded narration + faithfulness checker, longitudinal memory, panel mode. *Exit: focus-group transcript where every substantive claim links to a fact or event.*

**Phase 4 — Product surface (3–4 weeks).**
Cohort Studio, Scenario Lab, Interview Room, report export, ledger UI. *Exit: a non-engineer runs a full workflow — generate, stress-test, counterfactual, interview, export — without touching the API.*

**Phase 5 — Platform (ongoing).**
Plugin interfaces: prior packs, burden models, hazard models, domain ontologies as pluggable modules. Second domain vertical (e.g., employee-experience or customer-journey personas) as proof the engine is domain-agnostic. Multi-project workspaces, cohort/scenario libraries.

---

## 8. Implementation priorities for an AI-coding workflow

1. **Contracts before code.** Write the Pydantic models, event types, and module interfaces for the full target architecture first (even stubs). AI coding agents perform dramatically better against explicit typed contracts; the schemas *are* the spec.
2. **Vertical slices, not layers.** Each work session = one thin end-to-end slice (e.g., "timeline simulation for one visit type, with one hazard, one golden test") rather than "build the whole hazard module."
3. **CLAUDE.md in the repo** with: architecture map, the simulate/narrate separation rule, seeding conventions, "every heuristic goes through the ledger" rule, test commands, and the golden-test update procedure. This handoff doc's constraints section belongs there.
4. **Tests as guardrails for the agent.** Property + golden tests written early mean the coding agent can refactor aggressively without silent regressions — this is what makes the AI workflow safe on a simulation engine.
5. **Order of build:** Foundation → migrate existing modules onto it → Phase 1+. Resist building panel mode (the fun part) before determinism (the trust part).

## 9. Risks & mitigations

- **Realism theater** (plausible-looking but meaningless outputs) → sensitivity analysis + ledger + explicit confidence tags; never present numbers without their assumption lineage.
- **Scope creep into clinical claims** → the product framing in section 1 plus a hard rule: no module ever outputs "recommendation" language; outputs are "simulated under stated assumptions."
- **LLM dependency creep** → the null backend must always keep core workflows functional; CI runs the full simulation suite with LLM disabled.
- **Graph becomes a swamp** → ontology freeze per release; ingestion only through typed loaders with provenance.
- **One-person maintainability** → embedded everything (SQLite/DuckDB/Kùzu/Ollama), no servers to babysit, monorepo, boring tech.
