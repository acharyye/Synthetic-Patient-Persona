# CLAUDE.md — project context for Claude Code

## What this is
A **Synthetic Patient Persona**: a GraphRAG-grounded, conversational patient
digital twin used for trial-design and patient-journey work. An LLM answers *in
character* as a plausible patient, constrained by (a) a structured **Patient DNA**
profile and (b) facts retrieved from a biomedical **knowledge graph** so it can't
drift into clinically incoherent claims.

**Framing (important):** this is a design/ideation & stakeholder-simulation tool,
NOT regulatory evidence and NOT a statistical virtual-control-arm twin (the
Unlearn.AI / QSP kind). Keep that boundary in code comments and any UI copy.

## Architecture (data flow)
Synthea/MIMIC/registries ─▶ ingest ─▶ **Patient DNA** (Pydantic)
Hetionet/PrimeKG/Open Targets ─▶ ingest ─▶ **Neo4j KG**
Patient DNA + question ─▶ **GraphRAG** (retrieve subgraph + citations)
        ─▶ **Persona engine** (LLM, conditioned + constrained)
        ─▶ **FastAPI**: /persona/interview · /cohort/generate · /protocol/stress-test

## The one architectural rule: simulate with models, narrate with LLMs
The **deterministic core** decides *what happens* — eligibility, burden, dropout,
state transitions. Pure Python, seeded, no LLM calls, fully replayable.
The **narration layer** explains *how it feels* — interview answers, quotes. It
verbalises decisions the core already made and **never makes one**.

If you find yourself wanting an LLM call to change simulation state, the design
has gone wrong. Consequences worth protecting: simulations run in seconds with
zero LLM calls, a persona can't hallucinate a decision inconsistent with its
state, and the core is exactly regression-testable.

## Layout
- `src/spp/foundation/`            — **build on this**: rng, events, ledger, versioning, llm
- `src/spp/assumptions.py`         — every heuristic, registered with source + confidence
- `src/spp/schemas/patient_dna.py` — the Patient DNA schema (the "genome")
- `src/spp/graph/client.py`        — Neo4j wrapper (stubs when offline)
- `src/spp/graph/schema.py`        — KG labels/rel types/metaedges (single source of truth)
- `src/spp/graphrag/`              — retriever + grounding block builder
- `src/spp/graphrag/cypher_guard.py` — validates LLM-written Cypher before execution
- `src/spp/persona/`              — engine + prompt templates
- `src/spp/cohort/generator.py`    — sample N personas across a subpopulation
- `src/spp/cohort/correlation.py`  — Gaussian copula coupling the trait axes
- `src/spp/cohort/traits.py`       — goals/constraints/barriers derivation
- `src/spp/cohort/epidemiology.py` — per-condition priors the sampler draws from
- `src/spp/simulation/`            — schedule, hazard, timeline, survival curves
- `src/spp/protocol/eligibility.py`— criterion DSL + screening/attrition
- `src/spp/protocol/burden.py`     — participation-burden scoring + interviews
- `src/spp/ingest/`               — synthea_loader.py, kg_loader.py
- `src/spp/api/main.py`            — FastAPI surface

## Conventions
- Python 3.11+, Pydantic v2, type hints everywhere.
- Every external dependency (LLM, Neo4j) must degrade to a deterministic stub when
  `SPP_LIVE=false`, so the pipeline always runs offline. Preserve this.
- Grounding is **KG-native** (query the graph), not doc-chunking. Keep citations
  attached to every retrieved fact.

### Seeding
Never call `random`/`np.random` directly in simulation code. Derive a named scope:
```python
cohort = cohort_scope(master_seed, condition)   # foundation/rng.py
person = persona_scope(cohort, index)
gen    = person.generator()
```
Seeds derive by *name*, not draw order, so adding a draw anywhere doesn't shift
everything downstream and a single persona can be re-simulated in isolation.
Stamp `scope.describe()` into any output artifact.

