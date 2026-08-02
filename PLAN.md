# Synthetic Patient Persona - Current Plan

## Product goal
Build a synthetic persona platform for scenario testing, stakeholder simulation, and design exploration.

The system should help teams answer four questions:
- What kind of personas exist in a synthetic cohort?
- Which scenario rules would exclude them?
- Which personas would face high participation burden?
- What would those personas say about the experience?

This is a design and simulation tool. It is not a medical decision system and not a regulatory evidence system.

## What exists now
The project already has a working offline-first scaffold.

### Built so far
- A structured persona profile with demographics, condition, stage, biomarkers, medications, adherence, social context, and journey details.
- A cohort generator that creates synthetic personas from condition-based priors and seeded reproducible panels.
- A rule language for scenario criteria such as age >= 50, stage in {moderate, advanced}, CKD, and biomarkers.HbA1c_pct >= 7.5.
- An eligibility screening system with per-rule attrition and a sole-reason metric.
- A burden model that estimates how demanding a scenario would be for each persona.
- A FastAPI interface for cohort generation, stress testing, and persona interaction.
- Offline fallback behavior so the system still runs without external services.
- A graph client that can operate in offline stub mode and, when live, connect to a graph-backed environment with provenance-aware edges.

## Current maturity
This is an MVP prototype. It is useful for demos, product exploration, and internal design work.

## Main constraints
Keep these rules while improving the system:
1. Offline-first behavior is required.
2. The system should stay grounded in structured knowledge.
3. Scenario rules must be parsed safely and should not use eval.
4. The system should remain useful even when no external services are available.
5. The product framing should stay clear: it supports design thinking, not medical or regulatory claims.

## Current technical stack
- Python 3.11+
- Pydantic v2
- FastAPI
- pytest
- optional LLM integration
- optional graph database integration

## Known gaps
The current version is still a scaffold. The biggest gaps are:
- more realistic persona generation from real data,
- stronger grounding and retrieval,
- more advanced scenario modeling,
- better long-term persona behavior.

## Important caveats
- Adherence is modeled by heuristics, not measured data.
- Epidemiology priors are approximate and should not be presented as real findings.
- The system is for exploration and design support, not final evidence claims.
- The current graph layer is still a scaffold and is not yet a full knowledge-graph reasoning engine.

## Suggested next milestones
### Milestone 1: improve realism
- make personas more believable,
- improve their context and behavior,
- improve burden explanations.

### Milestone 2: connect to real data
- add stronger data ingestion,
- use richer graph knowledge,
- connect to more realistic scenario data.

### Milestone 3: improve reasoning quality
- improve retrieval,
- improve explainability,
- improve scenario comparison outputs.

### Milestone 4: make it product-ready
- add dashboards,
- add scenario comparison views,
- add exportable reports,
- improve user workflows.

## Best next direction
The strongest next version would be an offline-first, explainable, grounded simulation platform where synthetic personas behave like evolving agents with goals, constraints, and barriers.

## Prompt for deeper brainstorming
Use this prompt with a stronger model:
"Take the current project as a starting point and propose a next-generation synthetic persona simulation platform. Focus on product vision, architecture, modular technical design, realism, explainability, roadmap, and implementation priorities. Keep it offline-first, grounded, practical, and suitable for future development through an AI coding workflow."
