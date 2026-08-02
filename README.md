# Synthetic Patient Persona

A grounded, reproducible **synthetic patient population** for trial-design and
patient-journey work. Talk to statistically plausible synthetic patients whose
answers are constrained by a structured profile (*Patient DNA*) and grounded in a
small owned knowledge graph. Every number traces to a seed, a prior pack, and an
assumption ledger entry.

> Design/ideation & stakeholder-simulation tool — **not** medical advice and **not**
> a regulatory virtual-control-arm twin.

## Documentation
- [Project description](docs/PROJECT_DESCRIPTION.md)
- [Architecture](ARCHITECTURE.md)
- [Repository guide](docs/REPO_GUIDE.md)

## Quickstart (offline, no services needed)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=src
python scripts/quickstart.py
```
`quickstart.py` runs all four steps offline: interview a persona, generate a
200-patient cohort, screen it against a draft protocol, and ask the personas it
kept whether taking part is realistic for them.

Then the API:
```bash
uvicorn spp.api.main:app --reload --app-dir src
# open http://localhost:8000/docs
```

## Stress-testing a protocol
`POST /protocol/stress-test` screens a synthetic cohort and reports which single
criterion is costing you the most candidates:

```jsonc
{
  "condition": "type 2 diabetes",
  "n": 200,
  "inclusion": ["age >= 50", "biomarkers.HbA1c_pct >= 7.5", "stage in {moderate, advanced}"],
  "exclusion": ["biomarkers.eGFR < 45", "adherence_baseline < 0.5", "CKD"],
  "burden": { "visits_per_year": 24, "daily_diary": true },
  "interview_top_n": 3
}
```

Criteria are a small expression language — comparisons (`age >= 50`,
`biomarkers.eGFR < 45`, `sdoh.transport != none`), set membership
(`stage in {moderate, advanced}`) and bare clinical terms (`CKD`, `not metformin`).
Inclusion is ANDed, exclusion is ORed. `GET /protocol/fields` lists what's
available; an unknown field is a 400, never a silent screen-out.

Read `criteria_impact[].sole_reason` first — patients who would have qualified
but for that one line. `at_risk` and `interviews` then cover the people who pass
on paper but would struggle to take part.

## Scenario Lab (the UI)
```bash
uvicorn spp.api.main:app --port 8000    # API — every number is computed here
cd ui && npm install && npm run dev     # http://localhost:5173
```
Type a rule and watch attrition move as you type; fork a design and read the
flips by name; click a citation through to its fact. Those three are the demo,
and they are the entire E2E suite — see [RELEASE.md](RELEASE.md).

## How grounding works
Knowledge is a **small owned graph** (`data/knowledge/core.json` — nine node
kinds, ~140 nodes, every fact carrying its own source and confidence) behind a
frozen retrieval contract that returns fact **ids**, never prose. That is what
lets citations be verified mechanically and the substrate stay swappable.

Owning the ontology rather than ingesting a large public one is deliberate: a
small graph you can defend edge-by-edge beats a big one you can't. It also buys
the participation subgraph no public biomedical KG has —
`Procedure → Requirement → Barrier → Resource` — whose `Barrier` ids match the
simulation's derived barrier names, so a persona's *simulated* barrier resolves
into a *citable* fact.

Citations are a **decode constraint, not a prompt instruction**: `fact_ids` is a
JSON-schema enum of exactly the retrieved ids, so a fabricated citation is
ungrammatical rather than merely detectable. Verification is ordinary code.

A Neo4j/Hetionet backend still ships behind the same contract for larger-graph
work (`docker compose up -d` on host ports 7475/7688, then
`python -m spp.ingest.kg_loader`). It is not the default grounding path.

## What is pinned, and what is not
Everything that could be pinned by a test, is: determinism, replay purity, exact
Shapley efficiency, the correlation PSD gate, retention bands under two master
seeds, the citation gate, memory semantics under permutation.

**One claim is not.** That a 7B model under schema-constrained decoding cites the
*right* facts is unmeasured — every compliance number so far comes from scripted
stubs written to test the instrument. Pass bars are pre-registered and a canary
must prove it can detect degradation before any number is trusted. See
[RELEASE.md](RELEASE.md) for the two commands that close it.

Population priors are still literature ballparks, not fitted values — see
[Synthea](https://github.com/synthetichealth/synthea) and
`src/spp/ingest/synthea_loader.py`, which is a calibration-target source for the
prior packs rather than an input to the generator.

## Data sources
- **Knowledge:** authored in-repo (`data/knowledge/`). Optional: Hetionet.
- **Population priors:** authored prior packs (`data/prior_packs/`), to be
  calibrated from Synthea aggregates.

See the linked documentation above for the architecture and the file-by-file repository map.
