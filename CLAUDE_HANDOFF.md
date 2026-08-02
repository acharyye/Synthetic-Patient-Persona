# Claude Handoff Brief

## Project summary
This project is a synthetic persona platform for scenario testing, stakeholder simulation, and design exploration. It creates synthetic personas, evaluates scenario rules against them, estimates participation burden, and lets a grounded conversational agent respond as that persona.

## Core idea
The product is not a medical decision tool and not a regulatory evidence system. It is a design and simulation system for exploring how realistic personas might respond to a proposed experience or workflow.

## What the system already does
The current version includes:
- structured persona profiles with demographics, condition, stage, biomarkers, medications, adherence, social context, and journey details,
- seeded cohort generation from condition-based priors,
- a safe rule language for scenario criteria,
- eligibility screening with per-rule attrition and a sole-reason metric,
- participation burden scoring,
- a FastAPI interface for cohort generation, stress testing, and persona interaction,
- and offline fallback behavior.

## Main modules
- src/spp/schemas/patient_dna.py: core persona profile schema
- src/spp/cohort/epidemiology.py: condition priors
- src/spp/cohort/generator.py: cohort generation logic
- src/spp/protocol/eligibility.py: safe scenario rule evaluation
- src/spp/protocol/burden.py: burden scoring and persona interviews
- src/spp/persona/engine.py: persona response engine
- src/spp/graph/client.py and src/spp/graphrag/: grounded knowledge retrieval
- src/spp/api/main.py: API surface

## Product ambition
The next-level version should feel less like a prototype and more like a serious simulation platform. The strongest direction is an offline-first, explainable, grounded system where personas behave like evolving agents with goals, constraints, and barriers.

## Key constraints
- Keep the system offline-first.
- Keep the system grounded in structured knowledge.
- Keep scenario rules safe and parsed rather than executed dynamically.
- Keep the product framing clear: design support, not medical or regulatory claims.

## Important caveats
- Adherence is modeled heuristically, not measured from real data.
- Epidemiology priors are approximate and should not be treated as findings.
- The current graph layer is still a scaffold and not yet a full reasoning engine.

## Best roadmap
1. Improve persona realism.
2. Improve the burden and scenario reasoning layer.
3. Upgrade grounding and retrieval quality.
4. Add better dashboards, comparisons, and exportable reports.
5. Evolve the system into a more modular and scalable simulation platform.

## Brainstorm prompt
Use this prompt with a stronger model:

"Take this repository as the starting point for a next-generation synthetic persona simulation platform. Preserve the offline-first, grounded, explainable, and design-oriented framing. Propose a strong product vision, a modular architecture, a phased implementation roadmap, key technical choices, and concrete next steps for turning this into a much more advanced and differentiated system. Keep the focus on realism, scalability, product value, and long-term extensibility."
