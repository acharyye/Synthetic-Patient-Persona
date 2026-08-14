"""Population-level readouts derived from event logs.

Everything here is a pure function of the logs — no simulation state, no RNG. The
Phase 1 exit criterion lives in `survival_curve`: a retention curve a domain
reviewer would call plausible-shaped, with every coefficient behind it registered
in the ledger.

Read these as *design signal under stated assumptions*, never as forecasts. The
hazard model is tagged a known limitation precisely because the level of the
curve is not calibrated to anyone's observed retention — its shape and, above
all, the *difference between two designs* is what the tool is for.
"""
from __future__ import annotations

import math

from ..foundation.events import EventLog, EventType, JourneyStage, fold


def survival_curve(
    logs: dict[str, EventLog], horizon: int, points: int = 25
) -> list[dict]:
    """Fraction of enrolled personas still active at each of `points` timepoints."""
    if not logs:
        return []

    total = len(logs)
    step = max(1, horizon // max(1, points - 1))
    days = list(range(0, horizon + 1, step))
    if days[-1] != horizon:
        days.append(horizon)

    curve = []
    for day in days:
        states = [fold(log, until=day) for log in logs.values()]
        dropped = sum(1 for s in states if s.stage == JourneyStage.DROPPED)
        completed = sum(1 for s in states if s.stage == JourneyStage.COMPLETED)
        curve.append({
            "day": day,
            "retained": total - dropped,
            "dropped": dropped,
            "completed": completed,
            "retention": round((total - dropped) / total, 4),
        })
    return curve


def retention_summary(logs: dict[str, EventLog]) -> dict:
    """Headline retention, attendance and attrition-reason breakdown."""
    if not logs:
        return {"n": 0}

    states = {pid: fold(log) for pid, log in logs.items()}
    total = len(states)
    dropped = [pid for pid, s in states.items() if s.stage == JourneyStage.DROPPED]

    reasons: dict[str, int] = {}
    dropout_days: list[int] = []
    for pid in dropped:
        events = logs[pid].of_type(EventType.DROPPED_OUT)
        if events:
            reason = str(events[-1].payload.get("reason", "unknown"))
            reasons[reason] = reasons.get(reason, 0) + 1
            dropout_days.append(events[-1].t)

    attended = sum(s.visits_completed for s in states.values())  # int-sum: PersonaState.visits_completed
    missed = sum(s.visits_missed for s in states.values())  # int-sum: PersonaState.visits_missed
    rates = [s.attendance_rate for s in states.values() if s.attendance_rate is not None]

    return {
        "n": total,
        "retained": total - len(dropped),
        "dropped": len(dropped),
        "retention_rate": round((total - len(dropped)) / total, 4),
        "median_dropout_day": (
            sorted(dropout_days)[len(dropout_days) // 2] if dropout_days else None
        ),
        "visits_completed": attended,
        "visits_missed": missed,
        "overall_attendance_rate": (
            round(attended / (attended + missed), 4) if attended + missed else None
        ),
        "mean_persona_attendance": (
            round(math.fsum(rates) / len(rates), 4) if rates else None
        ),
        "dropout_reasons": dict(sorted(reasons.items(), key=lambda kv: (-kv[1], kv[0]))),
        "mean_burden_at_exit": round(
            math.fsum(s.burden.total for s in states.values()) / total, 4
        ),
    }


def burden_breakdown(logs: dict[str, EventLog]) -> dict[str, float]:
    """Mean accrued burden per component — which *kind* of burden dominated.

    The reason burden is a vector: a single score cannot tell a designer whether
    to move visits remote (travel) or off weekdays (scheduling).
    """
    if not logs:
        return {}

    states = [fold(log) for log in logs.values()]
    fields = type(states[0].burden).model_fields
    return {
        field: round(math.fsum(getattr(s.burden, field) for s in states) / len(states), 4)
        for field in fields
    }


def attrition_funnel(logs: dict[str, EventLog], screened: int | None = None) -> dict:
    """Screened -> enrolled -> retained -> completed, as counts."""
    states = [fold(log) for log in logs.values()]
    enrolled = len(states)
    return {
        "screened": screened if screened is not None else enrolled,
        "enrolled": enrolled,
        "retained": sum(1 for s in states if s.stage != JourneyStage.DROPPED),
        "completed": sum(1 for s in states if s.stage == JourneyStage.COMPLETED),
        "dropped": sum(1 for s in states if s.stage == JourneyStage.DROPPED),
    }
