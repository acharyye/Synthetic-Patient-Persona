# What the 2026-11 review measured

**Run date:** 2026-11-18 · **HEAD:** `76c529e` (2026-08-27) · **Method:** [AUDIT_METHOD_2026-11.md](AUDIT_METHOD_2026-11.md) · **Outside:** [AUDIT_MARKET_2026-11.md](AUDIT_MARKET_2026-11.md)

Every claim below is marked **MEASURED** (re-derived here from the artifact, with the command) or **INHERITED** (a subagent finding not independently re-derived). Nothing is quoted from memory.

## 1. The suite, re-run twice

| | Result |
|---|---|
| `code` node, 2026-11-18 | 1028 passed, 19 skipped, 0 failed, 4 warnings — **54.22s** |
| Orchestrator re-run, `-p no:cacheprovider` | 1028 passed, 19 skipped, 4 warnings — **79.38s** |

**MEASURED.** Both counts agree; only wall-clock differs, which is the expected shape for a warm vs cold cache.

- 39 test files, 1,047 collected, 8,187 lines of test code against 14,424 lines of product code — ratio **0.57:1**.
- **All 19 skips are one file**: `tests/test_graph_live.py:19`, `skipif SPP_LIVE != "true"`. That file is the entire coverage of the Neo4j/Hetionet stack, so ~7% of product code (`graph` 417 + `graphrag` 308 + `kg_loader` 218 + `persona` 69 ≈ 1,009 lines) **never executes in CI**.
- Collection is fragile on config: with `SPP_LIVE=` (empty string, not absent) the suite aborts with **33 collection errors** — `src/spp/config.py:36` declares `spp_live: bool = False` with no empty-string tolerance. INHERITED.
- No coverage tooling: `coverage` is absent from `.venv` and from `[dependency-groups].dev`. The 8 `pragma: no cover` sites cluster on the live paths. INHERITED.

```bash
PYTHONPATH=src .venv/bin/python -m pytest -q --tb=no -p no:cacheprovider
.venv/bin/python -m pytest tests/test_graph_live.py -q --co | tail -3   # the 19 skips
SPP_LIVE= PYTHONPATH=src .venv/bin/python -m pytest -q --co 2>&1 | tail -3  # 33 errors
```

## 2. Narration evidence, straight from the bundles

**MEASURED** — read from `evidence/<release>/<ts>/manifest.json` and `compliance.json`, not from any prose.

| | v0.1 | v0.3 | v0.4 | v0.5 |
|---|---|---|---|---|
| `prompt_version` | 1 | 2 | 3 | **4** |
| `model_digest` | `845dbda0ea48` | same | same | same |
| `compliance_rate` | 0.8333 | 1.0 | 1.0 | 1.0 |
| quarantined takes | 5 | 0 | 0 | 0 |
| `model_recall` | 0.500 | 0.525 | 0.5862 | **0.6724** |
| `system_recall` | 0.500 | 0.525 | 0.5862 | 0.6724 |
| `state_coverage` | — | — | 0.5641 | 0.500 |
| `f_recall_exclusive` | — | — | 0.4615 | 0.5897 |
| `single_segment_rate` | 0.4667 | 0.4333 | 0.5667 | 0.300 |
| `mean_segments_per_take` | 2.13 | 2.10 | 1.80 | 2.23 |
| `citation_validity` | 1.0 | 1.0 | 1.0 | 1.0 |
| `context_overflow_rate` | absent | absent | absent | **0.0 (measured)** |
| `bars_passed` | True | True | True | True |

`factual_fraction_by_tag`, the table the whole arc turns on:

| tag | v0.1 | v0.3 | v0.4 | v0.5 | v0.3→v0.5 |
|---|---|---|---|---|---|
| burden | 0.6667 | **0.400** | 0.700 | **0.900** | +0.50 |
| mitigation | 0.9333 | **0.4433** | 0.9333 | **0.850** | +0.41, but −0.08 from v0.4 |
| ae *(control)* | 1.0 | 0.9333 | 1.0 | **0.900** | −0.10 — **exactly at KR1.1's "flat within 0.10" bound** |
| proc *(control)* | 1.0 | 0.900 | 1.0 | 1.0 | +0.10 |
| tx *(control)* | 1.0 | 1.0 | 1.0 | 1.0 | flat |
| sym | 0.0 | 0.0 | 0.0 | 0.0 | flat at zero, all four runs |

**Two things follow that no surface currently says.**

1. **KR1.1 has moved and regressed on one axis at the same time.** Burden recovered 0.400→0.900 while a named control sits exactly on its tolerance bound, and mitigation fell 8 points from v0.4. The KR's grade has been 0.9 since 2026-08-14 and no reading since has been entered against it.
2. **`sym` at 0.000 across four runs is not a pass.** `RELEASE.md:348` calls the v0.4 `sym` take "pure feeling and uncited, which is the question doing its job" — that may well be right, but a metric pinned at zero through four prompt iterations is currently uninformative rather than satisfied, and `tests/eval/pass_bars.json` does not distinguish the two.

```bash
python3 - <<'PY'
import json
for rel,l in (('v0.1/20260802T150651+0000','v0.1'),('v0.3/20260814T200447+0000','v0.3'),
              ('v0.4/20260823T170152+0000','v0.4'),('v0.5/20260825T123023+0000','v0.5')):
    c=json.load(open(f'evidence/{rel}/compliance.json')); r=c['report']
    m=json.load(open(f'evidence/{rel}/manifest.json'))
    print(l, m['prompt_version'], str(m['model_digest'])[:12], r['model_recall'],
          r['state_coverage'], r['factual_fraction_by_tag'])
PY
```

