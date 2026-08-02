"""Derive goals, constraints and barriers from a persona's profile.

These are not decoration. They are the interface between the profile and the two
things that consume it:

  * the **dropout hazard**, which reads `barrier.severity`;
  * the **narration layer**, which reads the labels so a persona can say
    "I can't get there on a Tuesday" instead of generic distress.

Derivation is deterministic and rule-based — no RNG, no LLM. Two personas with
the same profile get the same barriers, which is what makes them explainable and
what lets `origin` point at the field responsible.

Severities come from the ledger (`traits.barrier_severity`), so a barrier's
weight can be perturbed by sensitivity analysis like any other coefficient.
"""
from __future__ import annotations

from ..assumptions import BARRIER_SEVERITY
from ..schemas import Barrier, PatientDNA

# Goal templates keyed by the profile signal that triggers them. Phrased in the
# persona's voice because they are injected into narration prompts verbatim.
_GOAL_RULES: list[tuple[str, str]] = [
    ("working", "keep working without my condition getting in the way"),
    ("caregiving", "stay well enough to look after the people who depend on me"),
    ("advanced_stage", "slow this down and stay out of hospital"),
    ("early_stage", "get on top of this before it gets worse"),
    ("polypharmacy", "get by on fewer tablets, not more"),
    ("low_adherence", "keep up with treatment more reliably than I manage now"),
    ("elderly", "stay independent for as long as I can"),
    ("default", "understand what is happening to me and what comes next"),
]


def _signals(dna: PatientDNA) -> dict[str, bool]:
    """Boolean profile signals the rules below key off."""
    sdoh = {k.casefold(): str(v).casefold() for k, v in dna.social_determinants.items()}
    stage = (dna.stage or "").casefold()

    return {
        "working": sdoh.get("employment") in {"full-time", "part-time", "shift-work"},
        "shift_work": sdoh.get("employment") == "shift-work",
        "caregiving": sdoh.get("caregiver") in {"spouse", "adult child"},
        "no_caregiver": sdoh.get("caregiver") == "none",
        "no_transport": sdoh.get("transport") == "none",
        "public_transport": sdoh.get("transport") == "public transport",
        "rural": sdoh.get("residence") == "rural",
        "low_literacy": dna.health_literacy == "low",
        "low_adherence": dna.adherence_baseline < 0.6,
        "polypharmacy": len(dna.medications) >= 3,
        "multimorbidity": len(dna.comorbidities) >= 3,
        "elderly": dna.age >= 75,
        "advanced_stage": stage in {"advanced", "iii", "iv", "gold3", "gold4",
                                    "nyha3", "nyha4"},
        "early_stage": stage in {"early", "i", "gold1", "nyha1"},
        "low_digital": dna.traits.get("digital_literacy", 0.5) < 0.3,
        "low_mobility": dna.traits.get("mobility", 0.5) < 0.3,
        "financially_stretched": dna.traits.get("financial_security", 0.5) < 0.3,
    }


def derive_goals(dna: PatientDNA, limit: int = 3) -> list[str]:
    """What this persona is trying to achieve, most specific first."""
    signals = _signals(dna)
    goals = [text for key, text in _GOAL_RULES if key != "default" and signals.get(key)]
    if not goals:
        goals = [dict(_GOAL_RULES)["default"]]
    return goals[:limit]


def derive_constraints(dna: PatientDNA) -> list[str]:
    """Facts of this persona's life that a protocol cannot negotiate away."""
    signals = _signals(dna)
    sdoh = {k.casefold(): str(v).casefold() for k, v in dna.social_determinants.items()}
    constraints: list[str] = []

    if signals["no_transport"]:
        constraints.append("no car and no reliable lift to the site")
    elif signals["public_transport"]:
        constraints.append("depends on public transport to get anywhere")
    if signals["shift_work"]:
        constraints.append("works shifts, so weekday daytime appointments are hard")
    elif signals["working"]:
        constraints.append(f"works {sdoh.get('employment', 'full-time')}")
    if signals["rural"]:
        constraints.append("lives rurally, a long way from the site")
    if signals["no_caregiver"]:
        constraints.append("no one at home to help")
    if signals["low_mobility"]:
        constraints.append("limited mobility, travel is tiring")
    if signals["financially_stretched"]:
        constraints.append("cannot absorb out-of-pocket costs")
    return constraints


def derive_barriers(dna: PatientDNA) -> list[Barrier]:
    """Typed barriers with severity, ordered worst first.

    `origin` names the profile field responsible so a report can trace a dropout
    back to the thing that caused it rather than to a score.
    """
    signals = _signals(dna)
    severity = BARRIER_SEVERITY.params
    candidates: list[tuple[str, str, str, str]] = [
        # (signal, barrier name, origin field, note)
        ("no_transport", "transport", "social_determinants.transport",
         "no way of getting to the site reliably"),
        ("public_transport", "transport_fragile", "social_determinants.transport",
         "journey depends on public transport running"),
        ("shift_work", "scheduling", "social_determinants.employment",
         "shift pattern collides with appointment windows"),
        ("low_literacy", "comprehension", "health_literacy",
         "consent forms and diaries are hard work"),
        ("low_digital", "digital_access", "traits.digital_literacy",
         "app-based tasks are a struggle"),
        ("no_caregiver", "unsupported", "social_determinants.caregiver",
         "nobody to help with attendance or medication"),
        ("low_adherence", "adherence", "adherence_baseline",
         "already misses doses"),
        ("polypharmacy", "pill_burden", "medications",
         "regimen is already complicated"),
        ("multimorbidity", "competing_care", "comorbidities",
         "other conditions compete for the same time"),
        ("low_mobility", "mobility", "traits.mobility",
         "travel and waiting are physically costly"),
        ("financially_stretched", "cost", "traits.financial_security",
         "travel and time off work are not affordable"),
        ("rural", "distance", "social_determinants.residence",
         "long journey each way"),
    ]

    barriers = [
        Barrier(
            name=name,
            severity=severity.get(name, 0.1),
            origin=origin,
            note=note,
        )
        for signal, name, origin, note in candidates
        if signals.get(signal)
    ]
    return sorted(barriers, key=lambda b: (-b.severity, b.name))


def derive_persona_traits(dna: PatientDNA) -> PatientDNA:
    """Attach goals, constraints and barriers to a persona.

    Returns a copy. Safe to call on a v1-migrated cohort to backfill.
    """
    return dna.model_copy(
        update={
            "goals": derive_goals(dna),
            "constraints": derive_constraints(dna),
            "barriers": derive_barriers(dna),
        }
    )
