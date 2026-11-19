# The plan the 2026-11 review produced

**Run date:** 2026-11-18 · **Revised:** 2026-11-19, on the owner's review of the first draft · **Method:** [AUDIT_METHOD_2026-11.md](AUDIT_METHOD_2026-11.md) · **Findings:** [AUDIT_EVIDENCE_2026-11.md](AUDIT_EVIDENCE_2026-11.md) · **Outside:** [AUDIT_MARKET_2026-11.md](AUDIT_MARKET_2026-11.md)

## What the owner changed, and why each change is right

The first draft was reviewed. Six corrections landed, and all six improve it. Recorded here rather than silently folded in, because the shape of a plan is its reasoning:

| # | First draft | Corrected | Reason given |
|---|---|---|---|
| 1 | Gate: ≥1 **signed paid engagement** in 6 weeks | 6 weeks → **a budget owner asks for a price or a pilot**; signed engagement → **~12 weeks** | Six weeks is shorter than a pharma procurement cycle, so the falsifier would fire even where demand exists. **A gate that cannot pass is not a gate** — the same defect as a canary that cannot fail |
| 2 | Cheapest probe = the GitHub Action + a published standard | **C0: one conversation** (a Boehringer contact), carrying the v0.5 bundle page and a flip table | Costs nothing and beats waiting for stars. The first draft optimised for reach when it should have optimised for *signal per hour* |
| 3 | Phase A ≈ 3 days | **A2 split**: A2a is the 20-minute rename + one seam test; A2b (the type-generation refactor) **deferred** | The refactor was inflating the cost of the honesty fix, which is the part that blocks everything |
| 4 | Phase B: T2D **plus** five keep-runs | **T2D only.** The registered `-p 1000` run already covers it; the keep-runs never came back | Ships one calibrated pack end to end without waiting on runs that do not exist |
| 5 | Freeze `is_circumstantial` because any lever re-opens every instrument validated on the old distribution | Freeze it because **no customer-visible claim depends on it** | The v0.5 law is true and was correctly applied to the wrong thing. The simple reason is the operative one |
| 6 | A9 = an open question | **Decided: track `docs/okf/`.** Calling an ignored folder canonical *is* the contradiction | Also: the four audit files are untracked and should be added |

Correction 1 deserves its own note, because it is the repo's own rule arriving from outside the repo. `ci/gates.json` and `tests/eval/pass_bars.json` exist so that no instrument passes by construction. The first draft's gate did exactly that — it was set at a threshold the sales cycle cannot cross in the window, which means it would have "falsified" demand regardless of demand. The revised gate is falsifiable in both directions.

## The gate the owner set

Asked which outcome this is aiming for, the answer was:

> *"all, if sellable, ofc sell. it will make it good research, and a portfolio for me. if no sell, then good research and portfolio for me. So, why not to sell if possible, if its an outstanding idea/product and demanded."*

That is a **gate, not "all three"** — and it is the easy kind, because the unconditional value is already secured. A 1,000-test reproducible engine with a pre-registration discipline is *already* research and *already* a portfolio piece. Commercial value is conditional on evidence of demand. So the operating rule falls out:

> **Do everything that raises all three. Build nothing that only pays off *if* it sells, until demand is measured.**

One consequence, stated because it is the counterintuitive one: **do not build the missing product surface this quarter.** The Interview Room and Cohort Studio UI (2–4 weeks), the run store + job queue + auth (3–5 weeks) are pure option-value on selling. Today 16 of 18 endpoints are unreachable and nobody has asked for them. The market read has two negative controls (§1 of the market brief) showing that engineering quality has not been anybody's constraint in this category.

One belief to correct before it costs time: *"if it's an outstanding idea, it's demanded."* Trial Pathfinder published the exact Shapley criterion-attribution in *Nature* on real data and got 69 stars; InSilicoTrial_MAS converged on the whole philosophy, MIT, solo, same disclaimers, and got 0 stars in six weeks. Outstanding idea and demanded are different variables, and the second one is the one with no evidence yet.