**Correction to my own first reading.** The synthesis initially reported v0.4's `state_coverage` as 0.4419 because `RELEASE.md:35` does. The committed v0.4 bundle reports **0.5641**. 0.4419 is the v2.2 *estimator's* re-reading of that run; RELEASE.md compares estimator-to-estimator across prompt versions, which is the right comparison for a lever effect and the wrong one for quoting a run. `state_coverage` now has **six** live values across the surfaces — 0.5641 (v0.4 aggregate), 0.5135 (cassette replay), 0.5263 (gold labels), 0.4762 / 0.4419 (v2.1 / v2.2 estimators), 0.5000 (v0.5), 0.556 (gold on the v0.5 audit slice) — and **no surface states which is THE number.** That is an instrument-reporting gap, not a model result.

## 3. The three provenance defects — verified line by line

**MEASURED.** Each was confirmed by reading the file, not by trusting a node.

### 3.1 The ledger contradicts the bundles

`src/spp/assumptions.py:289-296`, the `narration.model` entry, `source` text reads:

> *"NOT yet exercised against a live model: every compliance number to date comes from scripted stub models written to test the instrument, so this model's actual citation compliance is **UNMEASURED**."*

Its params: `prompt_version: 1`, `model_digest: ""`. Reality: `src/spp/narration/prompt.py:54` is `PROMPT_VERSION = 4`, and four bundles carry digest `845dbda0ea48…` with `compliance_rate` up to 1.0 and `bars_passed: True`.

This is served to users: `GET /assumptions` (`src/spp/api/main.py:545`) and `ui/src/App.tsx:68` fetches it. `scripts/record_narration.py:166` computes the digest at record time and **never writes it back**; the comment at `:275-277` ("Filled in at record time") describes a mechanism that does not exist. INHERITED: `grep narration.model tests/*.py` returns nothing, so **no test guards this entry**.

Same class of bug, smaller stakes: `narration/cassette.py:5` says "the 477 offline tests" (now 1,047 collected); `report/studio.py:9` says "the 181 contract tests" (collects 186).

```bash
sed -n '285,300p' src/spp/assumptions.py
grep -n "PROMPT_VERSION = " src/spp/narration/prompt.py
grep -rn "narration.model" tests/ || echo "no test guards it"
```

### 3.2 The offline stub cites databases it never queried

`src/spp/graph/client.py:229-236`, **MEASURED verbatim**:

```python
def _stub_neighborhood(entity: str) -> list[dict]:
    e = entity or "condition"
    return [
        {"source": e, "rel": "PRESENTS_SYMPTOM", "target": "fatigue", "cite": "kg:hetionet"},
        {"source": e, "rel": "TREATED_BY", "target": "first-line therapy", "cite": "kg:opentargets"},
        {"source": "first-line therapy", "rel": "CAUSES_AE", "target": "nausea", "cite": "kg:sider"},
        {"source": e, "rel": "ASSOCIATED_PATHWAY", "target": "example pathway", "cite": "kg:reactome"},
    ]
```

Four invented edges carrying four real-database citations, **with no synthetic marker on the edge objects**. Mitigations exist one layer up (`narration_synthetic: true`, `narration_backend: null`, `/health.graph_live: false`), so the artifact most likely to be screenshotted or exported is the unlabelled one. INHERITED: the `code` node confirmed by calling `POST /persona/interview` on the default offline path that these return verbatim.

### 3.3 The signature feature is inverted in the only UI that ships

| | |
|---|---|
| `ui/src/App.tsx:72` | `setUnquotable(data.unquotable ?? [])` |
| `src/spp/api/main.py:556` | returns `"unsupported": [a.name for a in LEDGER.unsupported()]` |

**MEASURED** at both ends. `Set(undefined)` → empty → the red "· never quote" badge at `ui/src/ProvenanceRail.tsx:40-42` never fires, so all 18 judgement-derived heuristics render in the same green `.tag.ok` styling as the 2 measured ones (`ui/src/styles.css:245-246`).

Why it survives: `ui/tests/components.test.tsx:113,126` pass `unquotable` as a **prop**, never exercising App's fetch; `tests/test_protocol_api.py:225-229` asserts the server key `unsupported`. Both halves green, the seam untested. Root cause: `scripts/export_schema.py:44-51` hand-maintains a **second** contract for the same wire format instead of deriving from route response models — the exact "a value copied is a value that diverges" failure `src/spp/__init__.py:8-20` was written to eliminate, reintroduced at the Python↔TS boundary. INHERITED: the `product` node confirmed `unsupported` appears **0** times in the production bundle and `unquotable` 3 times.

### 3.4 An unknown condition returns a confident 200

`src/spp/cohort/packs.py:313` `pack_for()` → `None` → `src/spp/cohort/epidemiology.py:172` → `GENERIC_EPI` (`:121`). **MEASURED** at both ends of that chain. No warning field, no generic flag in the payload, and the UI renders it identically to a real pack. INHERITED: the `product` node measured `{"condition":"glaucoma"}` returning 20/20 eligible via API and 79/100 via the UI, with `identity: "generic:glaucoma@v0 …"`.

For a tool whose thesis is "every number traces to a seed, a prior pack and a ledger entry", inventing a population on a typo and not saying so is the most serious of the four, because it produces a **confident wrong provenance** rather than a missing label.

## 4. The Synthea hole

**MEASURED.** `src/spp/ingest/synthea_loader.py` is **27 lines** (`wc -l`), and from `:18` to `:27`:

```python
def load_from_synthea(csv_dir: str | Path, limit: int | None = None) -> list[PatientDNA]:
    csv_dir = Path(csv_dir)
    if not csv_dir.exists():
        raise FileNotFoundError(...)
    # TODO(claude-code): read patients/conditions/medications with pandas and join
    # on PATIENT id to build one PatientDNA per person.
    raise NotImplementedError("Implement Synthea CSV joins -> PatientDNA.")
```

