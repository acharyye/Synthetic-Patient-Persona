# Repository Guide

This file is the file-by-file map for the repository. It is meant to make the codebase easy to navigate and to show where each major capability lives.

## Top-Level Files
- `README.md` - user-facing overview, quickstart, and demo instructions.
- `ARCHITECTURE.md` - technical architecture and system boundaries.
- `CLAUDE.md` - long-form project context for the coding agent.
- `CLAUDE_HANDOFF.md` - shorter handoff summary of the project state.
- `PLAN.md` - working product and implementation plan.
- `RELEASE.md` - version framing and release notes.
- `spp_vision_and_roadmap.md` - roadmap and longer-term product framing.
- `pyproject.toml` - Python package metadata and test configuration.
- `requirements.txt` - Python dependencies.
- `docker-compose.yml` - local Neo4j stack for live graph mode.

## Data
- `data/knowledge/core.json` - owned knowledge-graph substrate used by retrieval and grounding.
- `data/prior_packs/*.json` - condition prior packs for cohort generation.
- `data/.gitkeep` - keeps the data directory in the repository.

## Scripts
- `scripts/quickstart.py` - offline end-to-end demo covering interview, cohort generation, stress testing, and burden analysis.
- `scripts/build_knowledge_pack.py` - builds knowledge-pack artifacts.
- `scripts/calibrate_hazard.py` - calibrates the retention hazard model.
- `scripts/export_prior_packs.py` - exports prior-pack data.
- `scripts/export_schema.py` - exports artifact schemas for the UI.
- `scripts/record_narration.py` - records or validates narration evidence and cassettes.

## Backend Package: `src/spp`

### Package root
- `src/spp/__init__.py` - package marker.
- `src/spp/config.py` - environment and settings handling.
- `src/spp/assumptions.py` - assumption ledger for heuristics, thresholds, and model settings.

### API
- `src/spp/api/main.py` - FastAPI application and all public HTTP endpoints.
- `src/spp/api/__init__.py` - package marker.

### Schemas
- `src/spp/schemas/patient_dna.py` - core persona schema.
- `src/spp/schemas/migrations.py` - schema migration helpers.
- `src/spp/schemas/__init__.py` - schema exports.

### Foundation
- `src/spp/foundation/events.py` - event sourcing primitives.
- `src/spp/foundation/ledger.py` - assumption ledger implementation.
- `src/spp/foundation/llm.py` - model-call abstraction and offline fallback behavior.
- `src/spp/foundation/rng.py` - seeded random-number scope helpers.
- `src/spp/foundation/store.py` - persistence/store utilities.
- `src/spp/foundation/versioning.py` - version and compatibility helpers.
- `src/spp/foundation/__init__.py` - foundation exports.

### Cohort
- `src/spp/cohort/epidemiology.py` - condition-based priors.
- `src/spp/cohort/generator.py` - synthetic cohort generation.
- `src/spp/cohort/correlation.py` - latent correlation / copula handling.
- `src/spp/cohort/packs.py` - prior-pack loading and validation.
- `src/spp/cohort/residency.py` - cohort caching and residency identity.
- `src/spp/cohort/traits.py` - derived goals, constraints, and barriers.
- `src/spp/cohort/__init__.py` - cohort exports.

### Protocol
- `src/spp/protocol/eligibility.py` - safe criterion parsing and screening.
- `src/spp/protocol/lenient.py` - lenient parsing for live editor preview.
- `src/spp/protocol/burden.py` - participation burden scoring and interview ranking.
- `src/spp/protocol/attribution.py` - eligibility attribution and Shapley-style reporting.
- `src/spp/protocol/__init__.py` - protocol exports.

### Simulation
- `src/spp/simulation/schedule.py` - visit schedule construction.
- `src/spp/simulation/hazard.py` - retention hazard modeling.
- `src/spp/simulation/timeline.py` - event timeline helpers.
- `src/spp/simulation/survival.py` - survival and retention summaries.
- `src/spp/simulation/counterfactual.py` - fork-and-diff scenario comparisons.
- `src/spp/simulation/sensitivity.py` - assumption sensitivity analysis.
- `src/spp/simulation/report.py` - simulation report artifacts.
- `src/spp/simulation/__init__.py` - simulation exports.

