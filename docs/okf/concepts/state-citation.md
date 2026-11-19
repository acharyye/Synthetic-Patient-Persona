---
type: Concept
title: State-citation — the P/B/J/E id namespaces
description: Four id namespaces that let a persona cite its own declared state, not only retrieved graph knowledge. Built 2026-08-23, read 2026-08-24.
resource: ../../../src/spp/narration/state_facts.py
tags: [citation, grounding, v3, active-work]
timestamp: 2026-08-24T00:00:00Z
---

# State-citation — the P/B/J/E namespaces

**Status: built 2026-08-23 (task G), recorded and adjudicated 2026-08-24 (tasks H, I).**
The verdict and what it actually showed: [The v3 reading](v3-reading.md).

Until v3 a persona could cite **retrieved graph knowledge** (`F###`) but had no way to cite its
own **declared state**. Its circumstances — no car, a shift-work job, a diagnosis three years ago —
were in the prompt as prose with no id, so a sentence about them could not be `factual` without
breaking the citation contract. The hypothesis under test is that v2's `factual_fraction` collapse
on burden (0.667 → 0.400) and mitigation (0.933 → 0.443) *is* that gap.

## The four namespaces

| Prefix | Covers | Note |
|---|---|---|
| `P-` | Profile | `P-social_determinants.transport` — the surface is declared in `PROFILE_FIELDS` |
| `B-` | Derived barriers | `B-transport` — the id **is** the barrier name |
| `J-` | Journey milestones | `J-diagnosis` — what the battery grounds in today |
| `E-` | **Reserved** — simulation event-log entries | **Empty.** `derive_state_facts` takes no `PersonaState` |

Derivation is a pure function of the persona: `derive_state_facts(dna) -> StateCitations`, mirroring
`RetrievalResult` so the two halves compose into one decode enum. `build_prompt` offers them in an
**ABOUT YOU** block placed after GROUNDED FACTS, and `Prompt.allowed_state_ids` keeps the state half
separable by set membership rather than by re-parsing id strings.

## The three decisions that carry weight

**`B-<name>` must stay the barrier's name.** `traits.barrier_severity` derives `competing_care`, the
knowledge graph's `Barrier` node is keyed on that same string, and that shared identity is the whole
join between a *simulated* barrier and a *citable* fact. The slug function therefore preserves
underscores — a tidier `competing-care` would have quietly cut the join.

**The citable surface is declared, not emergent.** `PROFILE_FIELDS` lists it the way `TRAVERSAL_PLAN`
declares what the graph will walk. Biomarkers are deliberately outside it: a persona quoting a lab
value is making a clinical claim. A battery question that needs one is a **coverage finding to log**,
never a reason to widen the surface quietly.

**The surface is offered whole, not ranked against the question.** A relevance scorer for state would
be a second unevaluated variable inside a run whose entire design is one variable — the same reason
seeded fact-order permutation stays off for v3. Consequence to read carefully: state ids are now
**64% of the enum** (mean 28 state against 16 graph per battery case), so a rise in state citation
could be volume-driven. `f_recall_holds_independently` and the `state_citation_share` diagnostic are
what separate that from a real recovery. If v3 shows volume effects, the ranker gets its own paired
comparison.

## Why four and not three

Originally three, with `E-` covering journey milestones. Split into four (`c98cb19`) because of this
repo's own lesson about **artifacts acquiring semantics from their readers**.

An id namespace whose meaning changes later — `E-` meaning journey milestones in v3 cassettes and
event-log entries in v5 — makes **every v3 recording silently ambiguous** the day simulated personas
enter the battery carrying real logs, and forces click-through to disambiguate two provenance types
under one prefix. Four namespaces cost nothing under constrained decoding; ambiguity in a recorded
artifact cannot be repaired after the fact.

The emptiness of `E-` is asserted, not remembered: `tests/test_state_citation.py` fails if any
persona ever emits one. The consequence stands recorded rather than repaired — a question that wants
"you missed visit 3" has **no id** for an unsimulated persona.

## Measuring it: `state_coverage`

New metric, pre-registered floor **0.6**: the share of **circumstantial** segments carrying at least
one P/B/J id. It is what the recovery arm has to be caused *by* — `factual_fraction` rising without
state ids present is the over-correction signature, and no other metric can tell the two apart.

**Read 2026-08-24: 0.564, under the floor** — while burden and mitigation recovered and the
controls held. What that turned out to mean is *not* the relabelling the branch names; see
[The v3 reading](v3-reading.md).

Its denominator was operationalized on 2026-08-23, before any recording, and is
**kind-independent on purpose**: scoring only segments the model labelled `factual` would make the
metric blind to exactly the v2 pathology it exists to detect — a circumstantial claim relabelled
`feeling` to dodge a citation would leave the denominator instead of failing the numerator. It errs
toward *including*, which makes the bar harder rather than easier.

**The lever fires before the number counts.** `strip_state_ids` rebuilds the v2 configuration through
the same code path, and `run_canary` now refuses `sensitive` unless both the grounding lever and the
state lever move. Two readings stay separate: an axis nothing exercised is a finding about the
battery, a lever that will not move is a finding about the instrument.

## Click-through

`POST /room/fact/{id}` dispatches on the namespace. A `B-` id expands to the persona's derived
barrier and the profile field the simulation computed it from — the loop closed from the state side.
It never fabricates a link the persona lacks, and one persona's state id does not resolve against
another.

## Boundary

State-citation lets narration **point at** core state. It never lets narration **change** it — see
[Simulate with models, narrate with LLMs](../architecture/core-narration-split.md).

---
Related: [The v3 reading](v3-reading.md), [pre-registration](pre-registration.md), [Simulate with models, narrate with LLMs](../architecture/core-narration-split.md), [Ground on nothing rather than the wrong thing](../decisions/hetionet-no-alias.md)
