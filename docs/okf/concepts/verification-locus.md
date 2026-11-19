---
type: Concept
title: Verification belongs where it is consumed
description: The narration ledger still says compliance is UNMEASURED while four bundles say otherwise; the UI inverts the unquotable list. Three releases spent on instrument validity verified the ruler, not what it measures.
tags: [provenance, verification, instrument, effort-allocation, audit]
timestamp: 2026-11-18T00:00:00Z
---

# Verification belongs where it is consumed

**Found 2026-11-18**, in the [external review](../../../docs/AUDIT_METHOD_2026-11.md). One shape explains four separate defects, and it is worth naming because the project's own instruments do not cover it.

## The shape

Every one of these is a fact that was verified **once, at the source**, and then consumed somewhere that was never checked against it:

| Defect | Where it is stated | Where it is consumed | Verified? |
|---|---|---|---|
| `narration.model` says compliance is **UNMEASURED**, `prompt_version: 1`, empty digest | `assumptions.py:289-296` | `GET /assumptions` → `ui/src/App.tsx:68` | ❌ no test; four bundles contradict it |
| Unquotable list | `main.py:556` returns `unsupported` | `App.tsx:72` reads `unquotable` | ❌ the seam; both halves tested alone |
| Stub edges cite `kg:hetionet`, `kg:sider`, `kg:reactome` | `graph/client.py:229-236` | the exported interview artifact | ❌ marker lives one layer up |
| Unknown condition → `GENERIC_EPI` | `packs.py:313` → `epidemiology.py:172` | the UI, styled identically to a real pack | ❌ no warning field |
| Phase 5 port table (41/156/269) | `CLAUDE.md:438-446` | the port argument | ❌ no script computes it, no test asserts it, and `schedule.py` is on the HARD list with **zero** clinical tokens while `traits.py` is absent from it |

The project verifies sources extremely well — golden files, pack contracts, `TestPureCore`, `TestGateCanActuallyFail`, canaries on every lever. It has **no mechanism that asserts a consumer agrees with its source.** `export_schema.py` is the closest thing and it is a hand-maintained second copy of the contract, which is the failure `src/spp/__init__.py:8-20` exists to prevent, reintroduced at the Python↔TS boundary.

## Why it recurs

A source changes, the consumer does not, and both still pass their own tests. Three times the repo fixed this by deleting the duplicate (`CONDITION_EPI`, the version string, `AGENTS.md` as a pointer). Each fix removed one copy. None added a check that the remaining copies agree.

The `unquotable` case is the cleanest illustration: `ui/tests/components.test.tsx:113,126` pass it as a **prop**, so the component test cannot see the fetch; `tests/test_protocol_api.py:225-229` asserts the server key, so the API test cannot see the reader. Green on both sides of a broken seam, and the broken thing is the product's signature feature — 18 judgement-derived heuristics render in the same green styling as the 2 measured ones.

## The allocation consequence

Three releases (v0.3 → v0.5) verified the **instrument**: pre-registration, canaries, blind labels, three generations of `is_circumstantial`, per-distribution instrument expiry. That is good epistemics and it is also **13 commits to move one denominator from 0.5135 to a label-validated 0.5263** — a 1.3-point correction that confirmed the miss it was built to test.

Meanwhile **39 of 70 commits (55.7%)** went to narration-eval/instrument work and **5 (7.1%)** to grounding. Objective averages: O2 (reproducibility) **1.0**, O1 (citable claims) **0.9**, O3 (realism from data) **0.0**.

The instrument measures a population that is still `EXPERT_GUESS` on all 51 shipped marginals, and `RELEASE.md:155` still says *"never quote a number from that module as a finding."*

**Verification is load-bearing only where a consumer reads it.** The ruler is now validated to a standard most measurement work never reaches. What it measures is a guess, and the four places that would tell a reader so are the four that are stale.

## The rule this proposes

