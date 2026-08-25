# v0.5 — The lever worked and the floor was missed

Both clauses. Never one.

A reader who takes away "v4 failed" has been misinformed exactly as badly as one
who takes away "v4 passed." The segmentation lever did the thing it was built to
do, the headline metric still sits below its floor, and the two facts are not in
tension — they name different parts of the same result.

## The lever worked

v0.4 shipped a miss with a diagnosis: about half of it was the instrument, and of
the rest, roughly eight of eighteen uncovered segments were **compound** — a
circumstance riding along with a cited mitigation, one `fact_ids` list serving two
claims, and the scorer unable to split a sentence to see it. Prompt v4 asks for
**one claim per segment**.

It acted, on three independent readings:

| | v3 | v4 |
|---|---|---|
| `single_segment_rate` | 0.567 | **0.30** |
| `mean_segments_per_take` | 1.80 | **2.23** |
| compounds counted by a blind rater | the norm | **2 of 34 segments** |

The pre-registered falsification condition — *compounds do not fall* — was not
met.

**And the displacement barrier broke.** This is the finding the whole arc was
chasing. v0.4 measured state ids *displacing* graph citations: the two competing
for one segment's citation budget, so buying state coverage cost graph recall.
The conjunction was pre-registered precisely because either number alone is
purchasable by sacrificing the other:

    state_coverage       0.4419 -> 0.50     WHILE
    f_recall_exclusive   0.4615 -> 0.5897

Both rose. Splitting a compound gives each half its own segment and its own
citation obligation, and on these numbers state and graph citation stopped
competing.

Nothing structural was spent: `citation_validity` 1.0, `parse_failure_rate` 0.0,
`retry_rate` 0.0, `context_overflow_rate` 0.0 and measured, zero quarantine, zero
inline markers. The prompt changed; the **schema did not**, so every v3
guarantee — fabrication ungrammatical, format valid at the decoder — carried into
v4 untouched. A schema-level SPLIT would have traded a measurable behaviour for a
re-verification of every structural claim.

## The floor was missed

Gold-semantics coverage on the audited slice: **0.556 against a floor of 0.6.**
Ten apt-citing segments of eighteen coverable, from blind human labels.

The slice is symptom-heavy and burden-absent. That caveat **sized** the miss; it
does not excuse it. The headline stays a miss.

**What stands between 0.556 and the floor is reliability, not expressiveness.**
Identical claim shapes are intermittently grounded: *"I take metformin,
empagliflozin and semaglutide"* cites nothing while a four-drug segment of the
same shape cites all four; one methotrexate segment cites, another does not. The
uncited-coverable population is not a claim type the schema cannot express — it
is the same claim type, sometimes grounded and sometimes not.

## The methodology result, which may outlast the experiment

**The adopted instrument was beaten by the one it replaced, on the run's own
text.**

`is_circumstantial` v2.2 won its adoption gate honestly — agreement 0.6939, κ
0.3336, on a sheet held out from every instrument. On v4's output it scores
**0.5882 / +0.1765 against v2.1's 0.6765 / +0.2609**, and under-counts the
denominator by twelve of twenty-nine.

Nothing regressed. v2.2 is the same code that won. What changed is the text: its
frames were validated on multi-clause segments, and the SPLIT lever's entire
purpose was to produce short single-claim ones.

> **Estimator validity is distribution-relative. Any lever that changes the
> output distribution silently re-opens every instrument validated on the old
> one.**

Made structural rather than remembered. Adoption is **per-distribution**: an
instrument's validation carries a distribution stamp — prompt version, grain
statistics — and **expires** when a lever moves them. And the per-run audit is
promoted from *a check on the estimate* to *the mechanism that detects instrument
expiry*, which is what it did on its first exercise. Without it, `state_coverage`
0.50 ships as the v4 figure with no sign the instrument had degraded on exactly
the text it was measuring.

That completes a shape three releases have been accumulating:

| failure mode | mechanism |
|---|---|
| motivated reading — a prediction written after the numbers | pre-registration |
| a dead instrument — a metric that cannot fail | canaries |
| a true instrument dying quietly of distribution shift | per-run audits |

