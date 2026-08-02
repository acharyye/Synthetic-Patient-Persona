"""Sensitivity analysis: the fork mechanism pointed at the ledger.

Perturbing an assumption is the same operation as changing a design — run,
change one thing, re-run with identical seeds, count flips. So this is a thin
loop over `counterfactual.fork`, not a separate subsystem. The only difference is
what gets mutated: a ledger coefficient instead of a schedule.

What it answers: "results are robust to the adherence heuristic; highly sensitive
to the travel burden weight." That turns "your heuristics are made up" from an
attack into a ranked, reproducible table — which is the entire point of having
an assumption ledger in the first place.

Read the ranking, not the magnitudes. A perturbation of ±20% on a coefficient
that was expert judgement to begin with produces a flip count whose absolute
value means little; which coefficients dominate the ranking is the finding.
"""
from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from pydantic import BaseModel, Field

from ..foundation.ledger import LEDGER, Assumption
from ..schemas import PatientDNA
from .counterfactual import diff_runs
from .schedule import VisitSchedule
from .timeline import simulate_cohort


class SensitivityEntry(BaseModel):
    assumption: str
    confidence: str
    factor: float
    net_flips: int
    retention_delta: float
    flipped: int = Field(description="personas whose outcome moved, either way")

    @property
    def impact(self) -> int:
        """Magnitude, direction-agnostic — the ranking key."""
        return abs(self.net_flips)


class SensitivityReport(BaseModel):
    perturbation: float
    n: int
    baseline_retained: int
    entries: list[SensitivityEntry] = Field(default_factory=list)

    def most_sensitive(self, limit: int = 5) -> list[SensitivityEntry]:
        return self.entries[:limit]

    def headline(self) -> str:
        if not self.entries:
            return "no assumptions perturbed"
        top = self.entries[0]
        robust = [e.assumption for e in self.entries if e.impact == 0]
        text = (
            f"most sensitive to {top.assumption} "
            f"({top.net_flips:+d} flips at {self.perturbation:+.0%})"
        )
        if robust:
            text += f"; robust to {len(robust)} of {len(self.entries)} assumptions"
        return text


@contextmanager
def perturbed(assumption: Assumption, factor: float) -> Iterator[None]:
    """Temporarily scale every numeric parameter of one assumption.

    Restores on exit even if the simulation raises — a leaked perturbation would
    silently corrupt every later run in the process, which is exactly the kind of
    bug that produces a confident wrong table.
    """
    original = dict(assumption.params)
    try:
        assumption.params.update(LEDGER.perturbed(assumption.name, factor))
        yield
    finally:
        assumption.params.clear()
        assumption.params.update(original)


def run_sensitivity(
    cohort: list[PatientDNA],
    schedule: VisitSchedule,
    perturbation: float = 0.2,
    seed: int = 42,
    condition: str | None = None,
    only: list[str] | None = None,
) -> SensitivityReport:
    """Perturb each assumption in turn, CRN-paired against one baseline run."""
    baseline = simulate_cohort(cohort, schedule, seed=seed, condition=condition)
    baseline_retained = sum(
        1 for log in baseline.values()
        if not any(event.type.value == "dropped_out" for event in log)
    )

    names = only if only is not None else [
        a.name for a in LEDGER
        # Only assumptions the simulation actually consumes can move an outcome.
        if any(tag in a.tags for tag in ("timeline", "hazard", "burden", "traits"))
    ]

    entries: list[SensitivityEntry] = []
    for name in names:
        assumption = LEDGER.get(name)
        if not any(
            isinstance(v, (int, float)) and not isinstance(v, bool)
            for v in assumption.params.values()
        ):
            continue

        with perturbed(assumption, 1.0 + perturbation):
            variant = simulate_cohort(
                cohort, schedule, seed=seed, condition=condition
            )

        diff = diff_runs(baseline, variant, schedule.duration_days, label=name)
        entries.append(SensitivityEntry(
            assumption=name,
            confidence=assumption.confidence.value,
            factor=1.0 + perturbation,
            net_flips=diff.net_flips,
            retention_delta=diff.retention_delta,
            flipped=len(diff.recovered) + len(diff.lost),
        ))

    entries.sort(key=lambda entry: (-entry.impact, entry.assumption))
    return SensitivityReport(
        perturbation=perturbation,
        n=len(cohort),
        baseline_retained=baseline_retained,
        entries=entries,
    )
