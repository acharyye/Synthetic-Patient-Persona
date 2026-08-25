# Correction to the v0.4 release notes — 2026-08-25

The `v0.4` tag and its `RELEASE.md` are **unchanged and will stay unchanged**. They
were published on 2026-08-24. This file is the correction, placed next to them
rather than folded into them, for the same reason
`evidence/v0.4/20260823T170152+0000/NOTE.md` sits next to that bundle instead of
fixing it: a published artifact stays byte-stable, and the reader who holds the
tag learns what its notes got wrong without the history being rewritten.

## What the notes assert

`RELEASE.md` for v0.4 says of the `state_coverage` miss:

> So roughly half the circumstantial segments cite a state id and the rest were
> simply **relabelled**: `factual` without the grounding that was supposed to
> earn the label.

That attribution was written into the adjudication before anyone had read the
segments. It is wrong for all but one of them.

## What the segments actually are

Read 2026-08-25 over the committed cassette — 30 takes, offline, no model run.
`state_coverage` 0.5135 over 37 circumstantial segments, so **18 carry no state
id**:

| | count | |
|---|---|---|
| cite graph facts only, kind `factual` | **17** | grounded, on the other namespace |
| cite nothing, kind `feeling` | **1** | relabelling, in full |
| had no state id available to cite | **0** | never "had none to offer" |

**Not one of the 18 is an uncited factual claim.** Within the 17:

- **~9 are denominator false positives** — first-person *clinical* claims such as
  *"For the metformin, I need to do fasting blood tests"* (cites `F067`, `F001`).
  The claim is a property of a drug, the graph fact cited is the right one, and no
  state fact could support it. `is_circumstantial` counts them because it keys on
  first person plus a factual marker.
- **~8 are compound segments grounded on one half** — *"I work shifts, so weekday
  daytime appointments are hard for me. Evening and weekend clinic slots… could
  help"* cites the mitigations (`F042`, `F043`) and nothing for *I work shifts*,
  which is `P-social_determinants.employment`. A segmentation problem as much as a
  citation one.

So the miss is **~1/18 relabelling, ~9/18 instrument, ~8/18 segmentation**.

## What does and does not change

**The v0.4 verdict stands.** `state_coverage` missed its floor on both samples
(0.5641 and 0.5135) and the run takes the same branch of the pre-registered tree.
Nothing here revises a bound, and `tests/eval/v3_expected_shape.json` is untouched
— an expectation edited after seeing results is not an expectation.

**The stated mechanism does not stand.** "Relabelled rather than grounded"
describes 1 of 18. A reader taking the branch label at face value would look for a
labelling pathology that is not there.

**About half the miss is the instrument.** That makes the next change an
instrument change, scored on its own and never folded into a model comparison.
See `docs/okf/concepts/instrument-v2.md`.

## Why this is a NOTE and not an edit

The notes were pushed before the correction existed. The freeze rule applies at
publication: a tag whose notes can change is not a record. The error chain is
worth stating plainly, because the fix is mechanical rather than moral — the
release was reported as unpushed, an amend was authorised on that report, and the
amend was performed before the remote was checked. It was caught by a routine
`ahead/behind` reading before anything was force-pushed, and the local rewrite was
reverted.

`scripts/check_release_freeze.py` now refuses to amend or re-tag anything the
remote already carries. Enforced rather than remembered, which is this
repository's standing preference for any rule it has now demonstrated it can
break.

Referenced from v0.5's notes, which ship in `RELEASE.md` alongside this file.