## Phase A — unconditional · ~3 days, mostly grunt

*Raises all three regardless. A technical evaluator at a sponsor finds these in an afternoon, and the flagship claim is currently the stale one.*

| # | Item | Where | Type |
|---|---|---|---|
| A1 | Write digest + prompt version back into the ledger; delete the "UNMEASURED" text; **add a test asserting the ledger agrees with the newest bundle** | `assumptions.py:289-296`, `record_narration.py:166` | agreement test |
| A2a | `unquotable` → `unsupported`, **plus one test across the API–UI seam** | `App.tsx:72`, `main.py:556` | **20 min + a test** |
| A2b | *Deferred:* delete the duplicate contract — derive `artifacts.ts` from route *response models* so the seam is type-checked at compile time | `export_schema.py:44-51` | 2–3 days, not this phase |
| A3 | Mark stub edges synthetic **on the edge object** | `graph/client.py:229-236` | grunt |
| A4 | Return `generic_condition: true` on any `GENERIC_EPI` fallback; render amber in the UI | `packs.py:313` → `epidemiology.py:172` | design, small |
| A5 | `[build-system]` + `[project.scripts]` + `py.typed`; self-path `quickstart.py`; serve the SPA from FastAPI; widen `vite.config.ts`'s 5-prefix proxy | `pyproject.toml`, `quickstart.py`, `main.py` | grunt |
| A6 | `/health` reports the graph that actually grounds (141 nodes), not the optional Neo4j backend (0) | `main.py:98` | 2 hours |
| A7 | `print()` → `logging` with request IDs; error boundary in the SPA; `LLM_BACKEND` in `.env.example` + one README paragraph on Ollama | 6 modules, ~33 sites | grunt |
| A8 | **Sync the tracking surfaces** — see below | tracker + OKF | required by §2 |

**A1–A4 and A6 are all instances of one rule, recorded as a concept: [verification belongs where it is consumed](okf/concepts/verification-locus.md).**

### Status as of 2026-11-19 — A1, A2a, A3, A4, A6, C4 done

| Item | State | Evidence |
|---|---|---|
| A1 | ✅ | `assumptions.py` declares prompt 4 + the real digest; `tests/test_ledger_agrees_with_evidence.py` (19 tests, 5 refusal canaries); `record_narration.py` now **refuses** to run against a ledger that disagrees |
| A2a | ✅ | `App.tsx:79`; `ui/tests/app-fetch.test.tsx` (6 tests, real `App` + committed fixture); proven non-vacuous — reverting the fix fails 4 vitest **and** Playwright spec 1 |
| A2b | ⏸ deferred | `Population` is now hand-written in `preview.ts` — a **third** contract; fixture-shape guard covers the server side meanwhile |
| A3 | ✅ | `synthetic: true` on the edge + schema-valid rel types + the grounding block tells the model; `tests/test_stub_provenance.py` (22 tests, 8 canaries on the pre-fix values) |
| A4 | ✅ | `population.generic` on 10 endpoints; amber banner; `tests/test_population_provenance.py` (27 tests) + an E2E `toHaveCSS` check |
| A5 | ⏸ not started | `quickstart.py` self-path **done**, `.env.example` **done**; `[build-system]`/scripts/Dockerfile outstanding |
| A6 | ✅ | `/health` reports 141 nodes / 205 facts on the real graph, plus priors, ledger and narration; Neo4j demoted to its own block |
| A7 | ◐ partial | `.env.example` + `SPP_LIVE=` tolerance done (`tests/test_config_env_flag.py`, 7 tests); `print()` → `logging` and the SPA error boundary outstanding |
| A8 | ⏸ not started | the tracker/OKF sync — the owner's item 2 |
| A9 | ✅ decided | `docs/okf/` un-ignored; `CLAUDE.md`/`AGENTS.md` stay ignored |
| C4 | ✅ | README: four-bundle evidence table, five quickstart steps, the stub-placeholder boundary; worked example re-verified byte-exact |

