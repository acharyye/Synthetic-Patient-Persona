"""Cohort Studio: marginals against pack targets, and cohort diff.

Two rules, both about not creating a second source of truth.

**Tolerance bands come from the pack entries themselves**, never transcribed.
Each `MarginalSpec` already carries its own `tolerance`, and the pack-generated
contract suite asserts against exactly that number — so these charts are the 181
contract tests made visible, reading the same field. A band drawn from a constant
in this module would be a second copy that drifts, and the chart would eventually
show green while the test went red.

**The diff view reuses the leaf-walker** from `diffwalk.py` rather than growing
its own comparison logic. Two comparators would eventually disagree about what
"changed" means.
"""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from ..cohort import cohort_summary, generate_cohort
from ..cohort.packs import PriorPack, pack_for
from ..schemas import PatientDNA
from .diffwalk import ArtifactDiff, diff_artifacts


class MarginalBand(BaseModel):
    """One field's observed value against the band the pack itself declares."""

    field: str
    family: str
    category: str | None = None
    target: float
    tolerance: float
    observed: float
    # Provenance travels with the number, as everywhere else.
    source: str
    confidence: str
    structural_paths: list[str] = Field(default_factory=list)

    @property
    def within(self) -> bool:
        return abs(self.observed - self.target) <= self.tolerance

    @property
    def deviation(self) -> float:
        return round(self.observed - self.target, 4)


class StudioView(BaseModel):
    condition: str
    pack: str
    pack_version: int
    n: int
    seed: int
    summary: dict = Field(default_factory=dict)
    bands: list[MarginalBand] = Field(default_factory=list)

    @property
    def out_of_band(self) -> list[MarginalBand]:
        return [band for band in self.bands if not band.within]

    def headline(self) -> str:
        bad = len(self.out_of_band)
        return (
            f"{len(self.bands) - bad} of {len(self.bands)} marginals within the "
            f"tolerance the pack declares"
        )


def _categorical_bands(
    pack: PriorPack, cohort: list[PatientDNA], field: str
) -> list[MarginalBand]:
    spec = pack.marginal(field)
    values = [getattr(persona, field) for persona in cohort]
    values = [str(v) for v in values if v is not None]
    total = len(values) or 1

    bands = []
    for category, target in spec.params.items():
        observed = sum(1 for v in values if v == category) / total
        bands.append(MarginalBand(
            field=field, family=spec.family, category=category,
            target=float(target), tolerance=spec.tolerance, observed=round(observed, 4),
            source=spec.provenance.source, confidence=spec.provenance.confidence.value,
            structural_paths=spec.structural_paths,
        ))
    return bands


def studio_view(
    condition: str, n: int = 300, seed: int = 42, as_of: date | None = None
) -> StudioView:
    """Marginal bands for one cohort, every threshold read from the pack."""
    pack = pack_for(condition)
    cohort = generate_cohort(condition, n, seed=seed, as_of=as_of)
    summary = cohort_summary(cohort)

    if pack is None:
        return StudioView(
            condition=condition, pack="generic", pack_version=0,
            n=n, seed=seed, summary=summary,
        )

    bands: list[MarginalBand] = []

    # Continuous fields: compare the mean against the pack's own mean/tolerance.
    age_spec = pack.marginal("age")
    bands.append(MarginalBand(
        field="age", family=age_spec.family, target=float(age_spec.params["mean"]),
        tolerance=age_spec.tolerance, observed=float(summary["age_mean"]),
        source=age_spec.provenance.source,
        confidence=age_spec.provenance.confidence.value,
        structural_paths=age_spec.structural_paths,
    ))

    for field in ("sex", "stage", "health_literacy"):
        bands.extend(_categorical_bands(pack, cohort, field))

    # Comorbidities are bernoulli_set and structurally modulated — the pack says
    # so, and the band is drawn from its own (wider) tolerance rather than a
    # number invented here.
    comorbidity_spec = pack.marginal("comorbidities")
    observed_prevalence = summary["comorbidity_prevalence"]
    for name, target in comorbidity_spec.params.items():
        bands.append(MarginalBand(
            field="comorbidities", family=comorbidity_spec.family, category=name,
            target=float(target), tolerance=comorbidity_spec.tolerance,
            observed=float(observed_prevalence.get(name, 0.0)),
            source=comorbidity_spec.provenance.source,
            confidence=comorbidity_spec.provenance.confidence.value,
            structural_paths=comorbidity_spec.structural_paths,
        ))

    return StudioView(
        condition=condition, pack=pack.name, pack_version=pack.schema_version,
        n=n, seed=seed, summary=summary, bands=bands,
    )


# Cohort comparison moved to `compare.py`. The positional-pairing version that
# lived here rendered per-persona deltas between independent draws — sampling
# noise in the flip table's visual language. See compare.compare_cohorts.
