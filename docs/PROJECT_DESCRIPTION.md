# Project Description

Synthetic Patient Persona is a GraphRAG-grounded conversational patient digital twin for trial-design and patient-journey work. It gives product teams, clinicians, and researchers a way to explore how plausible synthetic personas would react to a proposed protocol, workflow, or experience.

The product is intentionally framed as design and stakeholder simulation. It is not medical advice, not a regulatory evidence system, and not a statistical virtual control arm.

## What It Does
- Generates synthetic personas from seeded, condition-specific priors.
- Screens cohorts against protocol criteria with per-rule attrition and sole-reason analysis.
- Estimates participation burden and highlights the highest-risk eligible personas.
- Lets a persona answer in character with grounded citations.
- Supports protocol stress tests, counterfactual comparisons, panel-style interviews, and a Scenario Lab UI.

## Core User Flows
1. Create or inspect a synthetic cohort for a condition.
2. Test inclusion and exclusion criteria against that cohort.
3. Identify which criteria are excluding the most personas.
4. Estimate how hard participation would be for the remaining personas.
5. Ask those personas what the experience would feel like.
6. Compare scenario changes with deterministic counterfactuals.

## Product Boundary
The deterministic simulation core decides what happens. The language model only narrates the outcome after the core has already decided it. That separation is central to the project:
- simulation is seeded, replayable, and regression-testable,
- narration is grounded and citation-checked,
- offline operation is always available through deterministic fallbacks.

## Primary Outputs
- FastAPI endpoints for cohort generation, stress testing, simulation, narration, and analysis.
- A Scenario Lab front end for live eligibility previews and shareable scenario URLs.
- Offline quickstart and reproducible demo scripts.
- Evidence bundles, test fixtures, and generated artifacts for evaluation and review.

## Audience
- Product and clinical design teams exploring study or journey concepts.
- Internal stakeholders reviewing scenario viability.
- Developers extending the simulation, grounding, or narration stack.

## Related Documents
- [Architecture](../ARCHITECTURE.md)
- [Repository guide](REPO_GUIDE.md)