Three failure modes, three mechanisms, all three now demonstrated on real runs.
The third is the least obvious, because nothing is broken at any point and the
instrument returns numbers of the usual shape throughout.

## How this run was gated

Every commitment was pushed before the generation it constrains:

- **17 arms pre-registered** and published before the prompt change existed.
- **The floor is gold-semantics**, answered against blind labels, never against an
  instrument's estimate — because an instrument's bias sign has already flipped
  once across texts.
- **The audit slice was seeded** (`20260825`, 15 of 30 takes, sampled from keys
  sorted by *fingerprint* — dict order is recording order is battery order, and a
  slice inheriting it is not a slice).
- **Two-pass labelling**, order fixed: circumstantiality text-only and frozen,
  then aptness with citations revealed. It validated itself on first use — the
  four not-apt segments are exactly the four the frozen pass had marked as
  schema-gap.
- **Aggregates stayed sealed** until the labels came back.
- **The reading order changed a verdict.** `schema_gap_union` reads 0.379 against
  v3's 0.1364 and would have been logged as an arm violation; read against the
  composition note first — four `sym` takes and *zero* burden takes in fifteen —
  it is **not adjudicable** from this slice against an arm registered at
  population level.

## Also in this release

- `is_circumstantial` v2.2, adopted on held-out labels, with v1 kept in the module
  and unused by scoring: every v1-era bundle number was produced by it.
- `RELEASE.NOTE.md` — the correction to v0.4's notes, placed beside them rather
  than folded into them. The v0.4 tag and its notes are byte-stable.
- `scripts/check_release_freeze.py` — refuses to amend or re-tag anything the
  remote already carries, and fails closed on an unreachable remote.
- `Take.persona_id` — takes carry whose they are, so the join is a lookup. Third
  appearance of *join by a non-unique key*; a fourth was caught in the design pass
  before it could produce a wrong number.

## Still open

- **`state_coverage` is below its floor**, and the next lever is reliability:
  when the model *can* cite correctly, what makes it do so every time? A decoding
  and prompt-consistency question, so v5 risks no structural guarantee either.
- **Gap-citing is systematic**, measured at four of fourteen citing segments. Under
  citation pressure the model reaches for the causally nearest id — the drug that
  causes the symptom, the condition that produces it. `state_citation_aptness`
  fell 0.913 → 0.714, in the direction registered before the run.
- **Zero `B-` and `J-` citations in the audited slice.** If derived barriers never
  speak run-wide, the barrier click-through chain has no traffic from v4 voice.
  Unsealed with the full run, and the expressiveness thread's next pull — after
  reliability.
- **`P-constraints.*` ids are being cited** while the authoring worksheet marked
  constraints context-not-citable. One line to reconcile.
- **Parameter leakage into voice**: *"I take my medication about 77% of the
  time"* is `P-adherence_baseline` = 0.77 speaking in first person. Maximally
  citable and a realism defect; the grounding metrics are structurally blind to
  it.
- `ingest/synthea_loader.py` remains the one open build-order item, so
  `cohort/epidemiology.py` priors are still literature ballparks. **Never quote a
  number from that module as a finding.**
- `cumulative_burden_weight` still ships **frozen at zero**, unidentifiable from
  two anchors.

## Running it

```bash
python -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt
export PYTHONPATH=src
python scripts/quickstart.py                      # offline, end to end
uvicorn spp.api.main:app --port 8000              # API
cd ui && npm install && npm run dev               # Scenario Lab
pytest && cd ui && npm test && npx playwright test
```

Recording a battery, reading one, and refusing to rewrite a published one:

```bash
SPP_LIVE=true PYTHONPATH=src python scripts/record_narration.py --canary --release v0.5
SPP_LIVE=true PYTHONPATH=src python scripts/record_narration.py --record --release v0.5
PYTHONPATH=src python scripts/adjudicate_bundle.py --release v0.5
PYTHONPATH=src python scripts/check_release_freeze.py --tag v0.5
```

Adding a dependency: edit `[project.dependencies]`, run `uv lock`, then
`scripts/sync_deps.sh`. CI fails if the rendering is stale.
