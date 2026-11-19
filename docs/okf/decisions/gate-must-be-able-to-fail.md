---
type: Decision
title: A bar that cannot fail is not a bar — context_overflow_rate is measured
description: context_overflow_rate is a pre-registered HARD bar whose observed value grade() supplied as a literal 0.0, so it passed in every run ever recorded. Now computed from cases the guard refused.
resource: ../../../src/spp/narration/evaluation.py
tags: [pre-registration, evidence, instrument, decision]
timestamp: 2026-11-19T00:00:00Z
---

# A bar that cannot fail is not a bar

**Found and fixed 2026-08-24**, while adjudicating the [v3 reading](../concepts/v3-reading.md).

## What was wrong

`tests/eval/pass_bars.json` registers `context_overflow_rate` as a **hard** bar with `max: 0.0` and
the rationale *"a non-zero rate means prompts outgrew the window and the run is not measuring what it
claims."* `grade()` supplied its observed value as a **literal `0.0`**.

So the bar reported `PASS` in every run ever recorded, including v0.1, v0.3 and v0.4 — and would have
reported `PASS` in a run where every prompt overflowed and nothing reached the model at all.

This repo already names the failure mode twice: `TestGateCanActuallyFail` in the protocol CI, and the
canary's refusal to record unless degraded configurations score worse. *An eval that cannot fail is
not evidence.* The rule had simply never been applied to `grade()` itself.

## What was decided

`ComplianceReport` gains `context_overflow_rate`, computed by `score()` from the cases whose prompt
the guard refused, and `grade()` reads it. Two properties are deliberate:

- **The denominator is cases *attempted*, not cases scored.** Dividing by the scored count would
  shrink the rate as more prompts overflowed, and hit 0/0 exactly when every one did.
- **An overflowed case leaves every behavioural denominator.** A prompt that never reached the model
  is not evidence about the model. Scoring it as a grounding failure would be the mirror-image
  error — an instrument fault charged to the model.

Pinned by `TestOverflowIsMeasuredNotAssumed` in `tests/test_narration_compliance.py`, which runs a
battery whose every prompt overflows and requires the hard bar to **fail**.

## Reading past bundles

Every bundle recorded before 2026-08-24 shows `context_overflow_rate` observed 0.0, PASSED. Read that
as **unevaluated**, not as evidence no prompt overflowed. `evidence/v0.4/.../NOTE.md` says so in
place.

## The same rule applies to tests, and caught one — 2026-08-25

Adding boundary tests for the three uncovered narration endpoints
(`/persona/narrate`, `/panel/run`, `/persona/interview`, see
[Testing surfaces](../architecture/index.md)) produced eleven tests that all passed on the first run.
Passing first time is not evidence, so each assertion was **mutation-checked**: break the behaviour
it names, require the test to go red. Seven of seven were caught — except one, which was not.

`test_panel_ungrounded_count` recomputed the ungrounded count from the returned statements and
compared it with the endpoint's reported figure. Offline **every statement grounds**, so both sides
are 0 and the assertion passes against an endpoint hard-wired to report `0`. Identical shape to
`context_overflow_rate`: a number that agreed with the truth only because the truth happened to be
the constant.

Rewritten to monkeypatch `run_panel` with a transcript that actually contains an ungrounded
statement, and the mutation is caught. **The practice generalises: a new test that passes
immediately has not yet been shown to be a test.** Mutating the code it covers costs seconds and is
the only thing that distinguishes coverage from decoration.

---
## Accuracy without chance-correction is not evidence of measurement — 2026-08-25

The blind validation of the `state_coverage` denominator scored the **shipped** instrument,
`is_circumstantial` v1, at **61.5% agreement and Cohen's κ = −0.0484**. Below chance. Its agreement
was the class balance's gift: 44 of 52 scored segments were circumstantial, so a classifier that
mostly says yes scores well while carrying no information about the concept.

The demonstration is exact. Restricted to coverable segments, v1 and v2 tie at **0.6957 raw
agreement** — indistinguishable — and separate at **κ 0.0359 against 0.3347**. Accuracy alone would
have called it a dead heat and left the shipped instrument in place.

**Every v1-era coverage number now carries that context.** Not that they are wrong — `state_coverage`
0.5135 and the human-label reading 0.5263 agree closely — but that v1 was never shown to be
measuring the thing it named, and its agreement figure would have looked healthy in any report that
quoted accuracy.

The transferable form, which is why this sits beside the bar that could not fail: **a metric that
cannot be worse than chance has not been shown to be better than it.** Same species as a HARD bar
supplied as a literal 0.0 and a test whose two sides are both zero — a number that agrees with the
truth for reasons unrelated to measuring it.

## Join by a key that is not unique — third appearance, 2026-08-25

A held-out validation joined archived cassette takes back to their personas by **question text**. The
battery has 30 cases over **six unique questions**, five personas each, so the join silently returned
the first matching persona and **24 of 30 takes were scored against the wrong state surface**. Every
agreement figure computed from it was wrong.

It was caught by reading the *misses* — own-regimen segments whose possession frames were visibly
being detected, yet scored as missed — not by anything in the aggregate. The aggregate looked
plausible; that is the whole difficulty with this bug.

Same bug, third costume:

| | key | what it did |
|---|---|---|
| 1 | `synthetic-0000` | unique only within a cohort, so every dict and report keyed on it was a latent collision |
| 2 | the compliance eval | keyed on that id and scored one condition's personas against another's expected facts |
| 3 | question text | 6 unique values over 30 cases, so 24 of 30 takes joined to the wrong persona |

