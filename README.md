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
- [Review method — 2026-11](docs/AUDIT_METHOD_2026-11.md) ·
  [what it measured](docs/AUDIT_EVIDENCE_2026-11.md) ·
  [the external market read](docs/AUDIT_MARKET_2026-11.md) ·
  [the plan](docs/AUDIT_PLAN_2026-11.md)

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

`quickstart.py` runs all five steps: interview one persona against the grounded
subgraph, generate a 200-patient cohort, screen it through a draft protocol, ask
the survivors whether taking part is realistic, and walk them through the visit
schedule to a retention curve. Offline, the narration layer emits a **citation
skeleton** rather than prose — structured, cited and verifiable, just not in
words. That is the honest offline boundary, not a degraded mode.

> **On `PYTHONPATH=src`.** The package is not installed — `pyproject.toml`
> declares no `[build-system]` and `uv.lock` treats the project as virtual, so
> `pip install -e .` is not a supported path today. Everything below needs the
> variable. `quickstart.py` additionally puts `src` on the path itself, so the
> first command works even if you forgot to export it; the worked example right
> after it, and `uvicorn`, `pytest` and `python -m spp.*`, all still need it.
> That is a known gap (see `docs/AUDIT_EVIDENCE_2026-11.md` §5), not a
> convention to copy.

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

**The offline stub returns placeholders, and each one says so.** With no Neo4j
present the legacy `GraphClient` path returns four edges that demonstrate the
*shape* of a grounded subgraph. They carry `synthetic: true` on the edge object
and a `placeholder, not a retrieved fact` marker inside the grounding block the
model reads — not only a response-level flag, because `grounded_edges` is the part
that gets printed, pasted and screenshotted while response flags do not travel.
Their citations are schema-valid (`kg:hetionet:DpS`, `…:CtD`, `…:CcSE`, `…:GpPW`)
and their relationship types are Hetionet's, not the owned graph's: `TREATED_BY`
is real in `data/knowledge/` and does not exist in Hetionet, and mixing the two
vocabularies is how a system ends up citing edges that were never loaded.
`tests/test_stub_provenance.py` holds all of it, including a canary that runs the
pre-fix values through the same validators and requires them to be rejected.

## What is pinned, and what is not
Everything that could be pinned by a test, is: determinism, replay purity, exact
Shapley efficiency, the correlation PSD gate, retention bands under two master
seeds, the citation gate, memory semantics under permutation.

**The one claim that wasn't, now is.** That a 7B model under schema-constrained
decoding cites the *right* facts was unmeasured in v0.1. It has since been
answered by **four** live runs, each archived under `evidence/<release>/`, read
in the order that bundle's README gives:

| release | prompt | accepted | quarantined | compliance | `model_recall` | bars |
|---|---|---|---|---|---|---|
| v0.1 | 1 | 25/30 | 5 | 0.8333 | 0.500 | met |
| v0.3 | 2 | 30/30 | 0 | 1.0 | 0.525 | met |
| v0.4 | 3 | 30/30 | 0 | 1.0 | 0.5862 | met |
| **v0.5** | **4** | **30/30** | **0** | **1.0** | **0.6724** | **met** |

All four against the same model digest (`qwen2.5:7b-instruct@845dbda0…`), with the
canary proving the instrument could fail before it was believed. v0.5 also broke
the displacement barrier that v0.4 measured: `state_coverage` and `f_recall_exclusive`
rose **together** (0.4419→0.50 and 0.4615→0.5897), which is the conjunction that
was pre-registered precisely because either number alone is purchasable by
sacrificing the other. It still missed its floor — 0.556 against 0.6 on the
blind-labelled slice — and [RELEASE.md](RELEASE.md) states both clauses, because
a reader who takes away only one has been misinformed.

That is evidence about **one** (prompt, model, sampling) configuration read
against **one** battery, not a validation of the model in general;
`require_compatible()` invalidates the recordings the moment any of the three
changes, and the battery's expected facts were re-authored for v0.4 so recall is
not comparable across that boundary. `tests/test_ledger_agrees_with_evidence.py`
holds the assumption ledger, the prompt module and the newest bundle to the same
three values, so this table cannot go stale the way it once did.

Population priors are still literature ballparks, not fitted values — see
[Synthea](https://github.com/synthetichealth/synthea) and
`src/spp/ingest/synthea_loader.py`, which is a calibration-target source for the
prior packs rather than an input to the generator. **Every number the cohort
sampler produces is therefore simulated under stated assumptions and is not a
finding.** Two things now say so mechanically rather than by README:

- `GET /assumptions` returns `unsupported`, and the Scenario Lab renders it — 18
  of 20 shipped heuristics are badged **never quote** in the provenance rail.
- `GET /health` reports `priors.quotable_marginals: 0` and `priors.any_number_quotable:
  false`, derived from the packs' own provenance rather than asserted.

A condition with no prior pack is sampled from a generic chronic-disease shape
and **says so**: every stakeholder endpoint returns `population.generic`, and the
Lab shows an amber banner instead of a confident number.

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
