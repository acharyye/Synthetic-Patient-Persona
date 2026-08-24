# Note added 2026-08-24 — this bundle's aggregates are not reproducible from the cassette

Found while adjudicating this bundle, and recorded here rather than corrected,
because the bundle is the record of what happened.

## What was measured

`record_narration.py --record` ran the battery **twice** against the live model:
once inside `score()` to produce `compliance.json`, and once again afterwards to
capture raw exchanges for the cassette. Same prompts, two samples. Ollama at
`temperature 0.0` with a fixed seed is nearly but not exactly reproducible, and
two of the thirty takes drifted between the passes.

Replaying the committed cassette (`tests/cassettes/narration_battery.json`)
through `score()` reproduces:

| metric | `compliance.json` | replay of the cassette |
|---|---|---|
| `model_recall` | 0.5862 | 0.5862 |
| `f_recall` | 0.5306 | 0.5306 |
| `circumstantial_segments` | 39 | 37 |
| `state_coverage` | **0.5641** | **0.5135** |

The recall metrics survive the drift; the state axis does not. The five takes in
`takes/` are byte-identical across both passes — the drift is in cases that were
not sampled, so reading the sampled takes could not have caught it.

The same defect recorded FIRST attempts while scoring RETRIED ones, so a take
repaired on its second attempt was archived in its broken form. No take in this
run was retried (`retry_rate` 0.0), so that path did not fire here.

## What it does and does not change

**The adjudication verdict is unchanged.** Both readings of `state_coverage` sit
below the pre-registered floor of 0.6, so the run takes the same branch of the
tree in `v3_expected_shape.json` either way. See `adjudication.json`.

**The headline number should be read as ~0.51–0.56, not as 0.5641.** The bundle
figure is one of two samples that were both taken and only one of which was kept.

`context_overflow_rate` reads 0.0 and PASSED in `compliance.json`. That bar was
not measured in this run — `grade()` supplied a literal 0.0 — so treat it as
unevaluated here rather than as evidence no prompt overflowed. It is measured
from 2026-08-24 onward.

## Fixed

`score()` now takes an `on_take` callback and the recorder consumes it, so one
generation feeds both the report and the cassette. `context_overflow_rate` is
computed from cases the guard refused. Pinned by
`TestScoringAndRecordingSeeTheSameSample` and `TestOverflowIsMeasuredNotAssumed`
in `tests/test_narration_compliance.py`.

The next bundle is reproducible from its own cassette. This one is not, and says so.
