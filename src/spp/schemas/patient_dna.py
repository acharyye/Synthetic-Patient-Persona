"""Patient DNA: the structured profile that conditions AND constrains a persona.

This is the 'genome' of a synthetic patient. It is populated from realistic
distributions (Synthea / MIMIC-IV / registries) so personas are statistically
plausible rather than invented, and it is passed to the persona engine so the
LLM cannot drift into clinically incoherent answers.
"""
from __future__ import annotations

import math

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field


class Medication(BaseModel):
    name: str
    dose: str | None = None
    started: date | None = None
    adherence: float = Field(1.0, ge=0.0, le=1.0, description="0=never taken, 1=perfect")


class JourneyMilestone(BaseModel):
    """A single event on the patient journey (onset -> diagnosis -> treatment -> ...)."""
    stage: Literal[
        "symptom_onset", "first_contact", "diagnosis",
        "treatment_start", "follow_up", "adverse_event", "outcome",
    ]
    when: date | None = None
    note: str = ""


class Barrier(BaseModel):
    """Something concrete standing between this persona and participation.

    Typed rather than a free-text list because barriers feed three consumers:
    the dropout hazard (severity), the narration prompt (label), and the report
    ("why did persona #3412 drop"), which needs `origin` to trace the barrier
    back to the profile field that produced it.
    """

    name: str
    severity: float = Field(ge=0.0, le=1.0)
    origin: str = Field(description="profile field this was derived from")
    note: str = ""


class PatientDNA(BaseModel):
    # Bumped when fields change meaning. Persisted payloads carry this and go
    # through foundation.versioning.migrate() on load.
    schema_version: int = 2

    patient_id: str

    # demographics
    age: int = Field(ge=0, le=120)
    sex: Literal["female", "male", "other"]
    ancestry: str | None = None

    # clinical core
    condition: str                       # primary condition, ideally a KG node id/name
    stage: str | None = None
    biomarkers: dict[str, float] = Field(default_factory=dict)
    comorbidities: list[str] = Field(default_factory=list)
    medications: list[Medication] = Field(default_factory=list)

    # behaviour / context that drives trial fit and adherence
    adherence_baseline: float = Field(0.8, ge=0.0, le=1.0)
    health_literacy: Literal["low", "medium", "high"] = "medium"
    social_determinants: dict[str, str] = Field(
        default_factory=dict,
        description="e.g. {'transport': 'none', 'caregiver': 'spouse', 'employment': 'shift-work'}",
    )

    # Latent trait quantiles from the copula, kept for provenance: they explain
    # why this persona's traits hang together the way they do, and let a report
    # answer "is this one unusual?" without re-deriving anything.
    traits: dict[str, float] = Field(default_factory=dict)

    # What this persona wants, what they cannot change, and what gets in the way.
    # Derived at generation time; consumed by the hazard model and narration.
    goals: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    barriers: list[Barrier] = Field(default_factory=list)

    # the journey
    journey: list[JourneyMilestone] = Field(default_factory=list)

    @property
    def barrier_load(self) -> float:
        """Summed barrier severity — the hazard model's main persona input."""
        return round(math.fsum(b.severity for b in self.barriers), 4)

    def summary(self) -> str:
        """Compact human/LLM-readable digest used in prompts."""
        meds = ", ".join(m.name for m in self.medications) or "none"
        comorb = ", ".join(self.comorbidities) or "none"
        return (
            f"{self.age}yo {self.sex} with {self.condition}"
            f"{f' ({self.stage})' if self.stage else ''}. "
            f"Comorbidities: {comorb}. Medications: {meds}. "
            f"Baseline adherence {self.adherence_baseline:.0%}, "
            f"{self.health_literacy} health literacy."
        )

    def context(self) -> str:
        """Fuller digest for narration: what they want and what's in the way.

        Kept separate from `summary()` so prompts can stay short where the extra
        detail would only dilute the profile constraint.
        """
        lines = [self.summary()]
        if self.goals:
            lines.append("Wants: " + "; ".join(self.goals) + ".")
        if self.constraints:
            lines.append("Cannot change: " + "; ".join(self.constraints) + ".")
        if self.barriers:
            worst = sorted(self.barriers, key=lambda b: -b.severity)
            lines.append(
                "Struggles with: "
                + "; ".join(f"{b.name} ({b.severity:.0%})" for b in worst)
                + "."
            )
        return " ".join(lines)
