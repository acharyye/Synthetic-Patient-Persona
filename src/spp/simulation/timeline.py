"""Walk personas through a schedule, emitting events.

This is where the foundation layer finally earns its keep: the simulation writes
an append-only event log per persona, and every downstream question — survival
curves, attrition funnels, "why did #3412 drop at visit 4", counterfactual
forking — is answered by reading those logs rather than by instrumenting the
simulator with special cases.

Determinism: each persona simulates from its own named seed scope, and each visit
from a child of that. So persona #7's trajectory is identical whether you
simulate 10 personas or 10,000, and re-running one persona alone reproduces it
exactly. That property is what makes Phase 2's counterfactual diffs measure the
design change instead of RNG drift.
"""
from __future__ import annotations

from ..foundation.events import EventLog, EventType, fold
from ..foundation.rng import SeedScope, cohort_scope, event_scope, persona_scope
from ..protocol.burden import ProtocolBurden
from ..schemas import PatientDNA
from .hazard import attendance_probability, dominant_reason, dropout_probability
from .schedule import VisitSchedule, burden_sensitivity, experienced_burden


def simulate_persona(
    dna: PatientDNA,
    schedule: VisitSchedule,
    scope: SeedScope,
    washout: bool = False,
) -> EventLog:
    """Simulate one persona's journey through `schedule`, returning its log."""
    log = EventLog(persona_id=dna.patient_id)
    log.append(EventType.ENROLLED, t=0, seed_path=scope.path)

    sensitivity = burden_sensitivity(dna)
    consecutive_missed = 0

    for index, visit in enumerate(schedule.visits):
        state = fold(log)
        if state.terminal:
            break

        # Keyed by stable identity so surviving visits draw identically
        # under a mutated schedule (common random numbers).
        visit_scope = event_scope(scope, visit.visit_id)
        gen = visit_scope.generator()

        felt = experienced_burden(visit, sensitivity)
        attends = gen.random() < attendance_probability(dna, state, felt)

        if attends:
            consecutive_missed = 0
            log.append(
                EventType.VISIT_COMPLETED, t=visit.day,
                payload={"visit": visit.visit_id, "label": visit.label}, seed_path=visit_scope.path,
            )
            log.append(
                EventType.BURDEN_ACCRUED, t=visit.day,
                payload={
                    "burden": felt.model_dump(),
                    "total": round(felt.total, 4),
                    "dominant": felt.dominant(),
                },
                seed_path=visit_scope.path,
            )
            increment = felt
        else:
            consecutive_missed += 1
            log.append(
                EventType.VISIT_MISSED, t=visit.day,
                payload={"visit": visit.visit_id, "label": visit.label,
                         "consecutive": consecutive_missed},
                seed_path=visit_scope.path,
            )
            # A missed visit costs the persona nothing in burden, but the reason
            # they missed is worth recording — it is what a site would act on.
            if dna.barriers:
                worst = max(dna.barriers, key=lambda b: b.severity)
                log.append(
                    EventType.BARRIER_TRIGGERED, t=visit.day,
                    payload={"barrier": worst.name, "visit": visit.visit_id},
                    seed_path=visit_scope.path,
                )
            increment = type(felt)()

        state = fold(log)
        hazard = dropout_probability(
            dna, state, increment, consecutive_missed,
            washout=washout and index == 0,
        )
        if gen.random() < hazard:
            log.append(
                EventType.DROPPED_OUT, t=visit.day,
                payload={
                    "reason": dominant_reason(dna, state, increment),
                    "visit": visit.visit_id,
                    "hazard": round(hazard, 4),
                },
                seed_path=visit_scope.path,
            )
            break

    if not fold(log).terminal:
        log.append(EventType.COMPLETED, t=schedule.duration_days)
    return log


def simulate_cohort(
    cohort: list[PatientDNA],
    schedule: VisitSchedule,
    seed: int = 42,
    condition: str | None = None,
    washout: bool = False,
) -> dict[str, EventLog]:
    """Simulate every persona, returning logs keyed by patient_id."""
    anchor = cohort_scope(seed, condition or (cohort[0].condition if cohort else "cohort"))
    return {
        dna.patient_id: simulate_persona(
            dna, schedule, persona_scope(anchor, index).child("sim"), washout=washout
        )
        for index, dna in enumerate(cohort)
    }


def schedule_from_protocol(
    protocol: ProtocolBurden, duration_days: int = 365
) -> VisitSchedule:
    """Convenience: the schedule a ProtocolBurden implies."""
    return VisitSchedule.from_protocol(protocol, duration_days=duration_days)
