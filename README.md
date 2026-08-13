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

No API keys, no database, no model download. Everything below runs offline and
deterministically — same seed, same output, every time.

```bash
git clone git@github.com:acharyye/Synthetic-Patient-Persona.git
cd Synthetic-Patient-Persona
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export PYTHONPATH=src

python scripts/quickstart.py
```

`quickstart.py` runs all four steps: interview a persona, generate a
200-patient cohort, screen it against a draft protocol, and ask the personas it
kept whether taking part is realistic for them. Offline, the narration layer
emits a **citation skeleton** rather than prose — structured, cited and
verifiable, just not in words. That is the honest offline boundary, not a
degraded mode.

### Find the line that costs you the most patients

```bash
python - <<'PY'
from spp.cohort import generate_cohort
from spp.protocol import screen

cohort = generate_cohort(condition="type 2 diabetes", n=300, seed=42)
result = screen(
    cohort,
    inclusion=["age >= 50", "biomarkers.HbA1c_pct >= 7.5"],
    exclusion=["biomarkers.eGFR < 45", "CKD"],
)
print(f"{result.n_eligible} of {result.n_screened} eligible")
for c in result.criteria_impact:
    print(f"  {c.criterion:32s} screened out {c.screened_out:3d}   sole reason {c.sole_reason:3d}")
PY
```

```
75 of 300 eligible
  biomarkers.HbA1c_pct >= 7.5      screened out 146   sole reason  83
  CKD                              screened out  93   sole reason  40
  age >= 50                        screened out  46   sole reason  16
  biomarkers.eGFR < 45             screened out  27   sole reason   8
```

Read `sole_reason` first: 83 people failed on the HbA1c line **and nothing
else**, so deleting it alone would take eligibility from 75 to 158. That is the
number that tells you which line of the protocol to renegotiate.

### Gate a protocol change like a code change

```bash
python -m spp.ci.cli list                                   # scenarios + content hashes
python -m spp.ci.cli check protocols/t2d_standard_of_care.json
```

Unmodified, that passes. Now open the scenario, raise `visits_per_year` from 12
to 18, set `daily_diary` to `true`, and run `check` again — roughly a second
later it fails with the people named:

```
❌ FAIL — Protocol CI: t2d_standard_of_care
retention regression 9.33pp vs baseline (fail threshold 1.0pp),
sign-stable across seeds [42, 1234] ([-7, -8])

7 personas lost, 0 recovered (-7 net) · retention 89.3% → 80.0% (-9.33pp)

| type-2-diabetes-s42-0084 | retained -> dropped | this visit (travel) |
| type-2-diabetes-s42-0113 | retained -> dropped | personal barriers (cost) |
```

Baseline and candidate run under identical seeds, so those are exact
per-persona flips rather than a difference of two aggregates. Thresholds are
pre-registered in `ci/gates.json`; a drop that reverses when the population is
redrawn warns instead of failing, because it is below the resolution of the
paired design. `.github/workflows/protocol-ci.yml` runs exactly this on a PR.

### Then the API and the UI

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

**The one claim that wasn't, now is.** That a 7B model under schema-constrained
decoding cites the *right* facts was unmeasured in v0.1. It is now answered by a
live run archived in `evidence/v0.1/20260802T150651+0000/`: 30 battery cases, 25
accepted, compliance 0.8333, citation validity 1.0, every pre-registered pass
bar met — with the canary proving it could detect a degraded configuration
first, and one defect found by reading the raw takes archived beside the
metrics. Read the bundle in the order its README gives.

That is evidence about **one** (prompt, model, sampling) configuration, not a
validation of the model in general; `require_compatible()` invalidates the
recordings the moment any of the three changes.

Population priors are still literature ballparks, not fitted values — see
[Synthea](https://github.com/synthetichealth/synthea) and
`src/spp/ingest/synthea_loader.py`, which is a calibration-target source for the
prior packs rather than an input to the generator.

## Data sources
- **Knowledge:** authored in-repo (`data/knowledge/`). Optional: Hetionet.
- **Population priors:** authored prior packs (`data/prior_packs/`), to be
  calibrated from Synthea aggregates.

See the linked documentation above for the architecture and the file-by-file repository map.

## License

MIT — see [LICENSE](LICENSE).

The authored content in `data/knowledge/` and `data/prior_packs/` is covered by
the same licence. Hetionet, if you enable the optional backend, is CC0 and is
downloaded at runtime rather than vendored here.
