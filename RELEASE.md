# v0.4 — The state-citation release

A persona can now cite **itself**. The `P-`/`B-`/`J-` id namespaces put its own
profile fields, derived barriers and journey milestones into the same citation
enum as the retrieved graph facts, so a claim about circumstance can be
`factual` instead of being relabelled `feeling` for want of an id.

It worked. It also cost something, and the instrument caught both — which is
the actual subject of this release.

## The diagnosis, and what happened to it

v0.3 shipped with `factual_fraction` collapsed on two question tags. The
pre-registered claim, committed 2026-08-14 **before the namespaces existed**,
was that this was a *state-citation gap*: the model labelled circumstantial
segments `feeling` because the schema had no id for a persona's own simulated
circumstances. Give it P/B/J ids and those segments should become `factual`
**and cited**.

| tag | v1 (pv1) | v2 (pv2) | v3 (pv3) | |
|---|---|---|---|---|
| burden | 0.6667 | **0.4000** | **0.7000** | recovered |
| mitigation | 0.9333 | **0.4433** | **0.9333** | recovered exactly |
| ae | 1.0 | 0.9333 | 1.0 | control, flat |
| tx | 1.0 | 1.0 | 1.0 | control, flat |
| proc | 1.0 | 0.9 | 1.0 | control, flat |

Both recovery arms landed inside their registered bounds while all three
controls stayed flat. On its face the diagnosis is confirmed.

**The verdict is `OVER-CORRECTION` anyway.** `state_coverage` — the axis built
for exactly this run, kind-independent by design — read **0.5641 against a
pre-registered floor of 0.6**. So roughly half the circumstantial segments cite
a state id and the rest were simply **relabelled**: `factual` without the
grounding that was supposed to earn the label. The recovery is real and its
mechanism is only partly the one predicted.

The floor caught it. That is the whole reason a floor written before the run
exists, and the arm was not moved to accommodate what was measured.

## What the canary found before the run

Two properties of the live configuration, both discovered by running the canary
and then failing to reproduce its baseline, both recorded as amendments while
nothing was yet recorded.

**The `strip_state_ids` lever is not clean.** `f_recall` was registered as
roughly unchanged when the state ids are removed. It moves 0.5306 → 0.6939, and
`f_recall_exclusive` — over the 39 must-groups no state id can satisfy — moves
with it, 0.4615 → 0.6154. That second figure is what makes the reading
unambiguous: this is not a mixed alternation being grounded through its profile
member instead of its graph one. **State ids displace graph citations for claims
with no other citation path.** The enum grew to ~64% state ids and the model
spent its citations accordingly. This is the enum-incentive effect
`f_recall_holds_independently` was registered to catch, arriving in the canary
rather than in the run. Baseline `f_recall` clears its 0.5 floor at 0.5306, and
the thinness is the finding.

**Model-server load state is a hidden variable.** A cold load and a warm one
produce different output for identical inputs: same battery, same digest, same
`(seed, temperature, top_p, num_predict, num_ctx)` — system_recall 0.5862 /
state_coverage 0.5641 cold, against 0.6034 / 0.5897 warm. Each state is
internally exact: two warm runs matched to 4dp and a deliberate unload
reproduced the cold figures exactly. So it is a variable, not noise, and the
digest that pins the weights says nothing about it. Every run now warms the
model first, because stamping it would only let a reader learn that two bundles
are incomparable.

## Two instrument defects, found in the wrong order

Both were found while *adjudicating* the run rather than while building the
instrument, which is why both survived to be found at all.

**Scoring and recording were two live passes** over identical prompts — once
inside `score()` for the report, once again to capture the cassette. Ollama at
temperature 0.0 with a fixed seed is nearly, not exactly, reproducible: two of
thirty takes drifted, and replaying the committed cassette gives `state_coverage`
0.5135 against the bundle's 0.5641. The archived aggregates described a
generation that existed nowhere, and the report and the recording each looked
like evidence for the other. The same defect recorded **first** attempts while
scoring **retried** ones, so a take repaired on its second try would have been
archived broken. Now one pass, via `score(on_take=...)`.