And the same fix all three times: **make the key carry identity.** `Take.persona_id` and
`Prompt.persona_id` now stamp who a take is about, so the join is a lookup rather than a
reconstruction. Two properties are load-bearing and pinned in `tests/test_persona_stamp.py`:

- **`persona_id` is NOT in the prompt fingerprint.** The fingerprint hashes what the model was
  shown, and the persona is already in the system text. Folding the id in would change every
  cassette key without changing a single prompt — invalidating every recording ever made, to gain
  nothing.
- **An unstamped take stays legal.** Takes recorded before 2026-08-25 have an empty stamp and must
  still load; a migration that refused the archive would delete the evidence the fix exists because
  of. This is the freeze principle and the schema-evolution principle pulling the same direction for
  once: the archive is not rewritten to match the new schema, and the new schema is not allowed to
  reject the archive.

A margin note the archive earned. The v0.1 bundle's takes carry no segment text — that schema did not
store it — so when a rater's prior exposure to those five takes had to be excluded from a validation
sheet, the exposed segments could not be identified and **seven segments were dropped by case
instead**. The bundle fix that came later exists precisely because a bundle must let a later reader
reconstruct what was read. Its absence is still being paid for, in installments, which is the
argument the fix was making.

The transferable form: **a join whose key is not unique does not fail, it returns the wrong row** —
which is why it belongs beside the bar that could not fail and the test whose two sides were both
zero. All three are silent wrongness wearing a plausible number.

## The minimal pair — the cheapest instrument validation this project has found

**2026-08-25.** One authored item settled a question no aggregate would have answered.

`is_circumstantial` v2.2 suppresses modal talk, because *"can make me feel tired"* is a property of a
drug and *"makes me feel tired"* is a fact about the speaker. The pair that tests it: **segment 37 of
the adoption sheet** (modal bisoprolol, labelled `n`) against **segment 00 of the held-out sheet**
(indicative bisoprolol, labelled `y?`) — same drug, same effects, different mood.

v2.2 **does not split them.** Correct on 00, wrong on 37. The diagnosis is exact and would have been
invisible in any agreement figure: **the modal suppression guards the experience frame only.** Modal
clinical text carrying a possessive fires the *possession* frame instead and walks through a door
BA2 was never fitted to.

That distinction — *one frame implements the rule* versus *the instrument implements the rule* — is
not recoverable from κ at any sample size. It is one sentence pair, authored from the rule, costing
minutes.

**The generalisation:** every boundary rule wants its minimal pair authored **at rule-writing time**,
before any sheet exists. Same discipline as the canary and the unit fixture, one level finer: the
canary asks whether the instrument can fail, the fixture asks whether each frame fires, and the
minimal pair asks whether a rule is enforced *everywhere it applies* rather than at the one site it
was written for.

## Position as a key — fourth appearance, and the first one caught in the design pass

**2026-08-25.** The v4 audit slice samples 15 of 30 takes. The obvious implementation samples from
`cassette.takes` in dict order — which is **insertion order, which is recording order, which is the
battery's order**. A slice that inherits that ordering is not a random slice, and the flaw would have
been invisible in the result: fifteen takes, seeded selection, entirely defensible-looking. The fix
is one word — sort the keys by fingerprint before sampling — and it went in **before the sample was
ever drawn**.

Fourth sighting of one bug class, and the interesting part is the interval shrinking:

| | where | when it was caught |
|---|---|---|
| 1 | visit ids regenerated from a list index | after personas flipped for reasons unrelated to the design change |
| 2 | `synthetic-0000`, unique only within a cohort | after the compliance eval scored across conditions |
| 3 | takes joined to personas by question text | after 24 of 30 were scored against the wrong state surface |
| 4 | audit slice sampled from dict order | **in the design pass, before the draw** |

Three post-mortems and then a pre-mortem. That progression is the strongest evidence available that
this knowledge base transfers rather than merely records: the same bug arrived a fourth time wearing
a fourth costume, and was recognised by shape before it could produce a wrong number.

The shape, stated once for the fifth time: **anything derived from position — list index, insertion
order, arrival order — is a key that looks stable and is not.** Seed by identity, join by identity,
sample from a canonical ordering.

## Three failure modes, three mechanisms — moved

Pre-registration catches motivated reading, canaries catch dead instruments, and per-run
audits catch true instruments dying quietly of distribution shift. That decision now has its
own file: [estimator validity is distribution-relative](estimator-validity.md).

---

## A commitment is not data — 2026-08-25

`SYNTHEA_TARGETS.json` was written into `data/prior_packs/`. `available_packs()` globs `*.json` in
that directory, so **every pack load failed instantly** — five conditions, one file, four minutes.

The mistake is small and the shape is not. It is the same species as *the eval must not be authored
from retrieval output*: **artifacts that steer the system must not live where the system eats.** A
pre-registration in the data directory is not merely misfiled; it is a commitment sitting inside the
input it constrains, where a loader will one day read it as an input rather than as a rule.

The pre-registrations live together in `tests/eval/` — `pass_bars.json`, `v3_expected_shape.json`,
`v4_expected_shape.json`, `instrument_v2_gate.json`, `synthea_targets.json` — and the file records
the four minutes it spent in the wrong place, because a log that only contains the tidy version is
not a log.

---
Related: [pre-registration](../concepts/pre-registration.md), [one generation, one sample](one-generation-one-sample.md), [The v3 reading](../concepts/v3-reading.md), [instrument v2](../concepts/instrument-v2.md)
