# Synthetic Patient Persona - Architecture

## Purpose
The system simulates synthetic personas as grounded conversational agents. It combines a structured persona profile, scenario rules, burden analysis, and a conversational interface.

## Main idea
The architecture is built around three things:
- realism,
- scenario evaluation,
- grounded interaction.

## High-level flow
User request -> API layer -> scenario logic -> persona engine -> response

## Main modules
### 1. Profile layer
File: src/spp/schemas/patient_dna.py

This is the main data model. It stores persona details such as age, sex, condition, stage, biomarkers, medications, adherence, social context, and journey milestones.

### 2. Cohort layer
Files: src/spp/cohort/epidemiology.py and src/spp/cohort/generator.py

This layer creates synthetic personas from condition-based priors and produces a cohort. It is seeded and reproducible for scenario comparisons.

### 3. Protocol layer
Files: src/spp/protocol/eligibility.py and src/spp/protocol/burden.py

This layer parses scenario rules, evaluates them against personas, and estimates participation burden. It provides the main screening and attrition logic.

### 4. Persona layer
Files: src/spp/persona/engine.py and src/spp/persona/prompts.py

This layer turns persona context and retrieved knowledge into a grounded conversational response. It can run in offline stub mode or live mode depending on configuration.

### 5. Graph layer
Files: src/spp/graph/client.py, src/spp/graphrag/retriever.py, src/spp/graphrag/grounding.py

This layer retrieves structured knowledge and formats it into evidence that the persona engine can use. It supports offline stubs and live graph-backed behavior.

### 6. API layer
File: src/spp/api/main.py

This layer exposes the main endpoints for cohort generation, stress testing, and persona interaction. It also surfaces protocol field syntax and disclaimer information.

## Core data flow
### Cohort generation
1. A condition is provided.
2. The generator uses priors to create a persona.
3. The persona is stored as a structured profile.
4. The system returns a cohort.

### Scenario evaluation
1. A set of scenario rules is provided.
2. The rules are parsed into structured objects.
3. Each persona is evaluated against the rules.
4. The system reports who passes, who fails, and why.

### Burden analysis
1. A persona profile is passed into the burden model.
2. The model estimates barriers such as transport, literacy, adherence, caregiving, and medication load.
3. A burden score and explanation are returned.

### Persona interaction
1. A persona profile and a user message are provided.
2. Relevant knowledge is retrieved.
3. The system builds a grounded prompt.
4. A persona-style response is returned.

## Runtime modes
### Offline mode
Default mode. The system uses deterministic stubs and still runs without external services.

### Live mode
Enabled when SPP_LIVE is true and credentials are available. The system can use LLMs and live graph access.

## Design principles
- Keep the persona profile as the source of truth.
- Keep grounding explicit.
- Parse rules safely.
- Keep logic usable without external services.
- Separate design support from evidence claims.

## Extension points
The current architecture is already structured for growth.
Possible future upgrades include:
- more realistic persona trajectories,
- richer graph retrieval,
- multi-agent interactions,
- better evaluation and benchmarking,
- a dashboard or UI layer.

## Best future direction
The next version should evolve into a more realistic, explainable, and modular simulation platform that can support scenario testing, workflow exploration, and product planning.

