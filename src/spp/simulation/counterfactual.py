"""Fork-and-diff: the wind tunnel.

Run a scenario, change one thing, run it again with identical seeds, and read
what moved. Because every stochastic decision is keyed by stable identity
(`tests/test_seed_keying.py`), the two runs are **paired per persona** — common
random numbers — so the difference between them is the design change and
nothing else.

That pairing is why the primary object here is a **flip table**, not two
aggregate curves subtracted. A 2-point retention delta across two independent
runs of 1,000 personas is inside the noise; the same delta as "31 personas
flipped from dropped to retained, 11 the other way" is exact, and each flip
names the persona and the visit where the two trajectories diverged.

Scope: **forking is scenario-level, at t=0.** That covers the whole demo — drop
visit 3, make visit 5 remote, relax rule 7. Mid-trajectory forking (branch a
half-finished run) is real machinery for no current use case; the event logs
make it addable later without redesign.
"""
from __future__ import annotations

from typing import Callable, Literal

from pydantic import BaseModel, Field

from ..foundation.events import EventLog, EventType, JourneyStage, fold
from ..schemas import PatientDNA
from .schedule import VisitSchedule
from .survival import burden_breakdown, retention_summary, survival_curve
from .timeline import simulate_cohort

Outcome = Literal["retained", "dropped"]


class Flip(BaseModel):
    """One persona whose outcome changed. The unit of a counterfactual finding."""

    patient_id: str
    baseline: Outcome
    variant: Outcome
    # First event index where the two logs stop agreeing — where the design
    # change actually bit for this person.
    diverged_at_event: int | None = None
    diverged_at_day: int | None = None
    baseline_exit_reason: str | None = None
    variant_exit_reason: str | None = None
    baseline_exit_day: int | None = None
    variant_exit_day: int | None = None

    @property
    def recovered(self) -> bool:
        return self.baseline == "dropped" and self.variant == "retained"

    @property
    def lost(self) -> bool:
        return self.baseline == "retained" and self.variant == "dropped"


class DiffResult(BaseModel):
    """A paired comparison of two scenario runs."""

    label: str
    n: int
    baseline_retained: int
    variant_retained: int

    recovered: list[Flip] = Field(default_factory=list)
    lost: list[Flip] = Field(default_factory=list)
    # Personas whose logs differ but whose final outcome does not — the design
    # touched them without changing whether they finished.
    perturbed: int = 0
    unchanged: int = 0

    baseline_summary: dict = Field(default_factory=dict)
    variant_summary: dict = Field(default_factory=dict)
    baseline_curve: list[dict] = Field(default_factory=list)
    variant_curve: list[dict] = Field(default_factory=list)
    burden_shift: dict[str, float] = Field(default_factory=dict)

    @property
    def net_flips(self) -> int:
        """Positive means the change retained more people than it cost."""
        return len(self.recovered) - len(self.lost)

    @property
    def retention_delta(self) -> float:
        return round((self.variant_retained - self.baseline_retained) / self.n, 4) if self.n else 0.0

    def headline(self) -> str:
        return (
            f"{self.label}: {self.net_flips:+d} net "
            f"(+{len(self.recovered)} recovered, -{len(self.lost)} lost) "
            f"of {self.n}"
        )


def _outcome(log: EventLog) -> Outcome:
    return "dropped" if fold(log).stage == JourneyStage.DROPPED else "retained"


def _exit_details(log: EventLog) -> tuple[str | None, int | None]:
    events = log.of_type(EventType.DROPPED_OUT)
    if not events:
        return None, None
    return str(events[-1].payload.get("reason")), events[-1].t


def _divergence(baseline: EventLog, variant: EventLog) -> tuple[int | None, int | None]:
    """First event index where the logs disagree, and the day it happened."""
    for index, (left, right) in enumerate(zip(baseline.events, variant.events)):
        if (left.type, left.t, left.payload) != (right.type, right.t, right.payload):
            return index, right.t
    if len(baseline.events) != len(variant.events):
        shorter = min(len(baseline.events), len(variant.events))
        longer = baseline if len(baseline.events) > shorter else variant
        return shorter, longer.events[shorter].t
    return None, None


