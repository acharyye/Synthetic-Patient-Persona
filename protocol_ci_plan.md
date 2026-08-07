# Plan: Protocol CI — "the gate you can't ship past"

## What this is

Turn the existing counterfactual engine into a CI check for human-process designs.
Protocol/scenario definitions live in a repo. Every change to one triggers a CRN-paired
simulation against a pinned population and baseline. A retention regression is a
**failing check** with a flip table in the PR comment:

> ❌ Retention regression vs baseline: −2.3pp (7 flips, sign-stable across seeds)
> Flipped: type-2-diabetes-s42-0007 (dropped at visit 4, burden.travel), …
> Attribution: rule `hba1c_max` +34% of new screen-fails.

Nothing here is new simulation capability. It is packaging: the `POST /counterfactual/run`
artifact + evidence-bundle discipline, re-shaped as (1) a CLI, (2) a baseline contract,
(3) a diff verdict, (4) CI glue. Do not touch the simulation core.

## Non-negotiable constraints (inherited from the repo — read CLAUDE.md first)

- Simulate/narrate split holds: this feature is **pure core**. The
  `TestNoLLMInTheCore` pattern applies — CI runs must never call the LLM adapter.
  Add the equivalent raise-test for the CI path.
- CRN discipline: baseline and candidate run under identical seeds; visit_id
  identity keying is what makes the flip table signal. Never compare across seeds
  except for sign-stability.
- Every verdict artifact stamps: master seed, pack id+version, cohort size,
  scenario hashes (baseline + candidate), ledger snapshot + `ledger_schema_version`,
  engine version. A verdict that can't name its configuration is not evidence.
- Pre-registered thresholds: pass/fail bars live in a committed config
  (`ci/gates.json`), never in code, never chosen after seeing numbers. Same rule
  as `pass_bars.json`.
- All new logic gets tests in the existing suites. Golden-file reading rule applies.

## Architecture (4 pieces, in build order)

### 1. Scenario-as-file + content hash (`src/spp/ci/scenario_file.py`)

- Canonical on-disk format for a scenario: YAML or JSON containing rules (DSL text),
  timeline (visit schedule with stable `visit_id`s), pack reference, cohort size, seed.
  Most of this exists as API request models — reuse those Pydantic models, add a
  file loader with the same validation path (lenient parse is for the editor;
  the CI loader is **strict**: any rule that doesn't parse → hard error, not
  "score the subset").
- `scenario_hash()`: canonical serialization (sorted keys, normalized whitespace
  in DSL text) → sha256. Two files meaning the same scenario must hash equal;
  hash goes in every verdict.
- Tests: round-trip load/dump, hash stability under key reordering, strict-mode
  rejection of a half-valid file (contrast with the editor's lenient path — put
  the comment there).

### 2. Baseline contract (`src/spp/ci/baseline.py`)

- `spp ci baseline <scenario-file>` runs the simulation and writes
  `ci/baseline.json`: scenario hash, config stamps, retention aggregate, per-persona
  outcome map keyed by (globally unique) persona ID, survival curve points,
  attribution table. This is a committed file — the repo's pinned expectation.
- `require_compatible(baseline, candidate_config)`: raises unless pack id+version,
  seed, cohort size, and engine schema version match. A baseline from a different
  population is not a baseline; refuse loudly (IncompatibleEventLog pattern).
- Baseline regeneration is an explicit command with a printed diff summary —
  the golden-file reading rule, applied here: baseline diff + contract green means
  intended redesign; baseline diff you didn't expect means investigate.
- Tests: byte-determinism of baseline for fixed inputs (reuses residency-identity
  proof), incompatibility raises on each mismatched field.

### 3. Verdict engine (`src/spp/ci/verdict.py`)

- Input: baseline + candidate scenario file. Runs candidate under baseline's exact
  seeds (CRN), computes:
  - retention delta (pp),
  - flip table (persona ID, direction, divergence event index, exit reason) —
    reuse the existing paired-diff code path, do not reimplement,
  - eligibility Shapley delta per rule (existing closed-form),
  - sign-stability: one extra run under the committed second seed
    (existing seed-1234 pattern); report `[n_flips_seed_a, n_flips_seed_b]`
    and whether direction agrees.
