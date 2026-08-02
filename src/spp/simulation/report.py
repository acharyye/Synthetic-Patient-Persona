"""The exportable run artifact.

One object per counterfactual run, carrying everything needed to defend the
result later: the flip table, exact attributions, the seeds every draw came
from, and a snapshot of the assumption ledger as it stood when the numbers were
produced.

The ledger snapshot is the point. A retention figure without its assumption
lineage is exactly the "realism theater" the roadmap warns about — plausible
output nobody can interrogate. Stamping the ledger in means a reader can see
which coefficients were expert judgement (`unquotable`) and re-run the sensitivity
loop against them.
"""
from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from ..foundation.ledger import LEDGER
from ..protocol.attribution import EligibilityAttribution
from .counterfactual import DiffResult

ARTIFACT_VERSION = 1

DISCLAIMER = (
    "Simulated under stated assumptions. Not a forecast, not medical advice, not "
    "regulatory evidence. Retention LEVELS are calibrated to plausibility targets "
    "rather than fitted to observed data — read the DIFFERENCE between designs, "
    "and check `sensitivity` and `assumptions` before quoting anything."
)


class RunProvenance(BaseModel):
    """Everything needed to reproduce the run exactly."""

    artifact_version: int = ARTIFACT_VERSION
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    master_seed: int
    cohort_seed_path: str | None = None
    condition: str
    cohort_size: int
    schedule_name: str
    schedule_visits: int
    duration_days: int


class DiffReport(BaseModel):
    """A counterfactual result, defensible on its own."""

    title: str
    provenance: RunProvenance
    change: str

    net_flips: int
    recovered: int
    lost: int
    perturbed: int
    unchanged: int
    retention_delta: float

    baseline_retention: float
    variant_retention: float
    burden_shift: dict[str, float] = Field(default_factory=dict)

    baseline_curve: list[dict] = Field(default_factory=list)
    variant_curve: list[dict] = Field(default_factory=list)

    # Named individuals, because "31 personas recovered" invites "which ones?"
    example_recovered: list[dict] = Field(default_factory=list)
    example_lost: list[dict] = Field(default_factory=list)

    eligibility_attribution: dict | None = None
    sign_stability: dict | None = None
    sensitivity: dict | None = None

    assumptions: dict = Field(default_factory=dict)
    disclaimer: str = DISCLAIMER

    def headline(self) -> str:
        direction = "recovers" if self.net_flips > 0 else "costs"
        return (
            f"{self.change}: {direction} {abs(self.net_flips)} of "
            f"{self.provenance.cohort_size} personas "
            f"({self.baseline_retention:.1%} -> {self.variant_retention:.1%} retention)"
        )


def build_report(
    diff: DiffResult,
    *,
    title: str,
    change: str,
    condition: str,
    master_seed: int,
    schedule_name: str,
    schedule_visits: int,
    duration_days: int,
    cohort_seed_path: str | None = None,
    eligibility: EligibilityAttribution | None = None,
    sign_stability: dict | None = None,
    sensitivity: dict | None = None,
    examples: int = 5,
) -> DiffReport:
    """Assemble the artifact. Pure — takes computed results, computes nothing."""
    return DiffReport(
        title=title,
        change=change,
        provenance=RunProvenance(
            master_seed=master_seed,
            cohort_seed_path=cohort_seed_path,
            condition=condition,
            cohort_size=diff.n,
            schedule_name=schedule_name,
            schedule_visits=schedule_visits,
            duration_days=duration_days,
        ),
        net_flips=diff.net_flips,
        recovered=len(diff.recovered),
        lost=len(diff.lost),
        perturbed=diff.perturbed,
        unchanged=diff.unchanged,
        retention_delta=diff.retention_delta,
        baseline_retention=diff.baseline_summary.get("retention_rate", 0.0),
        variant_retention=diff.variant_summary.get("retention_rate", 0.0),
        burden_shift=diff.burden_shift,
        baseline_curve=diff.baseline_curve,
        variant_curve=diff.variant_curve,
        example_recovered=[f.model_dump() for f in diff.recovered[:examples]],
        example_lost=[f.model_dump() for f in diff.lost[:examples]],
        eligibility_attribution=(
            {
                "headline": eligibility.headline(),
                "n_excluded": eligibility.n_excluded,
                "rules": [
                    {
                        **rule.model_dump(),
                        "shapley": round(rule.shapley, 3),
                        "shapley_share": round(rule.shapley_share, 4),
                    }
                    for rule in eligibility.rules
                ],
                "method": (
                    "Exact Shapley value of the exclusion veto game: each persona's "
                    "blame is split 1/|failing rules|. No sampling."
                ),
            }
            if eligibility is not None
            else None
        ),
        sign_stability=sign_stability,
        sensitivity=sensitivity,
        assumptions={
            **LEDGER.snapshot(),
            "unquotable": [a.name for a in LEDGER.unsupported()],
        },
    )
