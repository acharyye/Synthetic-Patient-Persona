# v0.1 — Simulation-driven design review

A synthetic patient population you can stress-test a protocol against, where
every number traces to a seed, a prior pack and an assumption ledger entry.

## What this is

Design and stakeholder simulation. **Not** medical advice, **not** regulatory
evidence, **not** a statistical virtual control arm. Retention levels are
calibrated to a plausibility target, not fitted to observed data — read the
*difference* between two designs, never an absolute figure.

## The demo, in three moves

The demo is the E2E suite narrated. If these three work, the product works;
they are `ui/e2e/killer-interactions.spec.ts` and they run in CI.

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

## What is pinned, and what is not

Everything that could be pinned by a test, is: 681 Python tests, 27 SPA tests,
3 E2E specs. Determinism (same seed → byte-identical), replay purity (analytics
recomputed in a fresh process from Parquet), exact Shapley efficiency, the PSD
gate, retention bands under two master seeds, the citation gate, memory
semantics under permutation.

**One claim is not pinned**: that a 7B model under schema-constrained decoding
actually cites the *right* facts. Every compliance number so far comes from
scripted stubs written to test the instrument. Pass bars are pre-registered in
`tests/eval/pass_bars.json` and the canary must prove it can detect degradation
before any number is trusted. Closing it needs one session on a machine with
Ollama:

```bash
ollama pull qwen2.5:7b-instruct
SPP_LIVE=true PYTHONPATH=src python scripts/record_narration.py --canary
SPP_LIVE=true PYTHONPATH=src python scripts/record_narration.py --record
```

That writes `evidence/v0.1/<timestamp>/` and drops cassettes on disk — at which
point the Interview Room upgrades from skeletons to recorded takes **with zero
code changes**, because the badge already reads whatever evidence exists.

## Running it

```bash
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
export PYTHONPATH=src
python scripts/quickstart.py                      # offline, end to end
uvicorn spp.api.main:app --port 8000              # API
cd ui && npm install && npm run dev               # Scenario Lab
pytest && cd ui && npm test && npx playwright test
```
