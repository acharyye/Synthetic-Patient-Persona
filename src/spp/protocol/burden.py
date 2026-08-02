"""Participation burden: who stays eligible on paper but struggles in practice.

Eligibility answers "may they enrol". This answers "what would it cost them" —
the failure mode that shows up as screen failure, missed visits and dropout
rather than as an exclusion criterion.

The score is a transparent weighted sum of barriers the Patient DNA already
records. It is a *triage heuristic* for deciding which personas are worth
interviewing, not a validated retention risk instrument. The qualitative half —
`burden_report` — is where the real signal is: it puts the protocol to the
persona and lets it answer in its own words, grounded by the KG.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from ..assumptions import BURDEN_FACTORS, BURDEN_INTENSITY, BURDEN_THRESHOLDS
from ..schemas import PatientDNA


class ProtocolBurden(BaseModel):
    """The participation ask, as a patient would experience it."""

    visits_per_year: int = 12
    travel_required: bool = True
    daily_diary: bool = False
    washout_required: bool = False
    procedures: list[str] = Field(
        default_factory=list,
        description="e.g. ['fasting bloods each visit', 'MRI at weeks 0/12/24']",
    )

    def describe(self) -> str:
        parts = [f"{self.visits_per_year} site visits a year"]
        if self.travel_required:
            parts.append("each requiring travel to the site")
        if self.daily_diary:
            parts.append("a symptom diary to complete every day")
        if self.washout_required:
            parts.append("a washout period off your current medication before starting")
        parts.extend(self.procedures)
        return "; ".join(parts)


class BurdenProfile(BaseModel):
    patient_id: str
    score: float = Field(ge=0.0, le=1.0, description="0 = low burden, 1 = severe")
    drivers: list[str] = Field(default_factory=list)


# Human-readable reason per factor. The *weights* live in the assumption ledger
# (`burden.factor_weights`) so they can be audited and perturbed; only the wording
# lives here.
_FACTOR_REASONS: dict[str, str] = {
    "low_adherence": "already struggles to take medication as prescribed",
    "no_transport": "no reliable transport to the site",
    "low_literacy": "low health literacy — consent and diaries are harder",
    "working": "work pattern conflicts with weekday visits",
    "no_caregiver": "no one at home to support attendance",
    "polypharmacy": "already on several medications",
    "multimorbidity": "multiple conditions competing for appointments",
    "elderly": "age 80+ — travel and fatigue compound",
    "rural": "lives rurally, long journey to site",
}

# Ordered weakest-to-strongest contribution, so `drivers` reads worst-first.
_FACTOR_ORDER = sorted(
    _FACTOR_REASONS, key=lambda key: -BURDEN_FACTORS.params.get(key, 0.0)
)


def burden_profile(dna: PatientDNA, protocol: ProtocolBurden | None = None) -> BurdenProfile:
    """Score participation burden for one persona and name what is driving it."""
    protocol = protocol or ProtocolBurden()
    sdoh = {k.casefold(): str(v).casefold() for k, v in dna.social_determinants.items()}

    cut = BURDEN_THRESHOLDS.params
    triggered = {
        "low_adherence": dna.adherence_baseline < cut["low_adherence_below"],
        "no_transport": sdoh.get("transport") in {"none", "public transport"},
        "low_literacy": dna.health_literacy == "low",
        "working": sdoh.get("employment") in {"full-time", "shift-work", "part-time"},
        "no_caregiver": sdoh.get("caregiver") == "none",
        "polypharmacy": len(dna.medications) >= cut["polypharmacy_at_least"],
        "multimorbidity": len(dna.comorbidities) >= cut["multimorbidity_at_least"],
        "elderly": dna.age >= cut["elderly_from_age"],
        "rural": sdoh.get("residence") == "rural",
    }

    weights = BURDEN_FACTORS.params
    score = 0.0
    drivers: list[str] = []
    for key in _FACTOR_ORDER:
        if triggered.get(key):
            score += weights[key]
            drivers.append(_FACTOR_REASONS[key])

    # A heavier protocol amplifies whatever barriers are already there rather
    # than adding burden to a patient who has none.
    steps = BURDEN_INTENSITY.params
    intensity = steps["base"]
    if protocol.visits_per_year >= 12:
        intensity += steps["visits_12_plus"]
    if protocol.visits_per_year >= 24:
        intensity += steps["visits_24_plus"]
    if protocol.daily_diary:
        intensity += steps["daily_diary"]
    if protocol.washout_required:
        intensity += steps["washout"]
    score *= intensity

    if protocol.washout_required and dna.medications:
        drivers.append("washout means stopping medication that is currently working")

    return BurdenProfile(
        patient_id=dna.patient_id,
        score=round(min(1.0, score), 2),
        drivers=drivers,
    )


def rank_by_burden(
    cohort: list[PatientDNA], protocol: ProtocolBurden | None = None
) -> list[BurdenProfile]:
    """Highest-burden personas first — the interview shortlist."""
    profiles = [burden_profile(dna, protocol) for dna in cohort]
    return sorted(profiles, key=lambda p: -p.score)


def burden_question(protocol: ProtocolBurden) -> str:
    """The question put to each persona. Deliberately open — we want their
    objection in their own words, not a yes/no against our own risk model.
    """
    return (
        "A research team has invited you to join a clinical trial. Taking part "
        f"would mean: {protocol.describe()}. "
        "Would that be realistic for you? Please be specific about what would get "
        "in the way, and what would have to change for you to say yes."
    )


def burden_report(
    engine,
    dna: PatientDNA,
    protocol: ProtocolBurden | None = None,
) -> dict:
    """Score one persona, then let it speak for itself about the protocol.

    `engine` is a PersonaEngine (untyped here to keep protocol/ independent of
    persona/). Offline this returns the deterministic stub reply, so the shape of
    the response is identical live or not.
    """
    protocol = protocol or ProtocolBurden()
    profile = burden_profile(dna, protocol)
    interview = engine.interview(dna, burden_question(protocol))
    return {
        **profile.model_dump(),
        "summary": dna.summary(),
        "response": interview["reply"],
        "grounded_edges": interview["grounded_edges"],
    }
