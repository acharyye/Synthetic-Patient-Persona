# How the 2026-11 review was run

**Run date:** 2026-11-18 · **HEAD under review:** `76c529e` (2026-08-27) · **Author of the review:** the agent session, at the owner's request ("whats this project about, how to improve, what to do next, business plan").

This is the **method** record. The findings live beside it:

- [AUDIT_EVIDENCE_2026-11.md](AUDIT_EVIDENCE_2026-11.md) — every load-bearing claim, marked MEASURED or INHERITED, with the command that reproduces it.
- [AUDIT_MARKET_2026-11.md](AUDIT_MARKET_2026-11.md) — the external brief: competitors, regulation, prices, sources.

It is written down because the review's own conclusion is that **unrecorded verification is not evidence** — the same law this repo already encodes as pre-registration and canaries. A review that could not be re-run or audited would repeat the failure it describes.

## Question as received

Four questions in one: what is this, how to improve, what next, what is the business plan. Only the first three are answerable from inside the repo. The fourth needs the outside, and nothing in the repo had it.

## Shape: a graph, not a chain

Per `CLAUDE.md` §0b, a task with ≥3 independent, similar units runs as a graph. Four reads were dispatched in parallel, each with a schema contract and each told **not to trust the docs**:

| Node | Agent | Contract | Returned |
|---|---|---|---|
| `code` | explore | Real logic vs stub; test health; packaging; the Synthea path | 7-section engineering audit |
| `drift` | explore | Repo reality vs every tracking surface | 7-section drift report |
| `market` | general | Competitors, regulation, prices, monetisation, demand evidence | 8-section sourced brief with URLs |
| `product` | explore | Could a stranger adopt this? | 7-section readiness audit |

**Edge test respected:** no node read another's data. All four started from the same commit and were free to disagree with each other and with `CLAUDE.md`.

**Single-writer respected:** the fan-in (this session) is the only writer. Subagents returned data; none of them wrote a tracked file. `tracker/tracker_state.json` and `docs/okf/` were touched only by the orchestrator, and only in the second step (see *Side effects*).

**Verifier:** the §0b rule is that central claims survive independent skeptics or stay hypotheses. Here the sceptic was the orchestrator re-deriving each headline number from the artifact rather than from a subagent's prose. That is recorded per claim in the evidence file.

## What was read first, and in what order

`CLAUDE.md` in full (696 lines) → `tracker/tracker_state.json` (844 lines, the canonical status) → `docs/okf/index.md` → `README.md` → `RELEASE.md` → `RELEASE.NOTE.md` → `spp_vision_and_roadmap.md` → `Brief.txt` → git history → `data/synthea/**` → the four fan-out reads → `docs/okf/SCHEMA.md` and `_TEMPLATE_concept.md` before writing anything down.

The precedence rule was applied as written: this file beats memory and beats any plan document; `docs/okf/` beats memory for procedure. Where a plan document and the tracker disagreed, the tracker won, and the disagreement was itself logged as drift rather than resolved silently.

## Verification rules applied

1. **Re-derive, don't inherit.** Every number quoted in the synthesis was pulled from its own artifact — `compliance.json`, `manifest.json`, `git log`, `wc -l`, `grep -n` — not from a subagent's summary. Four subagent claims survived this and one did not move (see *Where the subagents were wrong*).
2. **MEASURED vs INFERRED, stated.** Market claims are marked `[M]` (sourced, with URL) or `[I]` (judgement). The repo's own ledger convention (`source` + `confidence`) was carried across.
3. **Absence reported as absence.** Six premises in the original question could not be verified and are recorded as unverified rather than filled in.
4. **No retro-fixing.** Nothing was changed to make a finding cleaner. `evidence/` bundles were read, never written.

## Side effects, stated

Nothing was committed, pushed, tagged or sent anywhere. Three local writes occurred:

| Write | By whom | Status |
|---|---|---|
| `pytest` run twice (54s by `code`, 79s by the orchestrator) | both | Read-only; `-p no:cacheprovider` on the second |
| `tracker/tracker.html` regenerated | `drift` node, permitted by its instructions | Gitignored + generated (`.gitignore:56`); no tracked file touched |
| one root `node_modules/` created by an `npx` probe, then removed | `product` node | Self-cleaned; reported in its own output |