def diff_runs(
    baseline: dict[str, EventLog],
    variant: dict[str, EventLog],
    horizon: int,
    label: str = "counterfactual",
) -> DiffResult:
    """Pair two runs persona-by-persona and report what moved.

    Requires the runs to cover the same personas — pairing is the whole point,
    and silently comparing different populations would produce a plausible
    number that means nothing.
    """
    if set(baseline) != set(variant):
        missing = set(baseline) ^ set(variant)
        raise ValueError(
            f"runs cover different personas ({len(missing)} differ); a paired diff "
            "requires the same cohort on both sides"
        )

    recovered: list[Flip] = []
    lost: list[Flip] = []
    perturbed = 0
    unchanged = 0

    for patient_id in sorted(baseline):
        before, after = baseline[patient_id], variant[patient_id]
        before_outcome, after_outcome = _outcome(before), _outcome(after)

        if before_outcome == after_outcome:
            if before.model_dump() == after.model_dump():
                unchanged += 1
            else:
                perturbed += 1
            continue

        event_index, day = _divergence(before, after)
        before_reason, before_day = _exit_details(before)
        after_reason, after_day = _exit_details(after)
        flip = Flip(
            patient_id=patient_id,
            baseline=before_outcome,
            variant=after_outcome,
            diverged_at_event=event_index,
            diverged_at_day=day,
            baseline_exit_reason=before_reason,
            variant_exit_reason=after_reason,
            baseline_exit_day=before_day,
            variant_exit_day=after_day,
        )
        (recovered if flip.recovered else lost).append(flip)

    baseline_stats = retention_summary(baseline)
    variant_stats = retention_summary(variant)
    before_burden = burden_breakdown(baseline)
    after_burden = burden_breakdown(variant)

    return DiffResult(
        label=label,
        n=len(baseline),
        baseline_retained=baseline_stats["retained"],
        variant_retained=variant_stats["retained"],
        recovered=recovered,
        lost=lost,
        perturbed=perturbed,
        unchanged=unchanged,
        baseline_summary=baseline_stats,
        variant_summary=variant_stats,
        baseline_curve=survival_curve(baseline, horizon),
        variant_curve=survival_curve(variant, horizon),
        burden_shift={
            component: round(after_burden.get(component, 0.0) - value, 4)
            for component, value in before_burden.items()
        },
    )


def fork(
    cohort: list[PatientDNA],
    schedule: VisitSchedule,
    mutate: Callable[[VisitSchedule], VisitSchedule],
    seed: int = 42,
    label: str = "counterfactual",
    condition: str | None = None,
    washout: bool = False,
) -> DiffResult:
    """Run a scenario and its mutation under identical seeds, then diff.

    `mutate` must preserve visit identity for surviving visits — use the
    `VisitSchedule` mutation helpers rather than rebuilding a schedule, or the
    pairing breaks and the diff measures reshuffled randomness.
    """
    variant_schedule = mutate(schedule)
    baseline = simulate_cohort(
        cohort, schedule, seed=seed, condition=condition, washout=washout
    )
    variant = simulate_cohort(
        cohort, variant_schedule, seed=seed, condition=condition, washout=washout
    )
    return diff_runs(baseline, variant, schedule.duration_days, label=label)


def sign_is_stable(
    cohort_builder: Callable[[int], list[PatientDNA]],
    schedule: VisitSchedule,
    mutate: Callable[[VisitSchedule], VisitSchedule],
    seeds: tuple[int, ...] = (42, 1234),
    condition: str | None = None,
) -> dict:
    """Re-run the diff under a second master seed and report sign stability.

    For a small design change, the difference between an effect and a draw
    artifact is whether the net flip count keeps its sign when the population and
    the simulation are redrawn. Consistent with how the hazard calibration is
    checked — same honesty guard, same pattern.
    """
    results = [
        fork(cohort_builder(seed), schedule, mutate, seed=seed, condition=condition)
        for seed in seeds
    ]
    nets = [result.net_flips for result in results]
    signs = {(n > 0) - (n < 0) for n in nets}

    return {
        "seeds": list(seeds),
        "net_flips": nets,
        "retention_deltas": [r.retention_delta for r in results],
        "sign_stable": len(signs) == 1 and 0 not in signs,
        "verdict": (
            "consistent direction across seeds"
            if len(signs) == 1 and 0 not in signs
            else "DIRECTION NOT STABLE — treat as a draw artifact, not an effect"
        ),
    }
