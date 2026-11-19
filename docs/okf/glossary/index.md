---
type: Index
title: Glossary
description: Terms and definitions — Patient DNA, battery, bar, take, bundle.
tags: [glossary, index]
timestamp: 2026-11-19T00:00:00Z
---

# Glossary

Terms and definitions — Patient DNA, battery, bar, take, bundle.

| File | Description |
|---|---|
| _(empty — link new concepts here)_ | |

## Terms without a file of their own

Short enough to define here. A term earns its own file when it needs more than two sentences.

| Term | Meaning |
|---|---|
| **Patient DNA** | The structured persona profile (`schemas/patient_dna.py`) that every simulated decision and every narrated sentence is conditioned on. |
| **Battery** | The fixed 30-case question set (5 conditions × 6 question tags) the narration layer is scored on. |
| **Take** | One recorded prompt → response exchange, stamped with model digest, prompt version and sampling. |
| **Cassette** | The committed set of takes that passed the citation gate; CI replays it instead of calling a model. |
| **Quarantine** | Responses that failed the gate. Never replayed; they are the compliance dataset. |
| **Bar** | A pass threshold registered in `tests/eval/pass_bars.json` before any live run. |
| **Bundle** | The archive of one live run under `evidence/<release>/<timestamp>/`, read canary → takes → quarantine → aggregates → adjudication. |
| **Canary** | A deliberately degraded configuration the eval must score worse, proving the instrument can fail. |
| **Flip table** | The personas whose outcome changed between two CRN-paired runs — the primary result of any counterfactual. |
| **Prior pack** | `data/prior_packs/<condition>.json`: the population's marginals, correlations and per-entry provenance. |
| **Provenance kind** | What sort of claim a pack number is: expert guess, Synthea-calibrated, or fitted to customer data. Only the last is quotable. |

Conventions: [../SCHEMA.md](../SCHEMA.md) · Template: [../_TEMPLATE_concept.md](../_TEMPLATE_concept.md) · Entry point: [../index.md](../index.md)
