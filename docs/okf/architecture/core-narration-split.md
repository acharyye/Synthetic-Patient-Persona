---
type: Architecture
title: Simulate with models, narrate with LLMs
description: The deterministic core decides what happens; the narration layer only verbalises it and never makes a decision.
resource: ../../../CLAUDE.md
tags: [architecture, invariant, llm, determinism]
timestamp: 2026-08-17T00:00:00Z
---

# Simulate with models, narrate with LLMs

The one architectural rule of SPP. Everything else in the system is downstream of it, and most
design questions resolve by asking which side of the line the change falls on.

## The split

| Layer | Decides | Implementation |
|---|---|---|
| **Deterministic core** | *What happens* — eligibility, burden, dropout, state transitions | Pure Python, seeded, no LLM calls, fully replayable |
| **Narration layer** | *How it feels* — interview answers, quotes | Verbalises decisions the core already made; **never makes one** |

## The test

> If you find yourself wanting an LLM call to change simulation state, the design has gone wrong.

## Why it is worth protecting

Three consequences follow directly, and all three are lost the moment the line is crossed:

1. Simulations run in seconds with **zero LLM calls**.
2. A persona **cannot hallucinate a decision** inconsistent with its own state.
3. The core is **exactly regression-testable** — byte-exact goldens are possible at all.

The citation work in [state-citation namespaces](../concepts/state-citation.md) exists because
narration must be able to *point at* core state without ever *changing* it.

## Data flow

```
Synthea/MIMIC/registries ─▶ ingest ─▶ Patient DNA (Pydantic)
Hetionet/PrimeKG/Open Targets ─▶ ingest ─▶ Neo4j KG
Patient DNA + question ─▶ GraphRAG (retrieve subgraph + citations)
        ─▶ Persona engine (LLM, conditioned + constrained)
        ─▶ FastAPI: /persona/interview · /cohort/generate · /protocol/stress-test
```

---
Related: [state-citation](../concepts/state-citation.md), [pre-registration](../concepts/pre-registration.md), [Ground on nothing rather than the wrong thing](../decisions/hetionet-no-alias.md)