It is the **only** `NotImplementedError` in `src/spp/**` that is real debt (`protocol/eligibility.py:181` is a legitimate ABC overridden at `:189`), and the only 2 `TODO(claude-code)` markers in the repo are both here. INHERITED: zero callers (grep across `src/`, `tests/`, `scripts/`, `ci/`, `.github/` returns only its own `def`) and zero tests.

Around it, **196 lines of pre-registered governance** in `tests/eval/synthea_targets.json` carrying 9–11 registered decision blocks: `diff_before_adopt`, `fixture_design`, `sample_size_discipline` (n_threshold 50, registered before any target), `deceased_patients` (EXCLUDE non-empty `DEATHDATE`), `jar_pinning` (by content, never tag), `medication_ladder_is_membership_not_order`, `condition_mapping`, `calibration_run_parameters`, `PRE_RUN_FINDING`, `keep_run_supplement`, `sdoh_findings_deferred`.

**MEASURED** — the structural export's own manifest:

```json
{"tool": "synthea-with-dependencies.jar", "population_flag": "-p 100", "seed": 11,
 "patients_generated": 113, "generated_on": "2026-08-27",
 "jar_sha256": "018ad7f04f7aacb995804d7d4781c76d5fc714f7f23257ba50daa9eefae224ac",
 "purpose": "structural-validation run ONLY — feeds NO calibration target",
 "truncation": {"file": "observations.csv", "rows_kept": 5000,
                "rows_in_full_export": 81612, "full_file_sha256": "10cd35b6…"}}
```

The truncation is **recorded rather than silent**, and every other table is complete. That is the right move and it is worth naming as such.

**The binding constraint, from the repo's own file.** `PRE_RUN_FINDING` status reads `"REPORTED, NOT ACTED ON"`. INHERITED, then independently corroborated against the CSV by the `code` node: at `-p 1000` the expected living counts are t2d 60, breast cancer 30, COPD 20, heart failure 0, RA 0 — so **`-p 1000` clears the pre-registered n=50 for type 2 diabetes only**. In the 113-patient structural run the observed rows were t2d 8 (6 living), breast cancer 3/3, emphysema 1/0 living + COPD 3/2, CHF 1/0 living, **RA 0 rows** — and RA's keep-module SNOMED `69896004` is flagged UNVERIFIED in its own file, "the first suspect".

**What is missing before a fitted prior can exist** (INHERITED from the `code` node, consistent with what I measured):

1. The joins and `PatientDNA` construction — absent.
2. **No derivation mechanism at all.** `scripts/` has `calibrate_hazard.py`, `export_prior_packs.py`, `build_knowledge_pack.py`; nothing computes marginals from a Synthea export. No jar-fetch automation, no calibration-run runner, no MANIFEST emitter for that run.
3. The calibration runs have never been executed. Only the 113-patient structural run exists, and it is barred from feeding targets.
4. All five keep-modules say *"AUTHORED FROM THE DOCUMENTED MODULE FORMAT, not verified against a run."*
5. Nothing consumes `condition_mapping` or the 5-vs-6 can/cannot split; it is prose in a JSON nothing reads.
6. The n≥50 rule has no implementation — no smoothing, no threshold check, no third visible `ProvenanceKind` state.
7. **Nothing can write a `SYNTHEA_CALIBRATED` provenance into a pack.** `packs.py:47-79` can represent one; no producer exists.
8. `tests/test_synthea_targets.py:89-97` (`TestTodaysPacksAreHonest`) asserts all 51 shipped marginals are still `EXPERT_GUESS` — **and passes because nothing has moved.**

The one thing correctly wired: `epidemiology.py:100-113` builds `ConditionEpi.from_pack()`, so refitted priors reach the generator automatically. **Net: ~90% governance, ~0% mechanism.**

## 5. Drift: what the tracking surfaces do not know

**MEASURED.** `git log --pretty=%ad --date=short | sort | uniq -c`:

```
   5 2026-08-02    8 2026-08-23
   2 2026-08-07    5 2026-08-24
   5 2026-08-13   24 2026-08-25
  10 2026-08-14    6 2026-08-27
   4 2026-08-15   ----  70 total, `git rev-list --count HEAD`
   1 2026-08-17
```

Ten days with commits, all in 2026-08-02…27. **The repo has been silent ~12 weeks** (today 2026-11-18). There are **no July commits** — which corrects the premise of my own question to the `drift` node, and means `startWeek: 31` / `endWeek: 44` frames a 14-week plan that is 8 working days deep.

| Surface | Says | Reality |
|---|---|---|
| `tracker/tracker_state.json:8` | `lastModified: 2026-08-25` | 6 commits landed 08-27 |
| `tracker_state.json:7` | `todayWeek: 34` | 08-27 is week 35; today is week **47**, past `endWeek: 44` |
| `tracker_state.json:200-202` | S2 "the active workstream" = v0.4 | v0.4 and v0.5 both shipped; the active workstream is Synthea |
| `docs/okf/index.md:32` | "Current release: **v0.3**" | v0.5 |
| `docs/okf/index.md:33` | "In flight: v0.4" | shipped 08-23/24 |
| `README.md` | last touched **2026-08-13**; headlines v0.1 evidence | v0.5 |
| `tracker_state.json:634` | best recorded suite "991 passed" | **1028** |

**MEASURED:** `a150a67` (2026-08-27 10:00) rewrote `tracker_state.json` (+19/−12) and did **not** touch `lastModified` — `git show a150a67 -- tracker/tracker_state.json | grep -c lastModified` → 0. `CLAUDE.md:671` says the app detects newer state *by that field*, so the one tracker edit made after 08-25 is invisible to the thing that reads it.