**Suite: 1028 → 1113 passed, 19 skipped, 60s.** Goldens untouched and `test_pack_contract.py` 186 green, so the distribution did not move. UI: `tsc` clean, 33 vitest (was 27), 3 E2E green against a live server.

**Four defects the review had missed, found only by going into the code** — the stub citations were malformed and mixed two graph vocabularies; `build_grounding` rendered no flag so an edge-level marker never reached the model; the committed fixtures were *already* stale (`ledger_schema_version`, invisible for four releases because the drift guard compared top-level keys only); and `load_all_packs(directory)` silently ignored `directory` on a warm cache, which would have made the quotability canary unable to fail. All four are fixed and held. Full account: [AUDIT_EVIDENCE_2026-11.md](AUDIT_EVIDENCE_2026-11.md) §9.

**A9 — decided.** `docs/okf/` is tracked from this revision, because `CLAUDE.md:16-18` and `AGENTS.md` both declare it canonical for project status and a canonical surface that a cloner cannot read is not a surface. `CLAUDE.md` and `AGENTS.md` stay ignored: they are agent context, not status, and `.gitignore:37-45` already reasons correctly about the difference. The carve-out is narrowed rather than the rule loosened.

**A8, the sync, itemised:** bump `lastModified`; move J `backlog/0` → `in-progress`; pour the 9–11 registered decisions from `tests/eval/synthea_targets.json` into J's `decisions` with their dates; add the fixtures / structural export / keep-modules to `achievements`; add "suite 991 → 1028" and the 37 Synthea tests to `validations`; open a task for the prevalence finding (it is a *reported-not-acted-on* decision awaiting the owner, which is tracker state, not a commit message); re-grade **KR1.3** (four readings, latest 0.6724 against a 0.55 target, untouched since 08-14); record **KR1.1**'s v0.5 movement (burden 0.400→0.900, mitigation −0.08, `ae` exactly at its 0.10 bound); give task M its missing release notes; fix `docs/okf/index.md:32-35` ("Current release: v0.3" → v0.5, "in flight: v0.4" → Synthea calibration); split `estimator-validity` and a `v4-reading` out of `gate-must-be-able-to-fail.md`; widen `build_tracker.py:48`'s `MD_LINK` past `*.md` so `tracker.html` and `instrument_v2_gate.json` are actually checked; repoint `index.md:65` off the ignored `CLAUDE.md`; then `build_tracker.py`.

**A9, the decision only the owner can make:** `docs/okf/` is gitignored while `CLAUDE.md` and `AGENTS.md` declare it canonical for project status. Either track it or stop calling it canonical. A third copy of the rule is the failure `AGENTS.md` refuses to commit to.

## Phase B — unconditional · ~2 weeks

*Breaks the priors deadlock. This is the research payload **and** the only thing that makes the commercial claim true, and it is the regulator-facing obligation the field's own Level-5 framework names.*

