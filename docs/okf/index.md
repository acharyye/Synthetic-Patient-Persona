---
okf_version: "0.1"
type: Knowledge Bundle
title: Synthetic Patient Persona (SPP) — Knowledge Base (OKF)
description: Open Knowledge Format knowledge base for the Synthetic Patient Persona project.
resource: https://github.com/akm/synthetic-patient-persona
tags: [spp, synthetic-persona, graphrag, okf]
timestamp: 2026-11-19T00:00:00Z
---

# Synthetic Patient Persona — Knowledge Base (OKF)

**Project:** Synthetic Patient Persona (SPP) · **Owner:** akm · **As of:** 2026-11-19

> Entry point of the knowledge base. Branch out from here (progressive disclosure).
> Conventions for new files: [SCHEMA.md](SCHEMA.md). Template: [_TEMPLATE_concept.md](_TEMPLATE_concept.md).

## What is SPP?

A GraphRAG-grounded, conversational patient digital twin for trial-design and patient-journey work.
An LLM answers *in character* as a plausible patient, constrained by a structured **Patient DNA**
profile and by facts retrieved from a biomedical **knowledge graph**, so it cannot drift into
clinically incoherent claims.

**Framing (load-bearing):** this is a design/ideation and stakeholder-simulation tool. It is **not**
regulatory evidence and **not** a statistical virtual-control-arm twin. That boundary belongs in code
comments and UI copy.

## Key facts

- **Purpose / scope:** scenario testing, stakeholder simulation, design exploration.
- **Current release:** v0.5 — the lever worked and the floor was missed (2026-08-25). See the
  [v4 reading](concepts/v4-reading.md).
- **In flight:** [Synthea calibration](concepts/synthea-calibration.md) of the prior packs. The
  loader joins a real export into patient records; the marginal derivation and the calibration runs
  do not exist yet. Narration and instrument work is frozen until a calibrated pack exists.
- **Last reviewed:** 2026-11-18 — `../AUDIT_PLAN_2026-11.md`, and the rule it distilled:
  [verification belongs where it is consumed](concepts/verification-locus.md).
- **Stack:** Python 3.11+, Pydantic v2, FastAPI, pytest, Neo4j (optional), optional LLM backend.
- **Offline-first:** `SPP_LIVE=false` returns deterministic stubs; the system stays useful with no
  external services.
- **Steering:** OKRs in the [Tracker](../../tracker/tracker.html) (`../../tracker/tracker_state.json`).

## Knowledge map

| Folder | Contents |
|---|---|
| [architecture/](architecture/index.md) | How the system is built — layers, data flow, the core/narration split |
| [glossary/](glossary/index.md) | Terms — Patient DNA, battery, bar, take, bundle |
| [runbooks/](runbooks/index.md) | Operational procedures — running it, recording a battery, releasing |
| [concepts/](concepts/index.md) | Domain concepts, metrics, findings |
| [decisions/](decisions/index.md) | Decision log — why something is the way it is |
| [references/](references/index.md) | External sources — Hetionet, Synthea, tickets, dashboards |

## The rules that keep being load-bearing

1. **[Simulate with models, narrate with LLMs](architecture/core-narration-split.md)** — the
   deterministic core decides *what happens*; the narration layer only says *how it feels*.
2. **[Ground on nothing rather than on the wrong thing](decisions/hetionet-no-alias.md)** —
   `resolve()` returns None instead of aliasing to a near neighbour.
3. **[Pre-register before recording](concepts/pre-registration.md)** — a prediction written after
   seeing the numbers is not a prediction.
4. **[Declare the environment, then stamp it](decisions/environment-tiers.md)** — every guarantee
   is real only in the environment that happened to exist, unless that environment is declared.

## Maintenance

This knowledge base is maintained **with the work** (conventions in [SCHEMA.md](SCHEMA.md)): on any knowledge-changing
task, update the affected file and bump its `timestamp`; link new concepts from the owning `index.md`.
Keep relative `.md` cross-references alive — no dead links.