### Knowledge — default path (`src/spp/knowledge/`)
The owned graph. Runs unless you configure otherwise; every citation in the
product resolves against it.
- `src/spp/knowledge/ontology.py` - owned ontology: node/edge kinds, traversal plan.
- `src/spp/knowledge/graph.py` - NetworkX-backed store, validated at load.
- `src/spp/knowledge/retrieval.py` - deterministic retrieval and the frozen
  `RetrievalResult` contract (returns fact ids, never prose).
- `src/spp/knowledge/__init__.py` - knowledge exports.

### Knowledge — optional Neo4j/Hetionet backend (`src/spp/graph/`, `src/spp/graphrag/`)
Same contract, larger graph, **not the default**. Breadth over defensibility;
needs Docker and a ~14 MB download.
- `src/spp/graph/client.py` - Neo4j client wrapper with offline stub behavior.
- `src/spp/graph/schema.py` - Hetionet labels, edge types, and metaedges.
- `src/spp/graph/__init__.py` - graph exports.
- `src/spp/graphrag/retriever.py` - two-layer retrieval orchestration.
- `src/spp/graphrag/grounding.py` - grounding block construction.
- `src/spp/graphrag/cypher_guard.py` - Cypher safety validation.
- `src/spp/graphrag/__init__.py` - GraphRAG exports.

### Ingest
- `src/spp/ingest/kg_loader.py` - loads the knowledge graph.
- `src/spp/ingest/synthea_loader.py` - ingest path for synthetic EHR inputs.
- `src/spp/ingest/__init__.py` - ingest exports.

### Narration
- `src/spp/narration/interview.py` - grounded interview flow.
- `src/spp/narration/panel.py` - panel and focus-group narration.
- `src/spp/narration/room.py` - interview-room question selection and fact click-through.
- `src/spp/narration/prompt.py` - prompt assembly.
- `src/spp/narration/cassette.py` - recorded narration cassettes.
- `src/spp/narration/citations.py` - citation validation and rendering.
- `src/spp/narration/structured.py` - structured response decoding and rendering.
- `src/spp/narration/evaluation.py` - narration evaluation harness.
- `src/spp/narration/bundle.py` - evidence bundle assembly.
- `src/spp/narration/sampling.py` - seeded narration sampling helpers.
- `src/spp/narration/__init__.py` - narration exports.

### Persona
- `src/spp/persona/engine.py` - persona response engine.
- `src/spp/persona/prompts.py` - persona prompt templates.
- `src/spp/persona/__init__.py` - persona exports.

### Reporting
- `src/spp/report/compare.py` - cohort comparison helpers.
- `src/spp/report/diffwalk.py` - flip-table and diff traversal utilities.
- `src/spp/report/html.py` - HTML artifact rendering.
- `src/spp/report/studio.py` - Scenario Studio views and marginal comparisons.
- `src/spp/report/__init__.py` - report exports.

## UI: `ui`
- `ui/index.html` - Vite entry HTML.
- `ui/package.json` - UI package metadata and scripts.
- `ui/playwright.config.ts` - Playwright configuration.
- `ui/tsconfig.json` - TypeScript configuration.
- `ui/vite.config.ts` - Vite dev-server config and API proxying.
- `ui/src/main.tsx` - React entry point.
- `ui/src/App.tsx` - Scenario Lab shell.
- `ui/src/styles.css` - UI styling.
- `ui/src/components/` - Scenario Lab UI components.
- `ui/src/lib/` - client-side state, preview, and URL helpers.
- `ui/src/types/` - generated artifact types.
- `ui/e2e/` - Playwright end-to-end tests.
- `ui/tests/` - Vitest component and preview tests.

## Tests
- `tests/test_*.py` - backend regression, property, and contract tests.
- `tests/eval/` - narration and retrieval evaluation inputs.
- `tests/fixtures/` - shared JSON fixtures for backend and UI tests.
- `tests/golden/` - committed golden outputs.

## Practical Workflow
1. Use `scripts/quickstart.py` for the fastest offline smoke test.
2. Use `uvicorn spp.api.main:app --reload --app-dir src` for the API.
3. Use `cd ui && npm run dev` for the Scenario Lab.
4. Use `pytest` and `cd ui && npm test` before changing behavior.
5. Use `cd ui && npm run e2e` for the three killer interactions.

## Reading Order
If you are new to the repo, read these in order:
1. `README.md`
2. `docs/PROJECT_DESCRIPTION.md`
3. `ARCHITECTURE.md`
4. `src/spp/api/main.py`
5. `scripts/quickstart.py`
