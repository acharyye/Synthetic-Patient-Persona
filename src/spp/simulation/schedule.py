"""Scenarios as event schedules, not just rule sets.

A protocol is a sequence of things you ask someone to do on particular days. Once
it is expressed that way, burden accrues *over a timeline* instead of being one
static score, and dropout can happen at a specific visit for a specific reason —
which is what makes "why did persona #3412 drop at visit 4" answerable.

Burden is a vector (time, travel, procedural, cognitive, financial, scheduling)
per visit, and each persona experiences it through their own sensitivity
multipliers. The same schedule is genuinely not the same ask for a retired
driver and a shift worker with no car — that difference is the product.
"""
from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from ..assumptions import BURDEN_SENSITIVITY, VISIT_BURDEN
from ..foundation.events import BurdenVector
from ..protocol.burden import ProtocolBurden
from ..schemas import PatientDNA


class ScheduledVisit(BaseModel):
    # Stable identity, assigned once and preserved through every mutation. The
    # simulation seeds each visit's draws from this, NOT from list position, so
    # dropping one visit leaves every other visit drawing exactly as before
    # (common random numbers). Never regenerate these from an index.
    visit_id: str
    day: int = Field(ge=0)
    label: str
    burden: BurdenVector
    remote: bool = False


class VisitSchedule(BaseModel):
    """A protocol expressed as dated demands on a participant.

    Mutations return new schedules and **preserve `visit_id` on every surviving
    visit**. That invariant is what makes a counterfactual diff measure the
    design change rather than reshuffled randomness — see `tests/test_seed_keying.py`.
    """

    name: str = "schedule"
    duration_days: int = Field(365, gt=0)
    visits: list[ScheduledVisit] = Field(default_factory=list)

    @model_validator(mode="after")
    def _unique_ids(self) -> VisitSchedule:
        ids = [visit.visit_id for visit in self.visits]
        if len(ids) != len(set(ids)):
            raise ValueError("visit_id must be unique within a schedule")
        return self

    def __len__(self) -> int:
        return len(self.visits)

    def visit(self, visit_id: str) -> ScheduledVisit:
        for candidate in self.visits:
            if candidate.visit_id == visit_id:
                return candidate
        raise KeyError(f"schedule {self.name!r} has no visit {visit_id!r}")

    # -- mutations (identity-preserving) ------------------------------------

    def without(self, *visit_ids: str) -> VisitSchedule:
        """Drop visits. Survivors keep their ids, days and burdens untouched."""
        unknown = set(visit_ids) - {v.visit_id for v in self.visits}
        if unknown:
            raise KeyError(f"no such visit(s): {sorted(unknown)}")
        return self.model_copy(update={
            "visits": [v for v in self.visits if v.visit_id not in visit_ids]
        })

    def remote(self, *visit_ids: str) -> VisitSchedule:
        """Make visits remote — travel burden collapses, identity does not."""
        weights = VISIT_BURDEN.params
        factor = weights["remote_travel_multiplier"]
        return self.model_copy(update={
            "visits": [
                visit.model_copy(update={
                    "remote": True,
                    "burden": visit.burden.model_copy(update={
                        "travel": visit.burden.travel * factor
                    }),
                })
                if visit.visit_id in visit_ids else visit
                for visit in self.visits
            ]
        })

    def rescheduled(self, visit_id: str, day: int) -> VisitSchedule:
        """Move a visit in time, keeping its identity (and therefore its draw)."""
        visits = [
            visit.model_copy(update={"day": day}) if visit.visit_id == visit_id else visit
            for visit in self.visits
        ]
        return self.model_copy(update={
            "visits": sorted(visits, key=lambda v: v.day)
        })

    @classmethod
    def from_protocol(
        cls,
        protocol: ProtocolBurden,
        duration_days: int = 365,
        name: str = "protocol",
    ) -> VisitSchedule:
        """Expand a ProtocolBurden into evenly spaced visits.

        Even spacing is a simplification: real schedules front-load (screening,
        baseline, then taper). Worth replacing when a real protocol is imported.
        """
        weights = VISIT_BURDEN.params
        n_visits = max(1, round(protocol.visits_per_year * duration_days / 365))
        interval = max(1, duration_days // n_visits)

        travel = weights["travel"] if protocol.travel_required else (
            weights["travel"] * weights["remote_travel_multiplier"]
        )
        procedural = weights["procedural"] + (
            weights["procedure_increment"] * len(protocol.procedures)
        )
        cognitive = weights["cognitive"] + (
            weights["daily_diary_cognitive"] if protocol.daily_diary else 0.0
        )

        visits = [
            ScheduledVisit(
                # Assigned once, here. Every mutation preserves it.
                visit_id=f"v{i + 1:03d}",
                day=min(duration_days, (i + 1) * interval),
                label=f"visit-{i + 1}",
                remote=not protocol.travel_required,
                burden=BurdenVector(
                    time=weights["time"],
                    travel=travel,
                    # Washout is a one-off cost, paid at the first visit.
                    procedural=procedural + (
                        weights["washout_procedural"]
                        if protocol.washout_required and i == 0 else 0.0
                    ),
                    cognitive=cognitive,
                    financial=weights["financial"],
                    scheduling=weights["scheduling"],
                ),
            )
            for i in range(n_visits)
        ]
        return cls(name=name, duration_days=duration_days, visits=visits)


def burden_sensitivity(dna: PatientDNA) -> BurdenVector:
    """Per-component multipliers describing how this persona *feels* burden.

    Returns a BurdenVector used as elementwise weights, not as burden itself.
    Multipliers compose multiplicatively — someone rural with no transport and
    low mobility experiences travel as far more than any one factor implies,
    which is the clustering effect the copula put there in the first place.
    """
    weights = BURDEN_SENSITIVITY.params
    base = weights["base"]
    sdoh = {k.casefold(): str(v).casefold() for k, v in dna.social_determinants.items()}
    traits = dna.traits

    travel = base
    if traits.get("mobility", 0.5) < 0.3:
        travel *= weights["low_mobility_travel"]
    if sdoh.get("transport") == "none":
        travel *= weights["no_transport_travel"]
    if sdoh.get("residence") == "rural":
        travel *= weights["rural_travel"]

    scheduling = base
    if sdoh.get("employment") == "shift-work":
        scheduling *= weights["shift_work_scheduling"]
    elif sdoh.get("employment") in {"full-time", "part-time"}:
        scheduling *= weights["working_scheduling"]
    if sdoh.get("caregiver") in {"spouse", "adult child"}:
        scheduling *= weights["caregiving_scheduling"]

    financial = base
    if traits.get("financial_security", 0.5) < 0.3:
        financial *= weights["low_financial_financial"]

    cognitive = base
    if dna.health_literacy == "low":
        cognitive *= weights["low_literacy_cognitive"]
    if traits.get("digital_literacy", 0.5) < 0.3:
        cognitive *= weights["low_digital_cognitive"]

    time = base
    if len(dna.comorbidities) >= 3:
        time *= weights["multimorbidity_time"]
    if dna.age >= 75:
        time *= weights["elderly_time"]

    return BurdenVector(
        time=time,
        travel=travel,
        procedural=base,
        cognitive=cognitive,
        financial=financial,
        scheduling=scheduling,
    )


def experienced_burden(visit: ScheduledVisit, sensitivity: BurdenVector) -> BurdenVector:
    """Elementwise product: what this visit actually costs this persona."""
    return BurdenVector(
        **{
            field: getattr(visit.burden, field) * getattr(sensitivity, field)
            for field in BurdenVector.model_fields
        }
    )