**`context_overflow_rate` was a HARD bar at 0 that `grade()` supplied as a
literal `0.0`.** It had reported PASS in every bundle ever written and would have
done so in a run where every prompt overflowed. It is now counted, over cases
*attempted* rather than cases scored — an overflowed prompt never reaches the
model, so it is not evidence about the model and leaves every behavioural
denominator alone.

Neither changes the v0.4 verdict: both readings of `state_coverage` miss the
floor, so the run takes the same branch of the pre-registered tree either way.

## The bundle is not retro-fixed

`evidence/v0.4/20260823T170152+0000/` is committed as it was recorded, with a
`NOTE.md` stating that its aggregates are not reproducible from its own
cassette, that `state_coverage` should be read as ~0.51–0.56 rather than 0.5641,
and that `context_overflow_rate` was unevaluated there. A bundle is the record
of what happened. The next one is reproducible from its own cassette; this one
is not, and says so.

Adjudication is now its own act: `adjudicate_bundle()` and
`scripts/adjudicate_bundle.py` read a verdict out of `compliance.json`,
`quarantine.json` and the shape file with **no model involved**. Delete
`adjudication.json` and it reproduces exactly. It is written last and read last,
because a reader who meets the verdict first goes through the raw takes looking
for it.

## What is pinned

935 Python tests across 3.11 / 3.12 / 3.13, 27 SPA tests and 3 E2E specs, on
every push. New this release: that scoring and recording see the same sample
(`TestScoringAndRecordingSeeTheSameSample`), that the overflow bar is measured
rather than assumed (`TestOverflowIsMeasuredNotAssumed`), that a verdict can be
re-derived from an archived bundle (`TestReadingAnArchivedBundle`), and that
`E-` stays reserved and empty until event-log citation is actually built.

Work is now steered by OKRs in `tracker/tracker_state.json`, reconstructed from
git history rather than from prose — which immediately caught this file, in its
v0.3 form, still listing the prompt v2 re-record as open two commits after it
closed.

## Still open

- **`state_coverage` is under its floor.** The relabelling half of the recovery
  is unexplained. Reading it needs the raw takes, not another aggregate.
- **State ids displace graph citations.** Measured in the canary, not yet
  addressed. Any fix is a prompt or enum change and therefore a new
  pre-registration, not an edit to this one.
- **`sym` has read `factual_fraction` 0.0 in all three prompt versions.** The
  shape file explicitly predicted that symptom questions *could* legitimately
  rise once state ids existed, since symptoms are simulated state. It did not
  move at all. No bar was set, so this is a reading, not a miss — but it is the
  one prediction in the file that produced nothing.
- **57% of takes are a single segment**, up from 43% in v2. No metric here
  catches degeneracy.
- **The seeded fact-order permutation stays off.** It is the registered lever
  for position concentration and gets its own paired comparison, deliberately
  after v3, so two effects do not entangle.
- `ingest/synthea_loader.py` remains the one open build-order item, so
  `cohort/epidemiology.py` priors are still literature ballparks. **Never quote
  a number from that module as a finding.**
- `cumulative_burden_weight` still ships **frozen at zero**, unidentifiable from
  two anchors. Separating it from `burden_increment_weight` needs a third anchor
  varying per-visit burden at fixed visit count.

## Running it

```bash
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
export PYTHONPATH=src
python scripts/quickstart.py                      # offline, end to end
uvicorn spp.api.main:app --port 8000              # API
cd ui && npm install && npm run dev               # Scenario Lab
pytest && cd ui && npm test && npx playwright test
```

Recording a battery, and reading one:

```bash
SPP_LIVE=true PYTHONPATH=src python scripts/record_narration.py --canary --release v0.4
SPP_LIVE=true PYTHONPATH=src python scripts/record_narration.py --record --release v0.4
PYTHONPATH=src python scripts/adjudicate_bundle.py --release v0.4
```

Adding a dependency: edit `[project.dependencies]`, run `uv lock`, then
`scripts/sync_deps.sh`. CI fails if the rendering is stale.