### Every heuristic goes through the ledger
No magic numbers in simulation code. If a coefficient influences an outcome it is
registered in `assumptions.py` with a `source` and a `confidence`, and read from
there. This is what makes sensitivity analysis possible and what lets
`GET /assumptions` tell a reviewer exactly which numbers are judgement
(`LEDGER.unsupported()`) rather than measurement.

### Event sourcing
Persona state is a `fold` over an append-only event log, never stored directly.
The fold is **pure** — no I/O, no clock, no RNG. That purity is what makes
`fork_at()` counterfactuals measure the design change instead of the mechanism.

### Correlation is declared, never inferred — and gated, never repaired
`cohort.trait_correlations` holds **latent Gaussian ρ**, the copula's underlying
parameter. Two rules:

1. **A pair omitted is asserted uncorrelated.** Correlation does not propagate
   through a correlation matrix: declaring a~b and b~c does **not** give you a~c.
   (Zeros imply conditional independence only in the *precision* matrix, which
   this is not.) List every relationship that should exist.
2. **The matrix is gated at load, not projected.** Below `min_eigenvalue` it
   raises `NotPositiveDefinite` naming the axes to revisit. Projection exists but
   is off by default and never silent — it returns exactly which pairs moved and
   by how much, and that must be recorded in `cohort.correlation_psd_gate`. A
   projected matrix no longer matches its specification.

**Attenuation is expected.** ρ=0.45 measures 0.4334 on the uniforms
(`uniform_pearson` = (6/π)·arcsin(ρ/2)) and much lower again through a
categorical or count marginal. So **assert correlations at the latent level**;
asserting a realized value against a latent spec needs a tolerance wide enough to
hide a real mistake.

### Retention numbers are a plausibility target, not a fit
`intercept` and `cumulative_burden_weight` are fitted **jointly** by
`scripts/calibrate_hazard.py` against two anchors (light 4-visit → 93%, heavy
24-visit → 55%). The 12-visit design is **held out** and lands ~81% unfitted —
that is the generalisation evidence. Never fit a per-design intercept shift; if
one design needs its own correction, a slope is wrong.

Known weak identification: the fit drives `cumulative_burden_weight` to ~0.05.
The intensity spread is explained by visit **count** compounding through
survival, not by burden accumulating within a persona, so that term is largely
redundant with `burden_increment_weight`. Separating them needs a third anchor
varying per-visit burden at *fixed* visit count. Do not read the coefficient as
evidence either way.

Only the *difference* between designs is signal. Never quote an absolute
retention figure.

### Persona ids are globally unique — keep them that way
`patient_id` encodes `(condition, cohort_seed, index)`, e.g.
`type-2-diabetes-s42-0007`. It used to be `synthetic-0000`, unique only *within*
a cohort, which made every dict/file/report keyed on it a latent collision — the
compliance eval hit exactly that and silently scored one condition's personas
against another's expected facts. Fixed at the source rather than per-consumer,
so downstream code is correct by construction; ids are URL-safe because Phase 4
turns them into `/persona/{id}` routes. `tests/test_pack_contract.py` asserts
no collisions across conditions or seeds.

### Prior packs are the single source of truth
Population priors live in `data/prior_packs/*.json`, not in code. `CONDITION_EPI`
was migrated there and **removed** — two copies drift. Edit the JSON.

