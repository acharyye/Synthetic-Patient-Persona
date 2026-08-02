"""Attendance and dropout hazard.

Two discrete-time decisions taken at each scheduled visit:

  * **attend or miss** — logistic in adherence, accumulated burden, barrier load
    and how costly *this particular* visit is for this persona;
  * **drop out or continue** — logistic in cumulative burden, the burden just
    incurred, barrier load, adherence deficit and consecutive missed visits.

Both are part of the deterministic core: they consume a seeded generator and
decide what happens. No LLM is involved and none may be — narration explains
these outcomes afterwards, it never produces them.

Every coefficient comes from the ledger. `timeline.dropout_hazard` is tagged a
known limitation on purpose: it produces attrition in a plausible *range*, but it
is calibrated against nobody's retention data. Treat curve shape as a design
signal, never as a forecast.
"""
from __future__ import annotations

import math

import numpy as np

from ..assumptions import ATTENDANCE, DROPOUT_HAZARD
from ..foundation.events import BurdenVector, PersonaState
from ..schemas import PatientDNA


def _sigmoid(x: float) -> float:
    # Guard the exponential so an extreme logit can't overflow.
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-min(x, 60.0)))
    exp_x = math.exp(max(x, -60.0))
    return exp_x / (1.0 + exp_x)


def attendance_probability(
    dna: PatientDNA,
    state: PersonaState,
    visit_burden: BurdenVector,
) -> float:
    """Probability this persona turns up to this visit."""
    weights = ATTENDANCE.params
    logit = (
        weights["intercept"]
        + weights["adherence_weight"] * dna.adherence_baseline
        + weights["burden_weight"] * state.burden.total
        + weights["barrier_weight"] * dna.barrier_load
        + weights["visit_burden_weight"] * visit_burden.total
    )
    return float(np.clip(_sigmoid(logit), weights["floor"], weights["ceiling"]))


def dropout_probability(
    dna: PatientDNA,
    state: PersonaState,
    burden_increment: BurdenVector,
    consecutive_missed: int = 0,
    washout: bool = False,
) -> float:
    """Per-visit hazard of leaving the study altogether.

    Deliberately separates *cumulative* burden from the *increment* just
    incurred: people leave because of a bad visit as well as because of a long
    grind, and a model with only the running total cannot express the former.
    """
    weights = DROPOUT_HAZARD.params
    logit = (
        weights["intercept"]
        + weights["cumulative_burden_weight"] * state.burden.total
        + weights["burden_increment_weight"] * burden_increment.total
        + weights["barrier_weight"] * dna.barrier_load
        + weights["adherence_deficit_weight"] * (1.0 - dna.adherence_baseline)
        + weights["consecutive_missed_weight"] * consecutive_missed
        + (weights["washout_bump"] if washout else 0.0)
    )
    return float(np.clip(_sigmoid(logit), 0.0, weights["max_per_visit"]))


def dominant_reason(
    dna: PatientDNA, state: PersonaState, increment: BurdenVector
) -> str:
    """Best single explanation for a dropout, for the event payload and report.

    Attribution by largest contribution to the logit — approximate, but it points
    at a cause a designer can act on rather than at a number.
    """
    weights = DROPOUT_HAZARD.params
    contributions = {
        "accumulated burden": weights["cumulative_burden_weight"] * state.burden.total,
        "this visit": weights["burden_increment_weight"] * increment.total,
        "personal barriers": weights["barrier_weight"] * dna.barrier_load,
        "poor adherence": (
            weights["adherence_deficit_weight"] * (1.0 - dna.adherence_baseline)
        ),
    }
    driver = max(contributions, key=lambda k: contributions[k])

    # Name the burden component doing the damage — "travel" beats "burden".
    if driver in {"accumulated burden", "this visit"}:
        component = (state.burden.plus(increment)).dominant()
        if component:
            return f"{driver} ({component})"
    if driver == "personal barriers" and dna.barriers:
        worst = max(dna.barriers, key=lambda b: b.severity)
        return f"personal barriers ({worst.name})"
    return driver