**Commits after 08-25 with no tracker reflection** (INHERITED, from `git show --stat`): `d2ff1db` (+69 to `src/spp/cohort/packs.py` — `ProvenanceKind`, `QUOTABLE_KINDS`, the unversioned-`SYNTHEA_CALIBRATED` validator, and **quotability re-keyed from confidence to kind**), `dd93d64` (5 adversarial fixture CSVs + 101 test lines), `ce3822d` (20,041 lines / 4.7 MB structural export + 106 test lines + `.gitignore` carve-out), `ddd877e` (+69 prevalence finding), `76c529e` (5 keep-modules, +213). **None appears in the tracker.** `d2ff1db` is a semantic change to a gate every report reads, and KR3.2's grade is still 0.0 with no decision entry.

**`grep` the whole tracker:** `keep_module` → 0, `structural_seed11` → 0, `ProvenanceKind` → 0, `synthea_targets` → 0. S3's tasks J and K are `backlog`/`progress: 0` with every list empty.

**Five of seven `RELEASE.md:136-159` "Still open" items have no task and no KR:** the reliability lever (the *named next lever* for the release's own headline metric), gap-citing (`state_citation_aptness` 0.913→0.714), zero `B-`/`J-` citations in the audited slice, `P-constraints.*` cited against a worksheet marking them not-citable, and parameter leakage into voice ("I take my medication about 77% of the time" = `P-adherence_baseline` 0.77). Only the Synthea item and `cumulative_burden_weight` are tracked.

**Orphans the other way:** task M's entire deliverable (~440 lines of `scripts/export_report.py` + `report/html.py` renderers, 175 test lines) is absent from `RELEASE.md:126-134` and from `README.md`, and both its commits post-date the `v0.5` tag. **KR1.3 is stale in the flattering direction** — target 0.55, grade 0.8 since 08-14, four readings now 0.500 / 0.525 / 0.5862 / **0.6724**, and `RELEASE.md` never reports `model_recall` at all in the release with its highest value. Task C is `done`/100 while linked to a 0.0 KR. Task B's "done" credits the Neo4j slice (47,031 nodes / 277,997 edges) and links KR1.1, but **every narration module imports `spp.knowledge`** — only `persona/engine.py:15` imports `graphrag` — so KR1.1's lineage runs through a substrate that produced none of the v0.1–v0.5 numbers.

**Effort split** (INHERITED — the `drift` node's per-commit intent classification, not mechanical): narration-eval/instrument **39 of 70 commits (55.7%)**, product surface 17 (24.3%), meta 9 (12.9%), grounding 5 (7.1%). `is_circumstantial` alone consumed **13 commits** to move one denominator from 0.5135 to a label-validated 0.5263 — a 1.3-point correction that confirmed the miss it was built to test. Objective averages: **O2 = 1.0, O1 = 0.9, O3 = 0.0**; overall KR mean 0.633. The commit counts per day above are mechanical and confirm the concentration: 08-23/24/25 = 37 of 70.

## 6. OKF and publication state

**MEASURED:** `git ls-files docs/` returns exactly `docs/PROJECT_DESCRIPTION.md` and `docs/REPO_GUIDE.md`. `git check-ignore -v`:

```
.gitignore:50:docs/okf/   docs/okf/index.md
.gitignore:37:CLAUDE.md   CLAUDE.md
```

So `docs/okf/`, `CLAUDE.md`, `AGENTS.md` and every plan document are **unpublished**, while `CLAUDE.md:16-18` and `AGENTS.md` declare the OKF "canonical for project status". For anyone cloning the 290 tracked files, the canonical status surface does not exist. The `.gitignore:48-49` comment argues the right principle — steering "belongs where a reader can check it", so the tracker is tracked — then applies it inconsistently to the OKF.

**MEASURED:** `git check-ignore docs/AUDIT_2026-11.md` → not ignored. The `docs/` top level is publishable, which is why the three audit files live there rather than in the OKF.

`python3 tracker/build_tracker.py` → `OK`, exit 0, "4 Stages, 17 Tasks, 3 Objectives, lastModified=2026-08-25", "22 Konzepte, 92 Verweise", no dead links reported. **The checker is narrower than the guarantee:** `MD_LINK` (`build_tracker.py:48`) matches only `*.md`, so `concepts/instrument-v2.md:138` → `tests/eval/instrument_v2_gate.json` and `index.md:39` → `../../tracker/tracker.html` are never validated — and `tracker.html` is itself gitignored (`.gitignore:56`), so for a cloner the OKF's pointer to canonical steering is dead and the checker is blind to it by construction. `index.md:65` still instructs the maintainer to consult `../../CLAUDE.md`, the exact defect commit `19d91d1` ("a pointer to an ignored file must not ship") was made to fix.

INHERITED, spot-checked: `glossary/index.md:15` and `references/index.md:15` were **empty** (`_(empty — link new concepts here)_`) while `index.md:46,50` promise "Patient DNA, battery, bar, take, bundle" and "Hetionet, Synthea, tickets, dashboards" — and 20,041 lines of Synthea export had landed 08-27 with no reference entry. Both folders were populated by this review (see §10). `architecture/index.md` holds one file. There is **no OKF concept for v0.5** — `concepts/` has `v3-reading.md` for the previous release and nothing for v4's verdict — while `RELEASE.md:64-100`'s methodology law was appended mid-file to `decisions/gate-must-be-able-to-fail.md`, which admits at `:186` that it "has been accumulating one idea in costumes", against `SCHEMA.md:15` rule 1.

**A sixth instance, found while registering this review.** `docs/okf/concepts/instrument-v2.md` contradicts **itself**: `:64` says `state_coverage` under v2 is "**not adopted**" and cites `TestNotWiredIn`, while `:90` says "**v2 is adopted**: it beats v1 on both". Both were true at different moments of a 14-commit arc and neither was retired; the file knows nothing of v2.1/v2.2, and its frontmatter description ("not wired in until blind labels exist") is stale a third way. This is §3's rule failing inside the knowledge base: the file recorded each state of a moving decision and kept none of the current one. Left as found and registered here, rather than silently rewritten — rewriting it is A8's job, not the review's.

**Contradictions between surfaces, all MEASURED by reading them:**

| Question | Answers |
|---|---|
| Default grounding path | `README.md:156-158` owned graph · `ARCHITECTURE.md:62-77` owned graph · `okf/index.md:36` "Neo4j (optional)" · **`CLAUDE.md:38-42` Neo4j on the main path, and `okf/architecture/core-narration-split.md:38-45` is a verbatim copy of it** · tracker task B credits Neo4j |
| Job of `synthea_loader.py` | `CLAUDE.md:568` + tracker J + KR3.1: "CSV joins → PatientDNA" · `README.md:179-180`: "a **calibration-target source for the prior packs rather than an input to the generator**" · `synthea_targets.json`: calibrate pack marginals, nothing about PatientDNA rows. **The "historical" README is closest to what is being built.** |
| `CONDITION_EPI` removed? | `CLAUDE.md:172-173` says removed · `scripts/export_prior_packs.py:23` still imports it (INHERITED: measured `ImportError`) · `assumptions.py:452-456` still registers `cohort.condition_priors` pointing at `spp.cohort.epidemiology` |
| Which numbers are quotable | `README.md:165-171` headlines v0.1's 0.8333 · `RELEASE.md` reports v0.5's 1.0 · `synthea_targets.json:41` says `SYNTHEA_CALIBRATED` is **not** quotable, only `CUSTOMER_DATA_FITTED` — "a sales conversation, not a build item", which makes KR3.2 not a build goal at all |

**Phase 5 port table is unverifiable** (INHERITED, and the strongest version of the drift finding): `CLAUDE.md:438-446` claims HARD 41 / RENAME 156 / NEUTRAL 269 and names `simulation/schedule.py` as HARD. The `code` node's token scan found **zero** clinical vocabulary in `schedule.py` (0 hits) while `cohort/traits.py` (17 signals keyed on GOLD/NYHA ladders, 8 voice sentences) and `cohort/packs.py` (`dx_delay_months`, `medication_ladder`) are **absent from the HARD list**. The numbers 41/156/269 appear nowhere outside CLAUDE.md; no script computes the table, no test asserts it, and "bucket HARD seeds the mechanical boundary test's deny-list" names a test and a deny-list that do not exist. `CLAUDE.md:455-456` says the parity test covers "13 predicates … 780 evaluations"; the committed test is 13 rules × 100 personas = **1,300**. And the whole table lives in a gitignored file.

## 7. Product readiness, condensed

All INHERITED from the `product` node unless marked otherwise. The node booted the API and measured; I did not re-run its probes.

- **Not installable.** `pyproject.toml` has **no `[build-system]`** (MEASURED: `grep` returns only `[tool.pytest.ini_options]` and an inert `[tool.setuptools.packages.find]`), no `[project.scripts]`, no `py.typed`. `uv.lock:966` says `source = { virtual = "." }` — uv treats it as a virtual project, i.e. explicitly non-buildable. `PYTHONPATH=src` is the whole distribution story.
- **`quickstart.py` fails on a clean machine** — `ModuleNotFoundError: No module named 'spp'`. Its sibling `scripts/export_report.py:26` self-inserts `src` into `sys.path`; `quickstart.py` has no such line. One line fixes it.
- **One of three rooms exists.** `ui/src/main.tsx:6-9` renders `<App/>` with no router; `App.tsx` *is* Scenario Lab (~800 LOC total). The SPA calls **2 of 18 endpoints** (`/scenario/preview`, `/assumptions`). `/room/*` and `/studio/*` are fully built server-side, fully typed in `artifacts.ts:355-423`, and have **zero components**. `ui/vite.config.ts:6` proxies only 5 prefixes, so even a hand-written Interview Room would 404.
- **No async, no auth, no rate limit, no pagination.** All handlers are sync `def`. Measured latencies: `/counterfactual/run` **8.0s** at n=500 with sign stability, **23.5s** with sensitivity; `/counterfactual/report` 8.8s and recomputes. `le=500` caps exactly the two endpoints whose output goes to a committee, while `/scenario/preview` and `/studio/*` allow 2000.
- **No run store.** `foundation/store.py` (Parquet) has exactly one caller in the repo — `tests/test_replay_purity.py` — and its docstring advertises DuckDB, which is **not a dependency**. Cohort residency is an in-process `OrderedDict` LRU with `MAX_RESIDENT = 8`; measured 24 parallel previews at n=2000 gave **hits 0, misses 24**. No locking anywhere (`grep Lock|threading|async def` → 0 hits across the six relevant modules).
- **`as_of` defaults to `date.today()`** (`residency.py:67`, `generator.py:296`) and `/scenario/preview` never passes one, so the shareable URL's journey dates **expire at midnight**. INHERITED: eligibility survives the rollover (136 eligible, retention 0.8309 at both dates) but journey fields shift (diagnosis 2022-12-22 → 2023-04-04), so "the URL is the reproducibility state" holds for the number on screen and silently fails for the timeline.
- **No logging.** `grep -rn "import logging|getLogger|logger\." src/spp` → **zero hits in the entire package**; ~33 bare `print()` sites across 6 modules.
- **`/health` reports the wrong subsystem.** `main.py:98` reads `_engine.graph.stats()` — the optional `GraphClient` — returning `{graph_live: false, graph_nodes: 0}` while the graph narration actually grounds on `spp.knowledge.KnowledgeGraph` with **141 nodes / 205 facts**. An alert on `/health` pages on a working install and stays silent if `data/knowledge/core.json` is corrupted.
- **Ollama is the live default and is documented nowhere.** `config.py:9,12` → `llm_backend = "ollama"`, `qwen2.5:7b-instruct`. Grep for `ollama|qwen2.5` across README, ARCHITECTURE, REPO_GUIDE, PROJECT_DESCRIPTION, RELEASE, `.env.example` → **zero hits**; `.env.example` offers only `ANTHROPIC_*` and has no `LLM_BACKEND` line. A stranger setting `SPP_LIVE=true` with an Anthropic key silently hits `localhost:11434`, fails, and falls back to the null backend with one `print()` — they get template prose, believe the model works, and never learn why.
- **The UI has no error boundary.** API down or `n` out of range → 422 → unhandled rejection → stuck at "Waiting for first pass…" with zero explanation. `?n=0` silently substitutes 400 while displaying 0 (`urlState.ts:45-50`), rendering "339 of 400 screened".

**What is genuinely good enough to ship today** — stated so the audit is not read as uniform: the deterministic core, the seed-scope discipline, the assumption ledger as a *product feature*, the lenient-parse/last-good-figures handling in the preview path, closed-form Shapley, **`action.yml`** (the only thing a stranger adopts with zero install), the 1,028-test suite with a 3-interpreter matrix aimed deliberately at the *oldest* interpreter, hash-pinned deps with a byte-diff stale-lock gate, and documentation whose headline numbers **reproduce byte-exact** (INHERITED: the README's `75 of 300` and sole reasons 83/40/16/8 were re-run and matched).

## 8. Data and code shape

**MEASURED** where noted, else INHERITED.

| | |
|---|---|
| `data/` on disk | 19 MB; **4.86 MB / 18 files tracked in git** (`.gitignore:7` ignores `data/*`, `:12,13,21` re-include `prior_packs/`, `knowledge/`, `synthea/`) |
| `data/knowledge/core.json` | 92 KB — **141 nodes, 205 facts**, 9 node kinds, 8 predicates, 48 subjects, **5 conditions** |
| `data/prior_packs/*.json` | 5 packs (COPD, breast cancer, heart failure, RA, T2D), ~80 KB, 10 marginals each (t2d 11), 22 latent correlations, 3 derivations. **All provenance `EXPERT_GUESS`; none quotable** |
| `data/hetionet/` | 14 MB, **untracked**, re-downloaded at runtime |
| `data/synthea/` | 4.6 MB tracked — 5 keep-modules + the 113-patient structural export |
| Product code | 79 `.py`, 14,424 lines. `narration` **4,129 (28.6%)** · cohort 1,508 · ci 1,240 · foundation 1,233 · simulation 1,168 · report 1,040 · protocol 976 · knowledge 744 · api 644 · **dormant graph stack 1,039 (7.2%)** · schemas 163 · root 540 |
| UI | 8 TS/TSX, 1,084 lines |
| `evidence/` | v0.1, v0.3, v0.4, v0.5 — **no v0.2 bundle**, unexplained |

**Clinical token density: 532 hits** across `src/spp/**/*.py`. Seven places where a second domain is a **code and schema change, not a data drop**: `ontology.py:25-46` `NodeKind`/`EdgeKind` Literals, `:53-62` `EDGE_SIGNATURES`, `:66-75` `EDGE_PHRASING`, `:80-88` `TRAVERSAL_PLAN` (every path roots at `TREATED_BY`), `correlation.py:34-43` `TRAIT_AXES`, `packs.py:268-271` `REQUIRED_FIELDS` (a pack may change numbers about a population and is forbidden from changing what a population *is*), `eligibility.py:92-98` `_ORDINAL_LADDERS` (GOLD/NYHA baked into the parser), plus `BurdenVector` as schema in `foundation/events.py`. No `data/domains/`, no `DomainPack` model, no registry; `PACK_DIR` and `KNOWLEDGE_DIR` are hardcoded with no env override.

Honest sizing of the "drivers, employees, customers tomorrow" claim: **4–8 weeks of design work**, not a config change. What genuinely transfers free: the whole foundation — named seed scopes, the ledger, the pure fold, the copula with its PSD gate, CRN fork-and-diff, closed-form Shapley, cassette discipline. `tests/test_derivation_parity.py` proves all 13 barrier predicates parse in the existing DSL, and its companions `:129-151` honestly document that missing-data semantics **don't** transfer and that `traits.*` uses `.get(name, 0.5)` — median imputation wearing missing-handling's clothes.

## 9. What Phase A actually fixed, and the four things it found on the way

**Done 2026-11-19.** The owner's item 1: *"fix the four provenance defects and the README, about a day."* All four are fixed, the README is current, and the work turned up four more defects that the review had missed — including one that made a quotability canary unable to fail.

**Suite: 1028 → 1113 passed, 19 skipped, 60s.** Goldens **untouched** (`git diff tests/golden` empty) and `test_pack_contract.py` 186 green, so the distribution did not move — no sampler or simulation code was touched. UI: `tsc` clean, **33** vitest (was 27), **3** Playwright specs green against a live server.

| # | Fix | Where | Held by |
|---|---|---|---|
| A1 | `narration.model` now declares prompt 4, the real digest, `compliance_rate`, `bundles_measured`, `measured_release`; the "UNMEASURED" text is gone | `assumptions.py:271-330` | `tests/test_ledger_agrees_with_evidence.py` — **19 tests**, incl. 5 recorder-refusal canaries |
| A2a | `data.unquotable` → `data.unsupported` | `App.tsx:79` | `ui/tests/app-fetch.test.tsx` — **6 tests**, rendering real `App` against the committed fixture |
| A3 | Stub edges carry `synthetic: true` **on the edge**, schema-valid rel types and well-formed citations; the grounding block tells the model | `graph/client.py:229-266`, `graphrag/grounding.py` | `tests/test_stub_provenance.py` — **22 tests**, incl. 8 canaries running the pre-fix values through the same validators |
| A4 | `population.generic` as a first-class field on **10 endpoints**; amber banner in the rail | `api/main.py:population_provenance`, `ProvenanceRail.tsx`, `styles.css` | `tests/test_population_provenance.py` — **27 tests** + an E2E assertion on `border-left-color` |
| A6 | `/health` reports the owned graph (141 nodes / 205 facts), priors, ledger and narration; Neo4j demoted to a separate `neo4j` block | `api/main.py:health` | verified live; `priors.quotable_marginals` derived from packs |
| C4 | README: four-bundle evidence table replacing v0.1's headline; five quickstart steps not four; the stub-placeholder boundary; the `PYTHONPATH` note | `README.md` | worked example re-verified **byte-exact** (`75 of 300`, sole reasons 83/40/16/8) |
| — | `quickstart.py` self-inserts `src`; `.env.example` documents `LLM_BACKEND`/`OLLAMA_*`; `SPP_LIVE=` no longer breaks collection | 3 files | `tests/test_config_env_flag.py` — **7 tests** |

### What the review had wrong, found only by going into the code

1. **The stub citations were malformed, not merely unmarked.** `kg:hetionet` with no metaedge code does not match `schema.citation()`'s own format (`kg:hetionet:DpS`), and `TREATED_BY` / `CAUSES_AE` / `ASSOCIATED_PATHWAY` are not Hetionet rel types at all. `TREATED_BY` **is** real — in the *owned* graph (`knowledge/ontology.py:40`). So the stub was mixing both vocabularies in one edge list, which is precisely the failure `CLAUDE.md:60` warns about. Marking the edges alone would not have fixed it.

2. **`build_grounding` renders `cite` but not any flag**, so an edge-level marker never reached the model. The consumer was the fix point, not the producer — the review's own rule, applied to its own change.

3. **The committed fixtures were already stale before this session touched anything.** `ledger_schema_version` was added to the ledger snapshot nested *inside* the counterfactual artifact in `52e7168` — the same commit that wrote the fixture — and the fixture shipped without it, invisible through four releases. Cause: `test_the_counterfactual_fixture_still_matches_the_api` compared **top-level keys only**, and `export_schema.py` does not run in CI. Fixed by a recursive shape guard over all six fixtures (`TestRecursiveShapeGuard`, synthetic canary, because a historical one would pass vacuously after regeneration) plus a CI comment naming where the guard lives.

4. **`load_all_packs(directory)` ignored `directory` whenever the cache was warm** — a single global `_CACHE`, so the parameter was honoured cold and silently ignored on every later call. Discovered because the quotability canary needed a fitted pack in a temp directory and got the shipped `EXPERT_GUESS` one, returning `quotable: False` for a pack that *was* fitted: **a canary that reads the wrong artifact is a canary that cannot fail.** Cache is now keyed by directory, with `clear_pack_cache()` and three tests. Same species as the repo's "position as a key" bug class.

### The eighth instance: the link checker was narrower than its guarantee

`tracker/build_tracker.py:48` matched **only `.md`** targets, so two real links in
the knowledge base were never validated: `concepts/instrument-v2.md` →
`tests/eval/instrument_v2_gate.json`, and `index.md` → `../../tracker/tracker.html`.
The second is the sharp one — `tracker.html` is generated and gitignored, so for a
cloner the OKF's pointer to the canonical steering surface was dead **and the
checker was blind to it by construction**. `MD_LINK` is replaced by `ANY_LINK`:
every relative link is existence-checked, and only `.md` targets become graph
edges (a non-md file cannot be a node, and inventing one would be its own lie).

Verified by probe rather than by assertion: a temporary concept with one dead
`.json`, one dead `.md` and one live `.json` reports exactly the two dead ones and
exits 1; deleting it returns exit 0. An earlier mutation attempt (renaming
`tracker.html` away) tripped a different existence guard and proved nothing about
the scan — which is itself the lesson of §9.

### Two holes recorded rather than closed

- **`PriorPack.unquotable()` does not read `derivations.provenance`**, which carries its own `Provenance` and is `EXPERT_GUESS` in every shipped pack — the barrier-severity magnitudes that drive burden. So a pack with every marginal fitted reports `quotable: True` while the numbers turning barriers into a burden score remain judgement. Pinned by `test_derivations_are_not_covered_by_the_quotability_gate`; closing it is a decision about what a finding *is*, not a fix to slip into Phase B's stride.
- **`Population` is hand-written in `ui/src/lib/preview.ts`**, a *third* contract beside `artifacts.ts` and the route schemas — because the routes return bare `dict` and there is no response model to codegen from. That is A2b, deferred by the owner. Until it lands, a change to `/scenario/preview` must be made in three places; the fixture-shape guard covers the server side and `app-fetch.test.tsx` covers the reader.

### The mutation checks, because a green suite proves nothing about a new test

- **A2a:** `App.tsx` reverted to `data.unquotable` → **4 of 6** `app-fetch` tests fail, and **Playwright spec 1 fails against the live server**. Restored → 33 vitest + 3 E2E green.
- **A4:** the banner's amber is asserted as `toHaveCSS("border-left-color", "rgb(138, 90, 0)")`, so a banner rendered in the ledger's red would fail it — the design rule that red means never-quote and nothing else is now machine-checked, not stylistic.
- **A1:** five refusal canaries move one ledger field each (prompt version, digest, `num_ctx`, seed, bundle count) and require the guard to name it.
- **A3:** eight canaries run the *shipped* values through the new validators and require rejection; `test_the_old_grounding_block_would_have_been_unmarked` renders them through the current renderer.
- **Config:** `SPP_LIVE=maybe` must still raise, so the empty-string tolerance did not become a swallow.
- **Fixtures:** `test_a_removed_nested_path_is_found_by_descent_and_missed_from_the_top` asserts `set(stale) == set(live)` **passes** while the recursive diff fires — the blind spot demonstrated, not described.

### Self-corrections during the work, recorded rather than hidden

- I wrote `quotable: False` as a literal in `population_provenance`, then caught that it would go stale the moment Phase B ships a calibrated pack — **the exact bug this change exists to close**, in the code written to close it. Now derived from `pack.unquotable()`, with a canary.
- I documented `OLLAMA_BASE_URL` in `.env.example`; the field is `ollama_host`, and `extra="ignore"` means my own example would have been silently ignored. Caught by reading `config.py` after writing it.
- I removed `export PYTHONPATH=src` from the README, then found the README's *second* example (a heredoc) needs it. Restored, with the note phrased to say what needs it and what doesn't.
- Three test bugs of my own: `load_all_packs` is keyed by condition not pack name; `/counterfactual/run` 400s without a mutation; `unquotable()` is a method, not a property. All three failed loudly rather than silently, which is the point of writing the tests before declaring the fix done.

## 11. What the review wrote, and what a cloner receives

Six review files plus four test/CI files. The OKF is tracked as of this session
(`.gitignore` carve-out removed on the owner's A9 decision), so every row below is
now visible to anyone who clones:

| File | Tracked? | Contents |
|---|---|---|
| `docs/AUDIT_METHOD_2026-11.md` | ✅ | The graph shape, the four node contracts, precedence order, verification rules, **side effects**, where the subagents and the orchestrator were wrong, and the owner's six corrections |
| `docs/AUDIT_EVIDENCE_2026-11.md` | ✅ | This file — every internal claim, MEASURED or INHERITED, with the reproducing command; §9 is what Phase A changed |
| `docs/AUDIT_MARKET_2026-11.md` | ✅ | Competitors, regulation, prices, monetisation, the demand science, every URL, §8's thin-evidence list, and the downgraded negative controls |
| `docs/AUDIT_PLAN_2026-11.md` | ✅ | The owner's gate, Phases A/B/C, the two-window demand probe, what is frozen |
| `docs/okf/concepts/verification-locus.md` | ✅ (was ignored) | The one rule explaining the defects, and its allocation consequence |
| `docs/okf/references/external-2026-11.md` | ✅ (was ignored) | The load-bearing external facts, condensed |

Plus: `tests/test_ledger_agrees_with_evidence.py` (19), `tests/test_stub_provenance.py` (22), `tests/test_population_provenance.py` (27), `tests/test_config_env_flag.py` (7), `ui/tests/app-fetch.test.tsx` (6), `TestRecursiveShapeGuard` in `tests/test_scenario_lab.py`, and `tests/fixtures/assumptions.json`.

**Correction to an earlier claim in this file.** The first draft said *"no existing
file's substance rewritten."* That stopped being true the moment Phase A ran:
`assumptions.py`, `graph/client.py`, `graphrag/grounding.py`, `api/main.py`,
`cohort/epidemiology.py`, `cohort/packs.py`, `config.py`, `App.tsx`,
`ProvenanceRail.tsx`, `styles.css`, `preview.ts`, `preview.test.ts`,
`record_narration.py`, `quickstart.py`, `export_schema.py`, `README.md`,
`.env.example`, `.gitignore`, `tests.yml` and the two OKF indexes were all
substantively edited. The claim is right about the *review* and wrong about the
*session*, which is a distinction worth stating rather than a sentence worth keeping.

**The asymmetry is deliberate and is itself a finding.** The four `docs/` files are visible to anyone who clones the 290 tracked files; the two OKF concepts are not, because `docs/okf/` is gitignored while `CLAUDE.md:16-18` calls it canonical for project status. So the review's *knowledge* is published and its *concept files* are not. That is A9's decision, and writing the files into the OKF rather than beside the audit was the honest way to expose the contradiction instead of routing around it.

**Two side effects on files I did not author,** both disclosed rather than smoothed:

1. `docs/okf/concepts/index.md` — I first wrote a row describing `instrument-v2.md` as "adopted, then superseded… see the file's own status note." **No such note exists.** The pointer was false, which is the defect class this whole review documents, so it was corrected to state the fact and label the file stale instead.
2. `docs/okf/references/index.md` — my first version put Hetionet, Synthea, ICH and Pew as rows in the *file* table, violating `SCHEMA.md` rule 5 (that table lists files in the folder). Rewritten with a separate section and a stated rule for when a reference earns its own file.

## 12. What this session did not do

- **No tracker grade was moved.** `tracker_state.json` still says `lastModified: 2026-08-25`, S3's tasks J and K are still `backlog/0`, KR1.3 is still 0.8 against a 0.6724 reading, and the nine Synthea decisions are still absent. That is the owner's item 2 and it is deliberately not started here — the sync is a single-writer step, not a side effect of fixing code.
- **No commit, push, tag, or network write.** Nothing was staged. No `SPP_LIVE=true` run, so no live model was called and no new evidence bundle was produced; every narration number in §2 is a reading of committed artifacts.
- **Phase A is not finished.** Done: A1, A2a, A3, A4, A6, C4, and the cheap first-run traps. Open: A2b (the deferred type-generation refactor), A5's `[build-system]` / console scripts / Dockerfile / SPA-served-from-FastAPI, A7's `print()` → `logging`, and A9's remaining half (the four audit files are still untracked in git).
- **No subagent skeptic layer over the market brief.** The `market` node was verified for internal consistency and against my own reading of a few URLs; its competitor claims are single-sourced, and the sweep is not exhaustive by construction (the node hit a search rate limit and worked from primary sources). It is the weakest-verified part of this review and is marked accordingly in [AUDIT_MARKET_2026-11.md](AUDIT_MARKET_2026-11.md).
- **No demand measurement.** The probe is registered, not run. Nothing here establishes that anyone wants the product. What it establishes is narrower and survives the owner's correction: engineering quality has not been the constraint for anyone in this class, and the priors are still `EXPERT_GUESS` on all 51 shipped marginals while 55.7% of commits went to measuring the instrument. Whether that is a market opportunity or a well-built research artefact is what C0 and the two-window gate are for.