A pack carries marginals (family + params + support), the **full explicit** latent
correlation matrix (packs inherit the no-sparse-specs rule), derivation rules, and
per-entry provenance and tolerance. Deliberately *not* in a pack: hazard anchors
(they're scenario-intensity properties, not population ones) and overlays /
inheritance (flat packs only; base+delta is Phase 5).

Validation runs at load — field coverage, parameter sanity, and the PSD gate — so
a bad pack fails with the eigenvector diagnostic instead of failing downstream in
generation.

Mark `structural_paths` on any field a mechanism outside the copula also touches
(e.g. `comorbidities`, where `comorbidity_age_factor` stacks a causal path on top
of the latent ρ). Without it, the first person to measure realized correlations
files a bug against correct behaviour.

### Two test surfaces, deliberately different
`tests/test_golden.py` pins byte-exact output and **will** churn when the sampler
changes. `tests/test_pack_contract.py` is **generated from pack contents** —
marginals against their own declared tolerance, correlations via the
`uniform_pearson` closed form — and should **not** churn. Never hand-write a
contract assertion that restates a pack number; parametrize over the pack instead,
so adding a pack is adding data and coverage grows itself.

- golden diff + contract green → implementation changed, distribution intact
- golden diff + contract red → the distribution moved; look hard

### Common random numbers — seed by identity, never by position
Every stochastic decision seeds from **stable identity**: a visit's draws come
from `(persona_seed, visit_id)`, and `visit_id` is assigned once and preserved
by every `VisitSchedule` mutation. Never regenerate a visit id from a list index,
and never rebuild a schedule when you meant to mutate one — either would shift
every later draw, so dropping visit 3 would make visit 4 consume visit 3's
randomness and personas would flip for reasons unrelated to the design change.

That pairing is what makes counterfactual diffs low-variance, and it is asserted
in `tests/test_seed_keying.py`: a no-op fork must move nobody, and after dropping
a visit every surviving visit must consume an identical seed. Outcomes may still
change (less accumulated burden is causal); the *draws* may not.

### Counterfactuals report flips, not subtracted aggregates
Because runs are CRN-paired, the primary object is the **flip table** — which
personas changed outcome and at which event their logs diverged. A 2-point
retention delta at N=1000 is inside the noise as two independent runs; as "31
recovered, 11 lost" it is exact. Curves stay as the visual, flips are the number.
`sign_is_stable()` re-runs under a second master seed: if the net flip count does
not keep its sign, it is a draw artifact, not an effect.

Forking is **scenario-level at t=0** only. Mid-trajectory forking is real
machinery for no current use case; event sourcing makes it addable later.

### Attribution is closed-form — never add sampling
Eligibility exclusion is a **veto game**: rules a persona passes are null
players, the rules it fails are symmetric, so each takes exactly `1/|F|`. Summing
that over the cohort is the exact Shapley value in one pass, and `sole_reason` is
the `|F| = 1` special case. Values sum to the number excluded (efficiency), which
is what makes "responsible for 34% of attrition" a real share — so **store it at
full precision and round only for display**; rounding to 4dp breaks efficiency
(1/3 three times is 0.9999).

Dropout attribution is exact for the same reason: the hazard logit is linear, so
each term contributes exactly `weight x value`. If the hazard ever goes
nonlinear, say so loudly rather than quietly switching to sampling.

Sensitivity analysis is the same fork mechanism pointed at the ledger — perturb
one assumption, CRN-paired re-run, rank by flips. A thin loop, not a subsystem.

### Narration is quarantined nondeterminism
Phase 3 introduced the only nondeterministic layer. It is fenced on four sides:

1. **`build_prompt` is pure** — data in, `Prompt` out, no I/O or clock, pinned by
   golden files. Most narration bugs live here and cost nothing to catch.
2. **Model calls go through cassettes** (`narration/cassette.py`): live runs
   record `prompt_fingerprint -> response`, CI replays. Cassettes carry backend +
   model and `require_compatible()` refuses to replay across a model swap. **The
   model is an assumption** (`narration.model` in the ledger) — swapping it
   invalidates cassettes and requires re-running the narration evals.
3. **Citations are a decode constraint, not a prompt instruction.** The model
   emits `{"segments":[{text, kind, fact_ids}]}` under a JSON schema where
   `fact_ids` is an **enum of exactly the retrieved ids** — a fabricated `F999`
   is ungrammatical, not merely detectable. Prose rendering is code
   (`structured.py`). The gate then shrinks to what needs judgement: cited ids
   exist, factual segments are cited, feeling segments exempt. Claim-extraction
   stays an *offline eval*, never a runtime gate. Retry is capped at **one**,
   then `GroundingFailure` is surfaced: a retry loop would hide a model that will
   not ground and turn a measurable compliance rate into an invisible one.
4. **The null backend emits a citation skeleton**, not prose — structured, cited,
   verifiable — so retrieval → prompt → citation gate → event append is CI-tested
   end to end offline. Only the words in between are untested, which is the
   correct boundary.

Interviews append `INTERVIEWED` events, so longitudinal memory is a read over the
persona's own log — no second store, and replay purity extends to narration
inputs for free.

### Cassettes are recordings, not goldens — the record path is gated
Only responses that **pass the citation gate** may persist; failures go to
`<name>.quarantine.json` with their reason and become the compliance dataset. A
recording made from a non-compliant response would replay `grounded: true`
forever — the same trap that once produced an eval measuring stability instead of
relevance. `(prompt_version, model, adapter_version)` is stamped on every take
and every eval result; changing any of them invalidates recordings via
`require_compatible()`.

### Decode settings are correctness, not plumbing
`num_ctx` is set **explicitly** and the fit is checked before every call.
Ollama's default window is small and it truncates the prompt head *silently* —
downstream that is indistinguishable from the starved-context canary, so an
overflow is refused with its own quarantine reason rather than generated and
scored. The model is pinned by **digest, not tag** (a tag is a mutable pointer
that can change weights and quantization underneath you), and
`(seed, temperature, top_p, num_predict, num_ctx)` is stamped on every take —
`adapter_version` does not cover them.

### The compliance eval must prove it can fail
`scripts/record_narration.py --canary` scores deliberately degraded
configurations (starved context, stripped instructions, unconstrained ids) and
**refuses to record** unless the scores drop. An eval that cannot fail is not
evidence. Relevance is **recall, not precision** (precision stays at 1.0 for a model that
cites one safe fact — exactly how the composite first failed its own canary), and
it is **split in two** so a miss indicts the right component:

- `model_recall` — of the expected facts retrieval *offered*, how many were
  cited. A miss here indicts the prompt.
- `system_recall` — of *all* expected facts, how many were cited end to end. A
  system miss with a model pass is a **retrieval** problem: iterate the intent
  scorer in `knowledge/retrieval.py`, not the prompt.

**Pass bars are pre-registered** in `tests/eval/pass_bars.json` before any live
run, because the one instrument failure a canary cannot catch is grading the
first numbers by rationalisation. Changing a bar is its own explicit commit.
`citation_validity` is a hard bar at 1.0 *by construction* — a miss there is an
adapter or schema bug, not model non-compliance, and is triaged as such.

### Knowledge is a small owned graph behind a frozen contract
`data/knowledge/*.json`, nine node kinds, eight edge kinds, every fact carrying
provenance. Validated at load like a prior pack: dangling endpoints, ontology
signature violations and duplicate ids all fail loudly. `Barrier` node ids match
the simulation's derived barrier names, which is how a persona's *simulated*
barriers resolve into *citable* facts.

`retrieve() -> RetrievalResult` is frozen and returns fact **ids**, never prose.
That is what lets the checker verify mechanically and the substrate stay
swappable. Retrieval is query-aware via deterministic term/phrase matching — no
embeddings, because retrieval must stay replayable. Its eval set
(`tests/eval/retrieval_eval.json`) asserts **relevance, not just recall**: the
expected facts must be top-ranked.

### Panel mode: the LLM speaks, code decides who speaks
Turn order, probe triggers and termination are a deterministic state machine.
Themes group by **shared cited facts**, so "3 of 6 personas raised travel" is a
count over citations rather than a judgement call. A model may write a summary
over a mechanically attributed group; it may never decide the grouping.

### Analytics are pure reads
Survival curves, funnels and attribution depend on nothing but event logs.
`tests/test_replay_purity.py` proves it the strong way: write logs to Parquet,
recompute in a **fresh process**, require exact equality. Every log is stamped
with `SCHEMA_VERSION`; loading one from a different schema raises
`IncompatibleEventLog` rather than misreading it.

## Scenario Lab (ui/)
Vite + React + TS, strictly thin: **every number is server-computed**, the SPA
renders artifacts the API already returns. Run `npm run dev` in `ui/` alongside
`uvicorn spp.api.main:app`.

- **Types are generated, not written.** `scripts/export_schema.py` exports the
  artifact models to JSON Schema and codegens `ui/src/types/artifacts.ts`, which
  is **committed** — schema drift becomes a visible diff and a compile error, not
  a runtime surprise. Re-run it after changing any artifact model.
- **Fixtures are shared, rendering logic is not.** The same
  `tests/fixtures/*.json` feed the Python renderer tests and the SPA component
  tests. That is the right coupling: the two renderers can't silently disagree
  about a number. Don't try to share rendering code across Python and TS.
- **Staleness is explicit.** Type-ahead means out-of-order responses;
  `PreviewChannel` debounces, tags each request with a monotonic sequence, aborts
  in-flight requests, and **discards any response older than the newest applied**.
  Aborting is best-effort — the sequence check is the actual guarantee.
- **Latency split, deliberately.** Per-rule eligibility over a resident cohort is
  one pass and runs on every keystroke (~2ms warm). Timeline simulation is not
  and stays behind an explicit button. Blurring the line makes the fast thing
  feel slow.
- **Cohort residency has no invalidation problem.** The key
  `(pack_id, pack_version, cohort_seed, size, as_of)` IS the cohort's identity,
  because generation is deterministic — so eviction is always safe and a rebuild
  is provably identical. `pack_version` is in the key so an edited pack can never
  serve the old population.
- **The URL is the reproducibility state.** Condition, seed, size and rules live
  in the route, so any view is a shareable re-runnable reference rather than a
  screenshot of one.
- **Design constraints**: monospace with tabular figures for every number, ID and
  seed; provenance rail is a *persistent column*, never a footer; red
  (`--integrity`) means never-quote / parse error / ungrounded and **nothing
  else** — a lost persona is a cost, so it takes amber. No webfont: offline-first
  makes a silent CDN fallback a real bug.
- **Last-good figures, not the surviving subset.** While the rule text is
  broken, the readout shows the last result that parsed cleanly. The server
  honestly scores whatever still parses — but rendering that would make
  eligibility appear to *jump* when you break your only rule, which is a wrong
  number presented as current state. Diagnostics still come from the latest
  response, so the editor stays live.
- **E2E is exactly three specs** on the three killer interactions, and
  `playwright.config.ts` boots BOTH servers itself — a spec needing hand-started
  processes is a spec that quietly stops being run. Vitest owns `tests/`,
  Playwright owns `e2e/`; the vitest `include` keeps them apart.

## Interview Room
- **Cassette mode makes the input a picker, not a chat box.** Cassettes key on a
  prompt hash embedding the persona and its retrieved facts, so free text in
  cassette mode is a machine for cache misses. The recorded questions ARE the
  interface, each badged with its take's digest and prompt version; free text is
  shown disabled with the reason and unlocks when a live backend is configured.
- **`MEMORY_SEMANTICS = "independent"`, declared not implied.** Battery takes were
  recorded memory-free, so replay must be too — feeding take N a transcript of
  1..N-1 would change the prompt hash and miss every recording.
  `tests/test_room.py` replays the battery in permuted order and demands
  identical takes. Genuine multi-turn sessions would be a *different artifact*
  (a session cassette); the bug to avoid is silently mixing both semantics.
- **`REPLAY_RETRIEVAL_LIMIT` must match the recorder's** or every fingerprint misses.
- **Citation click-through closes the loop**: fact → provenance (source,
  confidence, as_of) → and when it's a Barrier, the persona's *derived* barrier
  and the profile field it came from. Never fabricates a link the persona lacks.

## Cohort Studio
- Tolerance bands are read from each pack's own `MarginalSpec.tolerance` — the
  contract suite made visible, same field, no transcribed thresholds.
- Cohort diff reuses `report/diffwalk.py` (extracted from the persona-id
  migration check) rather than a second comparator.
- **Per-persona rows require identity pairing. This is an invariant, not an
  option.** Within a run, CRN makes a paired diff exact — same persona, one
  design change, the delta is signal, and that is what the flip table reports.
  Across seeds, persona `i` on each side is an independent draw; a per-pair delta
  between exchangeable strangers is sampling noise, and rendering it in the flip
  table's visual language lends noise the authority that table earned. So
  cross-seed comparison goes **distributional** — both cohorts scored against the
  same pack targets and tolerances — and emits no persona rows. Positional
  pairing survives only as `determinism_debug`, which says so in its own note and
  still emits no rows. `tests/test_studio.py` asserts the invariant.

## Phase 5 port surface (measured, not started)
Vocabulary inventory over core modules, split by what each actually costs:

| bucket | hits | modules | |
|---|---|---|---|
| HARD — clinical concept, must become domain data | 41 | 7 | the real port |
| RENAME — clinical framing of a neutral idea | 156 | 17 | ID-migration playbook |
| NEUTRAL — persona, barrier, cohort, burden | 269 | 21 | keep |

HARD modules: `knowledge/ontology.py`, `knowledge/retrieval.py`,
`protocol/eligibility.py`, `simulation/schedule.py`, `report/studio.py`,
`narration/citations.py`, `cohort/correlation.py`.

**The table measures vocabulary, not semantics.** NEUTRAL was judged by string
match, and clinical structure hides under neutral names — `TRAIT_AXES`,
`TRAVERSAL_PLAN`'s Condition anchor, burden axis meanings, journey-stage
ordering. Bucket HARD seeds the mechanical boundary test's deny-list; only
running a second domain says whether NEUTRAL is clean.

**Barrier derivation is already expressible as data.** All 13 predicates in
`cohort/traits.py` parse in the existing criterion DSL and match the Python path
exactly (780 evaluations, `tests/test_derivation_parity.py`). No new rule
language is needed — a domain pack declares
`{"when": "sdoh.transport == none", "barrier": "transport", ...}` and the
parsed-not-executed discipline carries over. That test is a MIGRATION test:
delete it one release after cutover, together with `traits._signals`.

**Missing-data semantics do NOT transfer.** The two paths agree today by
coincidence — Python reaches "no barrier" via `None == "none"`, the DSL via an
explicit `_MISSING`. And `traits.*` uses `.get(name, 0.5)`, which is *median
imputation* wearing missing-handling's clothes. The port must declare
`on_missing: no_barrier | barrier | flag` per rule rather than inherit the
eligibility policy: a persona with no transport barrier and one whose transport
is unrecorded are different personas to the burden model.

## Evidence bundles
The first live narration run archives to `evidence/<release>/<timestamp>/` —
manifest (model digest, prompt version, sampling), canary output, aggregates and
pass-bar verdicts, the five seed-chosen raw takes, and every quarantine entry.
The README orders them canary → takes → quarantine → aggregates, because that is
the pre-committed reading protocol and a bundle that let a reader skip to the
numbers would defeat it. Bundles are the baseline a later model or prompt bump
gets diffed against.

## Testing (three surfaces, tested differently)
```bash
pytest                                    # everything offline
SPP_LIVE=true pytest                      # adds the live-graph tests
SPP_UPDATE_GOLDEN=1 pytest tests/test_golden.py   # accept an intended change
```
- `tests/test_golden.py` — 12 canonical (cohort, scenario) pairs with committed
  outputs. A diff is a **reviewed** change; regenerate deliberately and read it.
- `tests/test_properties.py` — Hypothesis invariants: eligibility monotonicity,
  burden bounds, fold purity, fork/time-travel agreement, order-independence.
- `tests/test_foundation.py` — the four foundation guarantees.

## Run it
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=src
python scripts/quickstart.py          # offline end-to-end
uvicorn spp.api.main:app --reload --app-dir src
pytest
```

## Build order (open TODOs, roughly MVP -> stretch)
1. `ingest/synthea_loader.py` — real Synthea CSV joins -> PatientDNA. **only one left**
2. ~~`ingest/kg_loader.py` + `graph/client.py` — load Hetionet/PrimeKG, real Cypher.~~ **done**
3. ~~`graphrag/retriever.py` — NL->Cypher (LLM), allowlist-validate, execute.~~ **done**
4. ~~`cohort/generator.py` — distributions from real epidemiology.~~ **done**
5. ~~`api/main.py` `/protocol/stress-test` — real eligibility eval + per-patient
   qualitative burden report via the persona engine.~~ **done**

Search TODO(claude-code) markers for the exact insertion points.

## The knowledge graph (items 2 & 3)
Hetionet v1.0 (CC0), loaded by `python -m spp.ingest.kg_loader`. Default load is
the persona-relevant metaedge slice — 47,031 nodes / 277,997 edges — not the full
2.25M; `--all` gets everything. Re-running is idempotent (MERGE on Hetionet ids).

- `graph/schema.py` is the single source of truth for labels, relationship types
  and metaedge codes. The loader, the traversals and the Cypher validator all
  read it; if they disagree, the system cites edges that don't exist.
- **Hetionet has only 137 diseases.** `heart failure` is not one of them and is
  deliberately NOT aliased to a near neighbour — `resolve()` returns None and the
  persona grounds on nothing. Grounding on the wrong disease is worse than
  grounding on none. `CONDITION_ALIASES` maps shorthand (COPD, T2D) to the
  spelled-out Hetionet names.
- **`DpS` symptom edges are MEDLINE co-occurrence, not curated** — "Birth Weight"
  shows up as a symptom of type 2 diabetes. `build_grounding` warns the model
  rather than filtering silently, so the provenance problem stays visible.
- Retrieval is two-layer: a deterministic anchored traversal that always runs,
  plus an optional LLM-generated Cypher query merged on top. The LLM layer is
  best-effort — every failure path falls back to layer 1. Grounding must never
  depend on a model behaving.
- `graphrag/cypher_guard.py` is deny-by-default: single read-only statement,
  schema-allowlisted labels/relationships, bounded LIMIT, no CALL/UNION, no
  parameters we didn't bind. It guards our pipeline; it is **not** a substitute
  for a read-only Neo4j role in a real deployment.

Note: docker-compose maps host ports **7475/7688** (not 7474/7687) so this stack
can coexist with another Neo4j.

### Done so far (4 & 5)
- `cohort/epidemiology.py` holds per-condition priors (age/sex/stage/comorbidity/
  biomarkers/therapy ladder). **These are order-of-magnitude literature ballparks,
  not fitted values** — item 1 replaces them with Synthea-derived distributions.
  Never quote a number produced by this module as a finding.
- Adherence is *derived* from literacy + SDOH + pill burden rather than sampled
  independently. That coupling is what makes the stress-test surface realistic
  attrition. Coefficients in `_derive_adherence` are judgement, meant to be tuned.
- `protocol/eligibility.py` is a small non-`eval` criterion DSL
  (`age >= 50`, `stage in {a, b}`, bare `CKD`, `not metformin`). Unknown fields
  raise `CriterionError` at parse time — a protocol typo must never look like an
  eligibility signal. Missing values evaluate False, so inclusion fails and
  exclusion doesn't fire.
- `criteria_impact.sole_reason` is the headline metric: patients who would have
  qualified but for that one line.
