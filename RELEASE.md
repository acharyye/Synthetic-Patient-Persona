# v0.2 — Protocol CI, and the narration claim closed

A synthetic patient population you can stress-test a protocol against, where
every number traces to a seed, a prior pack and an assumption ledger entry —
now wired to a **pull request**, and with the one unpinned claim from v0.1
answered by a live run instead of a promise.

## What this is

Design and stakeholder simulation. **Not** medical advice, **not** regulatory
evidence, **not** a statistical virtual control arm. Retention levels are
calibrated to a plausibility target, not fitted to observed data — read the
*difference* between two designs, never an absolute figure.

## New in v0.2

### Protocol CI (`src/spp/ci/`)

Gates protocol design changes the way tests gate code changes. A change to a
committed scenario triggers a CRN-paired simulation against a pinned baseline,
and a retention regression becomes a failing check with a flip table in the PR
comment.

Packaging, not new capability: it reuses the counterfactual engine and the
closed-form Shapley attribution, `simulation/` was not touched, and nothing
statistical is invented. If a comparison is not expressible as CRN-paired flips
plus an existing attribution, it does not go in the verdict.

- `ci/scenario_file.py` — canonical scenario + content hash. **Strict** loader:
  unlike the editor's lenient path, an unparseable rule in a *committed* file is
  fatal, because gating on "the rules that happened to parse" gates on a design
  nobody wrote.
- `ci/baseline.py` — the pinned expectation, diffed like a golden file.
  `require_compatible` refuses a baseline whose pack version, seed, cohort size,
  duration or engine version differs.
- `ci/verdict.py` — gates read from committed `ci/gates.json`, pre-registered
  before any verdict existed. FAIL requires the drop to clear the threshold
  **and** be sign-stable across two master seeds.
- `ci/render.py`, `ci/cli.py` — `verdict.md`, and a host-agnostic
  `spp ci baseline|check|list`. The GitHub Action is a thin adapter.

**One bug worth recording**, caught by running the failing case rather than by
reading it. The sign-stability control originally fell back to comparing the
candidate against *itself* when a baseline had no stored scenario. That yields
zero flips at every seed, reports "not sign-stable", and downgrades every FAIL
to WARN — a gate that cannot fail while looking like protection. A 20pp
regression losing 15 personas passed as a warning. Baselines now store their
scenario, the fallback is a hard error, and `TestGateCanActuallyFail` pins it.

### The live narration claim is closed

v0.1 shipped with exactly one claim unpinned: that a 7B model under
schema-constrained decoding cites the *right* facts. It is now answered by a
real run, archived in `evidence/v0.1/20260802T150651+0000/`.

qwen2.5:7b-instruct pinned by digest, prompt v1, 30 battery cases: **25
accepted, 5 quarantined, compliance 0.8333**, citation validity 1.0, zero parse
failures, every pre-registered pass bar met. The canary proved it could detect
degradation first — stripping the citation instructions dropped `model_recall`
from 0.50 to 0.0167, and starving the context window collapsed 29 of 30
citations onto the first offered fact while the headline metric *improved*.

Reading the raw takes then found a defect no metric could see: 7 of 25 responses
embedded literal `[F###]` markers, so citations rendered doubled. The renderer
now strips them (`narration/structured.py`); the root cause is a stale line in
prompt v1, left as an explicit decision because fixing it bumps the prompt
version and invalidates the recordings. **The defect is archived next to the
metrics** — a bundle containing only what went well is not evidence.

## The demo, in four moves

The first three are the E2E suite narrated — `npx playwright test` in `ui/`,
which boots the API and the dev server itself. The fourth is the new one.

All three test surfaces run on every push and PR (`.github/workflows/tests.yml`):
Python, SPA typecheck and tests, then the E2E specs. `protocol-ci.yml` is
separate and gates protocol *designs* rather than code.

### 1. Type a rule, watch attrition move

Open the Scenario Lab. Tighten `age >= 50` to `age >= 75` and the eligible count
falls **as you type** — one pass over a resident cohort, ~2ms warm. The per-rule
table names which criterion is doing the damage, with an exact Shapley share:
excluding a persona is a veto game, so each failing rule takes `1/|F|` and the
values sum to the number excluded.

Now break the rule — type `bmi_at_screening > 30`. The editor squiggles and
explains, but the readout **keeps the last figures that were actually true** and
marks itself stale. Being mid-keystroke is not an error state, and showing the
score for the surviving rules would make eligibility appear to jump.

### 2. Fork, and read the flips by name

Make every other visit remote and re-run. The answer is not a shifted curve, it
is **seven named people**: who was recovered, what their baseline exit reason
was, and the event where the two trajectories diverged. Runs are paired per
persona under common random numbers, so those flips are exact where a 2-point
retention delta would be inside the noise. `sign_stability` re-runs under a
second master seed; if the direction does not hold, it says so.

### 3. Click a citation through to its barrier

In the Interview Room, pick a recorded question — the picker *is* the interface,
because a cassette can only answer what it has heard. Every answer carries a
badge naming its evidence: `recorded take — qwen2.5:7b-instruct@sha256…,
prompt v1`, or `citation skeleton — no model`.

Click a citation. You get the fact, its provenance (source, confidence, as_of),
and — when it is a Barrier — **which of this persona's simulated barriers
resolves to it and the profile field it was derived from**. A spoken sentence,
its fact, that fact's source, and the simulated barrier it grounds.

### 4. Break a protocol, watch the build go red

```bash
PYTHONPATH=src python -m spp.ci.cli check protocols/t2d_standard_of_care.json
```

Raise `visits_per_year` from 12 to 18 and turn on the daily diary, and the check
fails in ~1.2s with the people named:

```
❌ FAIL — retention 89.3% → 80.0% (-9.33pp), sign-stable across seeds [42, 1234]
7 personas lost, 0 recovered
type-2-diabetes-s42-0084  retained -> dropped  this visit (travel)
```

Thresholds come from `ci/gates.json`, not from the run. The config stamp at the
bottom of the verdict says which population, seed and ledger produced it.

## What is pinned

Everything that could be pinned by a test, is: **793 Python tests** (774 run
offline, 19 need a live graph), 27 SPA tests, 3 E2E specs. Determinism (same seed → byte-identical), replay purity
(analytics recomputed in a fresh process from Parquet), exact Shapley
efficiency, the PSD gate, retention bands under two master seeds, the citation
gate, memory semantics under permutation, no-LLM-on-the-CI-path (`TestPureCore`),
and that the gate can actually fail.

## Known limits, unchanged

- `ingest/synthea_loader.py` is the one open build-order item. Until it lands,
  `cohort/epidemiology.py` priors are order-of-magnitude literature ballparks —
  never quote a number produced by that module as a finding.
- `cumulative_burden_weight` ships **frozen at zero**, not fitted: it is
  unidentifiable from the current two anchors. The ledger says so in the same
  file as the coefficient. Separating it from `burden_increment_weight` needs a
  third anchor varying per-visit burden at fixed visit count.
- Compliance evidence describes **one** (prompt, model, sampling) configuration.
  It is not a validation of the model in general, and `require_compatible()`
  invalidates the recordings the moment any of the three changes.

## Running it

```bash
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
export PYTHONPATH=src
python scripts/quickstart.py                      # offline, end to end
uvicorn spp.api.main:app --port 8000              # API
cd ui && npm install && npm run dev               # Scenario Lab
pytest && cd ui && npm test && npx playwright test
```
