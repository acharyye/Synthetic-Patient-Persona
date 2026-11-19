---
type: Decision
title: Ground on nothing rather than on the wrong thing
description: Conditions absent from Hetionet are not aliased to a near neighbour — resolve() returns None and the persona grounds on nothing.
resource: ../../../src/spp/graph/schema.py
tags: [decision, grounding, knowledge-graph, hetionet]
timestamp: 2026-08-17T00:00:00Z
---

# Ground on nothing rather than on the wrong thing

**Decision:** when a condition has no Hetionet node, `resolve()` returns `None` and the persona
grounds on nothing. It is **not** aliased to a clinically adjacent disease.

## Context

Hetionet v1.0 (CC0) contains only **137 diseases**. The default load is the persona-relevant
metaedge slice — 47,031 nodes / 277,997 edges — not the full 2.25M. Re-running is idempotent
(MERGE on Hetionet ids).

`heart failure` is not among the 137.

## Why

Aliasing to a near neighbour produces a persona that speaks fluently and cites real edges — for the
wrong disease. That failure is **invisible to the reader**, because the output has every surface
marker of being grounded. Grounding on nothing is visibly empty; grounding on the wrong thing is
confidently wrong.

`CONDITION_ALIASES` therefore maps only **shorthand to spelled-out Hetionet names** (COPD, T2D) —
never one disease to a different disease.

## Consequence

`graph/schema.py` is the single source of truth for labels, relationship types and metaedge codes.
The loader, the traversals and the Cypher validator all read it. **If they disagree, the system cites
edges that do not exist** — which is the same failure in a different costume.

---
Related: [Simulate with models, narrate with LLMs](../architecture/core-narration-split.md), [state-citation](../concepts/state-citation.md)