`git status` before and after differs only by the pre-existing untracked `.agents/` and `.claude/launch.json`, plus the new `docs/AUDIT_*.md` files and the OKF additions listed in the evidence file.

The second step of this work — syncing `tracker_state.json` and `docs/okf/` to what the review found — was **deliberately not taken** in the first step, at the owner's instruction to document before starting. That sync is itself the first item of the plan.

## Where the subagents were wrong, or I was

Recording this because a review that reports only its own successes is the motivated reading this repo's pre-registration rule exists to prevent.

- **My synthesis initially repeated `RELEASE.md`'s framing** that v0.4's `state_coverage` was "0.4419 → 0.50". The committed v0.4 `compliance.json` reports **0.5641**. 0.4419 is the v2.2 *estimator's* reading of the same run, and RELEASE.md is comparing estimator-to-estimator across prompt versions. Both are defensible; quoting either without its instrument is not. Corrected in the evidence file.
- **The `drift` node's effort-split percentages** rest on a per-commit intent judgement, which is not mechanical. The commit *counts* per day are mechanical and are reproduced independently in the evidence file; the 55.7% grouping is the node's classification and is marked INHERITED.
- **The `market` node hit a websearch rate limit** mid-run and switched to primary sources (SEC filings, vendor pages, journals). That is the better method, but it means the competitor sweep is not exhaustive by construction, and a vendor I did not search for could change the competitive read. Recorded as a limitation, not smoothed over.
- **The `code` node's "zero callers" claim for `synthea_loader.py`** was verified by me directly and holds.

### The owner's review (2026-11-19) — six corrections, all accepted

The review was itself reviewed, and the reviewer found real problems. Recorded because an external skeptic catching things is the point of the exercise:

| Correction | Weight |
|---|---|
| **The market brief's negative controls are overstated.** Low star counts on an unmarketed academic repo and a six-week-old solo repo are the **base rate**, not evidence about willingness to pay | The most substantive correction. It downgrades the section I had called "the most useful data here" — and the plan's gate no longer rests on it. Written into [the market brief](../../../docs/AUDIT_MARKET_2026-11.md) §1 and §9 |
| **The demand gate cannot pass in 6 weeks** — shorter than a pharma procurement cycle, so the falsifier fires even where demand exists. Ask for *"a budget owner asks for a price or a pilot"* at 6 weeks, a signed engagement at ~12 | A gate that cannot pass is the same defect as a canary that cannot fail. Two windows now, falsifiable both ways |
| **The plan skipped the cheapest probe available** — a Boehringer contact, one conversation carrying the v0.5 bundle page and a flip table | Correct, and embarrassing in the useful way: I optimised for reach when signal-per-hour was cheaper. Added as C0 |
| **Phase A is more than 3 days as written**, because A2 bundled a 2–3 day type-generation refactor with a 20-minute rename | Split into A2a (fix + seam test, now) and A2b (refactor, deferred) |
| **Do type 2 diabetes only.** The registered `-p 1000` run covers it; the five keep-runs never came back | Removes a dependency on four under-powered conditions. B1–B3 resscoped |
| **Freezing `is_circumstantial` is right, for a simpler reason:** no customer-visible claim depends on it | The v0.5 distribution-shift law is true and was applied to the wrong thing. Both reasons now recorded, the simple one first |

The owner also confirmed eight load-bearing claims independently against the repo, and accepted two as self-criticism ("I did all the Synthea work without updating the tracker, which breaks the repo's own §2 rule").

## What would falsify this review

Three checks, none performed here:

1. If a named sponsor team turns out to have asked for exactly the missing product surface, the "distribution is the constraint" read is wrong and the engineering backlog is the real next step.
2. If the priors can be fitted from an already-public dataset of adequate n without a licensed partnership, Goal 2 shrinks from two weeks to two days and the SBIR rationale weakens.
3. If `is_circumstantial` reliability turns out to gate a customer-visible claim rather than only a metric, the instrument arc should resume immediately instead of being frozen.