- Gate evaluation from `ci/gates.json`. Ship with:
  ```json
  {
    "retention_drop_pp": {"fail": 1.0, "warn": 0.25},
    "require_sign_stability_for_fail": true,
    "max_new_sole_reason_share": {"warn": 0.15}
  }
  ```
  Semantics: FAIL only when drop exceeds threshold AND sign-stable (a
  non-sign-stable drop is WARN — "possible regression, below resolution").
  Never fail on a delta the paired design can't distinguish from noise.
- Output: `verdict.json` (machine) + `verdict.md` (human, renders as PR comment) —
  verdict, headline delta, flip table (top N by divergence, full table linked),
  attribution waterfall, config stamps, and the paired-design one-liner under the
  flip count (same rule as the HTML report: nobody reads it as a difference of
  aggregates).
- Tests: golden verdict for a fixture (baseline, candidate) pair; gate boundary
  tests at exactly-threshold; sign-instability downgrades FAIL→WARN; no-op
  candidate → PASS with zero flips (the existing no-op fork test, promoted).

### 4. CLI + CI glue (`src/spp/ci/cli.py`, `.github/workflows/protocol-ci.yml`, `action.yml`)

- `spp ci check <scenario-file> --baseline ci/baseline.json --gates ci/gates.json`
  → writes verdict files, exit code 0/1 (WARN exits 0 with annotation).
- GitHub Action (composite): checkout, install (uv), run check on changed scenario
  files (detect via `git diff --name-only` against base ref, filter by path glob
  from config), post/update a single sticky PR comment with `verdict.md`
  (marker comment + update-in-place; never spam one comment per push).
- Also emit GitHub annotations (`::error file=...`) pointing at the scenario file.
- Dogfood: add a `protocols/` dir to this repo with one real scenario + committed
  baseline, and wire the workflow so the repo gates itself. The demo IS the repo's
  own green check turning red on a bad PR.
- Tests: CLI exit codes per verdict; changed-file detection unit-tested against a
  fixture git log is overkill — test the path-filter function only, trust git.

## Vertical slices (one per Claude Code session)

1. **S1:** scenario_file.py + hashing + strict loader + tests. Exit: round-trip +
   hash-stability tests green.
2. **S2:** baseline.py + CLI `baseline` subcommand + determinism/compat tests.
   Exit: committed `ci/baseline.json` for the dogfood scenario, regenerated twice,
   byte-identical.
3. **S3:** verdict.py reusing paired-diff + Shapley + gates + golden verdict tests.
   Exit: no-op → PASS, drop-visit-3 fixture → expected flips, boundary tests green.
4. **S4:** CLI `check` + verdict.md renderer + tests. Exit: `spp ci check` on the
   dogfood pair produces the exact committed golden verdict.md.
5. **S5:** GitHub workflow + sticky comment + annotations + dogfood PR. Exit: a
   deliberate bad PR against this repo shows a red check with the flip table in
   the comment. Screenshot goes in RELEASE notes.

## Explicitly out of scope (do not build)

- No LLM/narration anywhere in this path (enforced by test, not comment).
- No mid-trajectory forking, no multi-scenario matrix runs, no dashboard — the PR
  comment is the UI.
- No GitLab/Bitbucket support yet; keep the core CLI host-agnostic so it's a thin
  adapter later.
- No auto-fix suggestions in the comment (attribution names the rule; stop there).
- No new statistics: if a comparison isn't expressible as CRN-paired flips +
  existing attributions, it doesn't go in the verdict.

## Definition of done

- Repo gates itself: real workflow, real baseline committed, one red-check demo PR.
- `verdict.json` carries every stamp listed in constraints; a stranger can re-run
  `spp ci check` from the stamps alone and get byte-identical verdict.json.
- All suites green; new tests live in the main Python suite (target: every gate
  branch covered, golden verdict pinned).
- CLAUDE.md gains a section: CI path is pure-core, baseline reading rule, gates
  are pre-registered.