> **Any fact stated in one place and read in another gets an agreement test, not a note.** Same species as `TestGateCanActuallyFail` and `TestFloatAccumulation`: make the invariant mechanical so it stops being remembered.

Applied to the five rows above, that is roughly a day of work, and it is the precondition for every external conversation the plan contemplates — a technical evaluator at a sponsor finds these in an afternoon.

## The sixth and seventh instances, found by fixing the first five

Going into the code turned up two more, and the second is the one worth remembering:

6. **The committed fixtures were stale for four releases.** `ledger_schema_version`
   was added to the ledger snapshot *nested inside* the counterfactual artifact in
   `52e7168` — the same commit that wrote the fixture — and the fixture shipped
   without it. `test_the_counterfactual_fixture_still_matches_the_api` compared
   **top-level keys only**, and `export_schema.py` does not run in CI. The guard
   was narrower than its own docstring ("if the artifact shape changes").
7. **`load_all_packs(directory)` ignored `directory` whenever the cache was warm.**
   A single global `_CACHE` meant the parameter was honoured on a cold call and
   silently dropped on every later one — a parameter that is believed *sometimes*,
   which is worse than one that is missing, because the caller has written code
   that looks correct. It was found only because a quotability canary needed a
   fitted pack in a temp directory and received the shipped `EXPERT_GUESS` one,
   returning `quotable: False` for a pack that was fitted.

**Instance 7 is the argument for this whole rule.** A canary that reads the wrong
artifact is a canary that cannot fail — and it does not look broken, because it
returns the conservative answer. The repo's own instrument culture (`TestGateCan
ActuallyFail`, `TestOverflowIsMeasuredNotAssumed`, the frozen `ungrounded_count`
assertion) is about tests that cannot pass; this is about tests that cannot
**fail**, and nothing in the codebase was watching for it.

## What it looks like fixed

A1–A4 and A6 are closed (2026-11-19). The shape of every fix is the same: **the
value moves to where it is read, or a test asserts the two agree.**

| Defect | Fix shape | Held by |
|---|---|---|
| stale ledger entry | declaration + agreement test, *not* import-time disk I/O — the registry must not depend on the working tree | 19 tests, incl. 5 refusal canaries; `record_narration.py` now refuses a disagreeing ledger |
| renamed key at the seam | reader corrected, then the seam itself rendered in a test with a stubbed `fetch` | `ui/tests/app-fetch.test.tsx`; proven non-vacuous — the old code fails 4 vitest **and** Playwright spec 1 |
| unmarked stub edge | marker on the edge **and** in the block the model reads, because the consumer is the fix point | 22 tests, 8 of them running the pre-fix values through the same validators |
| silent generic fallback | a first-class field on 10 endpoints, derived from one resolver, plus a banner | 27 tests, incl. a canary that a fitted pack reads `quotable: True` |
| stale fixture | a recursive shape guard over all six fixtures, with a **synthetic** canary | `TestRecursiveShapeGuard` — synthetic because a historical one passes vacuously after regeneration |

## The holes still open

- **`PriorPack.unquotable()` does not read `derivations.provenance`**, which is
  `EXPERT_GUESS` in every shipped pack — the barrier-severity magnitudes driving
  burden. A pack with every marginal fitted reports `quotable: True` while those
  remain judgement. Pinned as a named limitation rather than patched, because
  closing it is a decision about what a finding *is*.
- **`Population` is hand-written in `ui/src/lib/preview.ts`** — a third contract
  beside `artifacts.ts` and the route schemas, because the routes return bare
  `dict`. Deferred to A2b; the fixture-shape guard and the fetch test cover both
  sides meanwhile.

---
Related: [pre-registration](pre-registration.md), [gate must be able to fail](../decisions/gate-must-be-able-to-fail.md), [one generation, one sample](../decisions/one-generation-one-sample.md), [the evidence file](../../../docs/AUDIT_EVIDENCE_2026-11.md), [the plan](../../../docs/AUDIT_PLAN_2026-11.md)
