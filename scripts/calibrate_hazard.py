"""Jointly calibrate the dropout hazard's intercept and cumulative-burden slope.

    PYTHONPATH=src python scripts/calibrate_hazard.py

Why joint. A per-design intercept shift patches a symptom: if the shift needed
grows with visit count (it did — -0.27 for a 4-visit design, -1.91 for a
24-visit one), the *slope* on cumulative burden is wrong, and every new protocol
intensity will need its own correction. Two free parameters against two anchors
pins both at once:

    intercept                 sets the floor hazard for a light protocol
    cumulative_burden_weight  sets how fast hazard grows as burden accumulates

Anchors are deliberately the extremes (light and heavy). The mid-intensity
protocol is HELD OUT — it is never fitted, and where it lands is the only real
evidence that the two-parameter form generalises rather than interpolates.

The anchors are plausibility targets, not observed data. This calibrates the
model to a stated belief about trial retention; it does not validate it. That is
why the tests it feeds assert BANDS and ORDERING, never point values.
"""
from __future__ import annotations

import math
from datetime import date

import numpy as np

from spp.assumptions import DROPOUT_HAZARD
from spp.cohort import generate_cohort
from spp.protocol import ProtocolBurden
from spp.simulation import retention_summary, schedule_from_protocol, simulate_cohort

AS_OF = date(2026, 8, 1)
COHORT_N = 400
SEED = 42

# (label, protocol, target retention). Only the anchors are fitted.
LIGHT = ("light", ProtocolBurden(visits_per_year=4, travel_required=False), 0.93)
HEAVY = ("heavy", ProtocolBurden(visits_per_year=24, daily_diary=True,
                                 washout_required=True), 0.55)
HELD_OUT = ("typical (held out)", ProtocolBurden(visits_per_year=12), None)


def retention(cohort, protocol: ProtocolBurden, intercept: float, slope: float) -> float:
    """Retention under a candidate (intercept, slope). Mutates the ledger entry
    in place and restores nothing — the caller owns the final value.
    """
    DROPOUT_HAZARD.params["intercept"] = float(intercept)
    DROPOUT_HAZARD.params["cumulative_burden_weight"] = float(slope)
    logs = simulate_cohort(
        cohort, schedule_from_protocol(protocol, 365), seed=SEED,
        washout=protocol.washout_required,
    )
    return retention_summary(logs)["retention_rate"]


def _bisect(evaluate, lo: float, hi: float, target: float, iterations: int = 16) -> float:
    """Bisect a monotonically DECREASING function to hit `target`.

    Bisection rather than Newton: the objective is a step function in the seeds
    (a parameter nudge that flips no persona's draw has zero gradient), so a
    numerical Jacobian goes singular. Bisection needs only monotonicity, which
    both parameters genuinely have — raising either raises hazard, which lowers
    retention.
    """
    for _ in range(iterations):
        mid = (lo + hi) / 2.0
        value = evaluate(mid)
        if abs(value - target) < 0.004:
            return mid
        if value > target:      # retaining too many -> increase the parameter
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def solve(cohort, start: np.ndarray, rounds: int = 4) -> np.ndarray:
    """Alternating bisection: intercept against the light anchor, cumulative
    slope against the heavy one, repeated until both settle.

    The two anchors are near-separable — a light protocol accumulates little
    burden so the slope barely bites, while a heavy one is dominated by it — which
    is exactly why this converges in a handful of rounds.
    """
    intercept, slope = float(start[0]), float(start[1])

    for round_index in range(rounds):
        intercept = _bisect(
            lambda value: retention(cohort, LIGHT[1], value, slope),
            lo=-9.0, hi=-3.5, target=LIGHT[2],
        )
        slope = _bisect(
            lambda value: retention(cohort, HEAVY[1], intercept, value),
            lo=0.0, hi=3.0, target=HEAVY[2],
        )
        light_now = retention(cohort, LIGHT[1], intercept, slope)
        heavy_now = retention(cohort, HEAVY[1], intercept, slope)
        print(f"  round {round_index}: intercept={intercept:+.3f} slope={slope:+.3f}"
              f"  light={light_now:.1%} heavy={heavy_now:.1%}")
        if abs(light_now - LIGHT[2]) < 0.02 and abs(heavy_now - HEAVY[2]) < 0.02:
            break

    return np.array([intercept, slope])


def main() -> None:
    cohort = generate_cohort("type 2 diabetes", COHORT_N, seed=SEED, as_of=AS_OF)
    start = np.array([
        DROPOUT_HAZARD.params["intercept"],
        DROPOUT_HAZARD.params["cumulative_burden_weight"],
    ])

    print(f"anchors: light -> {LIGHT[2]:.0%}, heavy -> {HEAVY[2]:.0%}")
    print(f"starting from intercept={start[0]:+.3f} slope={start[1]:+.3f}\n")
    fitted = solve(cohort, start)

    print(f"\nFITTED  intercept={fitted[0]:+.4f}  cumulative_burden_weight={fitted[1]:+.4f}\n")
    print(f"{'design':<22}{'retention':>10}{'target':>10}")
    for label, protocol, target in (LIGHT, HEAVY, HELD_OUT):
        got = retention(cohort, protocol, fitted[0], fitted[1])
        marker = f"{target:.0%}" if target is not None else "held out"
        print(f"{label:<22}{got:>9.1%}{marker:>10}")

    print(
        "\nPaste the fitted values into assumptions.py `timeline.dropout_hazard`.\n"
        "The held-out design is the validation: if it lands in a plausible band "
        "without having been fitted, the two-parameter form generalises."
    )


if __name__ == "__main__":
    main()