**Scope, as corrected: type 2 diabetes only.** The registered `-p 1000` structural run already covers it, so the loader can ship one calibrated pack end to end **without** the five keep-runs — which never came back anyway, and whose SNOMED codes are all still marked *"AUTHORED FROM THE DOCUMENTED MODULE FORMAT, not verified against a run"* (RA's `69896004` has 0 observed rows and its own file calls it "the first suspect"). Waiting on them would hold the mechanism hostage to four conditions that the registered arithmetic already says are under-powered.

**B1 — Act on the finding registered as "REPORTED, NOT ACTED ON".** The repo's own arithmetic: at `-p 1000` the expected living counts are t2d **60**, breast cancer 30, COPD 20, heart failure 0, RA 0 — so the run clears the pre-registered n=50 **for type 2 diabetes only**. Two honest moves:

- **now:** narrow the *calibration* target list to T2D, and record the other four as explicitly out of scope with their observed counts as the reason;
- **later, if the four ever matter:** amend `calibration_run_parameters` (a bigger `-p`, or the keep-runs actually executed).

What is **not** honest: quietly widening the n=50 threshold to admit the conditions that miss it. The threshold was registered before any target existed, and a threshold moved after seeing the numbers is not a threshold.

**B2 — Build the mechanism that does not exist.** The joins → `PatientDNA`; a marginal-derivation script (`scripts/` has `calibrate_hazard.py`, `export_prior_packs.py`, `build_knowledge_pack.py` and **nothing** that computes marginals from a Synthea export); jar-fetch automation pinned by content hash; a MANIFEST emitter for the *calibration* run; the n≥50 rule as a **third visible `ProvenanceKind` state** rather than a paragraph; and a **producer** for `SYNTHEA_CALIBRATED`, which today is representable and unwritable.

**B3 — Ship one Synthea-calibrated T2D pack end to end.** Note what the deliverable is *not*: `synthea_targets.json:41` already decided that `SYNTHEA_CALIBRATED` is **not quotable** — only `CUSTOMER_DATA_FITTED` crosses that line, and it calls that *"a sales conversation, not a build item."* So B3's value is not a quotable number. It is **proof the refitting mechanism works**, which is the sentence that makes the commercial claim true: *"give us your anonymised aggregates and we will refit the pack."* That is also why KR3.2 should be restated as the gate the file says it is, rather than as a build goal.

**B4 — Open one real-data thread.** A licensed dataset: a CRO's anonymised screen-fail aggregates, an academic registry, a sponsor's own enrolment history. This is the only thing that converts Level-5 rehearsal into an estimate. It is a sales conversation, which is why it belongs after C0 rather than before it.

## Phase C — the demand probe

*C0 is two hours and one conversation. C1–C4 are about two days of writing. All of it doubles as research and portfolio output, and it runs alongside B, not after it.*

**C0 — Have the conversation that already exists.** A Boehringer contact came up during the review. One call, carrying two artifacts that are already built — the v0.5 bundle page from `scripts/export_report.py render_bundle`, and a flip table — costs nothing, and **a budget owner's question beats any number of stars.** This is the cheapest real signal available and the first draft missed it by optimising for reach instead of for signal per hour.

> Recorded as stated by the owner. The review has no details of the contact, the thread, or its context — those live outside the repo and must be filled in by the owner before this becomes a plan step rather than a note.

**C1 — Package and ship `action.yml`.** "Gate a protocol change like a code change: a retention regression is a failing PR check with a flip table naming the lost personas." It is the only thing in the repo a stranger adopts with **zero install** — no Python, no `PYTHONPATH`, no data. That is the wedge, and it already exists.

**C2 — Publish the reproducibility standard.** The first seeded, open-flip-table protocol wind-tunnel comparison across the five condition families, framed against the closed platforms: *Medidata, QuantHealth and Prognica cannot be re-run, audited, or air-gapped. This can.* It is the LMArena move adapted to one person — not a leaderboard, a **standard others are measured against** — and it is simultaneously a paper, a portfolio piece, and the only positioning that turns the project's odd design choices into an argument. It also requires the priors caveat to be stated honestly, which Phase B improves rather than hides.

**C3 — Pitch one protocol review at $15–50K.** Sell the analysis, not a licence. The deliverable already exists: `scripts/export_report.py` writes self-contained, network-free HTML with the flip table and per-criterion attribution, and `render_bundle` orders an evidence bundle in its own reading protocol.

**C4 — Fix the public entry point.** `README.md` has not been touched since 2026-08-13 and headlines the **v0.1** bundle: "compliance 0.8333, 25 accepted." The current measurement is 1.0 with 0 quarantined and `model_recall` 0.6724. A prospect reading the public surface today gets the worst number the project ever produced. Cheap, and it is the highest-leverage half-hour in the plan.

## The pre-registered gate

Write this **before** C1–C4 go public, in the repo's own idiom (`tests/eval/pass_bars.json`, `ci/gates.json`, `v4_expected_shape.json` — every commitment pushed before the generation it constrains). Because the one instrument failure a demand probe cannot catch is grading the first numbers by rationalisation. Proposed content, `tests/eval/demand_probe.json`:

```
registered_on:   2026-11-19        # before anything public ships
windows:
  signal_window_weeks:  6          # what a budget owner can reach in
  commitment_window_weeks: 12      # what a pharma procurement cycle actually takes
signals:
  primary_6wk:   a budget owner asks for a price, a pilot, or an evaluation
                 (named person, named org, attributable budget line)
  primary_12wk:  >=1 signed paid engagement (protocol review or licence)
  secondary:     >=25 installs of the GitHub Action from named orgs
                 OR >=200 stars OR inbound from a named sponsor/CRO/device team
  falsifier:     none of the above inside its own window
reading:
  primary_6wk OR primary_12wk OR secondary
                 -> build the product surface (run store, save/load, Interview
                    Room, Cohort Studio). Demand exists.
  falsifier      -> declare it a public good; publish the reproducibility standard
                    as the reference layer; STOP building product surface;
                    bank the research and portfolio value.
not_admissible:
  - stars alone as a primary signal (Synthea: 3,470 stars, 10 years, no revenue)
  - vendor interest without a budget line (Prognica-style "let's talk")
  - my own enthusiasm, or yours, as evidence
  - a "no" from someone who is not the budget owner
```

**Why two windows and not one.** The first draft asked for a signed engagement in six weeks. Pharma procurement does not move that fast, so the falsifier would have fired on a healthy demand signal — which is a gate that cannot pass, the same defect `ci/gates.json` and `tests/eval/pass_bars.json` exist to prevent. Asking for *a budget owner asking* at six weeks is falsifiable in both directions: it can fail because nobody wants it, and it can pass without a contract.

**The falsifier branch is not a failure state.** It is the Synthea shape — widely used, cited, grant-funded, no revenue — and a perfectly respectable terminal outcome. What is not respectable is drifting into it by inattention, which is what the last 12 weeks look like from outside.

**One more honest limitation, added on revision.** The negative controls in the market brief (Trial Pathfinder, InSilicoTrial_MAS) are **weaker evidence than the brief makes them sound.** An unmarketed academic repo and a six-week-old solo repo having few stars is the **base rate**, not proof that nobody would pay. They support the direction — distribution is probably the binding constraint — and they cannot carry the weight of a gate. So the gate rests on C0's conversation and the price-request signal, and **not** on the star counts. If C0 comes back with a budget owner asking, the controls were noise and the plan pivots immediately.

## What is explicitly frozen

**No further `is_circumstantial` revision until a real-data pack exists.** The reason is the simple one, not the elegant one: **no customer-visible claim depends on it.** The v0.5 law — *any lever that changes the output distribution silently re-opens every instrument validated on the old one* — is true, and it applies to the priors move coming in Phase B, which changes the population rather than the text. That is a second reason and a worse one to spend effort now, because it means re-validating twice.

Also frozen: the two missing rooms, the run store, auth, the job queue, the A2b type-generation refactor, any marketplace, any relicensing, any attempt at regulatory standing.

## Sequencing, in one line

**A (≈1 day: the four provenance defects + README) → C0 (a conversation, immediately, in parallel) → tracker/OKF sync → B1+B2+B3 (≈2 weeks, T2D only) → C1+C2+C4 alongside B → gate read at 6 weeks (price/pilot) and 12 weeks (signature).**

The owner's stated next three, which this now matches: *(1) fix the four provenance defects and the README, about a day; (2) sync the tracker and OKF to reality; (3) build the loader and one Synthea-calibrated T2D pack.*

Total before the first real demand signal is readable: **one day of fixes plus one conversation.**
