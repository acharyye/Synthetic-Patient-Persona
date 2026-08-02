# Synthetic Patient Persona

A GraphRAG-grounded conversational **patient digital twin** for trial-design and
patient-journey work. Talk to statistically plausible synthetic patients whose
answers are constrained by a structured profile (*Patient DNA*) and grounded in a
biomedical knowledge graph.

> Design/ideation & stakeholder-simulation tool — **not** medical advice and **not**
> a regulatory virtual-control-arm twin.

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

## Going live (real knowledge-graph grounding)
```bash
cp .env.example .env          # add ANTHROPIC_API_KEY, set SPP_LIVE=true
docker compose up -d          # Neo4j on host ports 7475 (browser) / 7688 (bolt)
PYTHONPATH=src python -m spp.ingest.kg_loader        # ~47k nodes / 278k edges
PYTHONPATH=src python -m spp.ingest.kg_loader --stats
SPP_LIVE=true pytest                                 # includes the live graph tests
```

Ports are offset from the Neo4j defaults so this stack coexists with another
Neo4j; override with `NEO4J_HOST_HTTP` / `NEO4J_HOST_BOLT`.

`GET /health` tells you whether grounding is real — `graph_live: false` means
personas are running on the offline stub subgraph.

### How grounding works
Retrieval is two layers. A **deterministic traversal** anchored on the patient's
condition always runs (symptoms → treatments → adverse events → pathways). When
live, an **LLM-generated Cypher query** for the specific question is validated
and merged on top; if generation, validation or execution fails, layer one still
stands. Every returned edge carries a citation naming the Hetionet metaedge it
came from.

Two honest limits worth knowing:
- Hetionet carries **137 diseases**. `heart failure` isn't one; it resolves to
  nothing rather than being silently mapped to a near neighbour, and the persona
  is told to say it doesn't know.
- Its symptom edges are **MEDLINE co-occurrence, not clinical curation**, so a
  few are junk. The grounding block flags this to the model rather than
  filtering it out of sight.

Patient data is still synthetic-from-priors — see
[Synthea](https://github.com/synthetichealth/synthea) and
`src/spp/ingest/synthea_loader.py` for the remaining build-order item.

## Data sources
- **Personas:** Synthea (synthetic EHRs), MIMIC-IV (credentialed), registries.
- **Knowledge graph:** Hetionet, PrimeKG, Open Targets, SIDER (AEs), Reactome (pathways).

See `CLAUDE.md` for architecture and the build order.
