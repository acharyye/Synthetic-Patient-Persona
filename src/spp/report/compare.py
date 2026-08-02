"""Cohort comparison — distributional across seeds, paired only within identity.

The distinction this module exists to enforce:

**Within a run**, common random numbers make a paired diff exact. Same persona,
one design change, and the delta *is* the signal — that is what the flip table
reports and why it can name seven people.

**Across seeds**, persona `i` under seed 42 and persona `i` under seed 1234 are
two independent draws from the same distribution. Exchangeable strangers. A
per-pair delta between them is pure sampling noise, and rendering it in the same
visual language as a flip table lends noise the authority that table earned for
signal. A reader who learned to trust one will trust the other.

So the mode is not a preference:

    identity pairing  -> per-persona rows permitted
    anything else     -> distributional only, no per-persona rows, ever

That is an invariant with a test, not a dropdown. Positional pairing survives
only as `determinism_debug` — useful for checking that generation is
reproducible, labelled as such on its face, and still forbidden from emitting
per-persona rows.

Distributional comparison reuses the contract machinery: both cohorts are scored
against the *same* pack targets and the pack's *own* tolerances, so the question
becomes "do both satisfy the contract, and how far apart are they" rather than
"did persona 7 change".
"""
from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from ..cohort import cohort_summary, generate_cohort
from ..schemas import PatientDNA
from .diffwalk import ArtifactDiff, diff_artifacts
from .studio import MarginalBand, studio_view

CompareMode = Literal["identity", "distributional", "determinism_debug"]


class MarginalComparison(BaseModel):
    """One marginal in both cohorts, against the pack's own target and band."""

    field: str
    category: str | None = None
    target: float
    tolerance: float
    left: float
    right: float
    source: str
    confidence: str

    @property
    def delta(self) -> float:
        return round(self.right - self.left, 4)

    @property
    def left_within(self) -> bool:
        return abs(self.left - self.target) <= self.tolerance

    @property
    def right_within(self) -> bool:
        return abs(self.right - self.target) <= self.tolerance

    @property
    def both_within(self) -> bool:
        return self.left_within and self.right_within

    @property
    def notable(self) -> bool:
        """A delta only means something once one side leaves the band."""
        return not self.both_within


class PersonaChange(BaseModel):
    """Only ever emitted under identity pairing. See the module docstring."""

    patient_id: str
    changed_paths: list[str] = Field(default_factory=list)


class CohortComparison(BaseModel):
    left: str
    right: str
    mode: CompareMode
    n: int

    marginals: list[MarginalComparison] = Field(default_factory=list)
    summary_diff: ArtifactDiff
    # Populated ONLY when mode == "identity". Enforced, not merely documented.
    persona_changes: list[PersonaChange] = Field(default_factory=list)
    note: str = ""

    @property
    def out_of_band(self) -> list[MarginalComparison]:
        return [m for m in self.marginals if m.notable]

    def headline(self) -> str:
        if self.mode == "identity":
            return (
                f"{len(self.persona_changes)} of {self.n} personas changed "
                f"(paired by identity — deltas are signal)"
            )
        drifted = len(self.out_of_band)
        return (
            f"{len(self.marginals) - drifted} of {len(self.marginals)} marginals "
            "agree within the pack's tolerance"
        )


def _bands_by_key(bands: list[MarginalBand]) -> dict[tuple[str, str | None], MarginalBand]:
    return {(band.field, band.category): band for band in bands}


def compare_cohorts(
    condition: str,
    left_seed: int,
    right_seed: int,
    n: int = 300,
    as_of: date | None = None,
    allow_determinism_debug: bool = False,
) -> CohortComparison:
    """Compare two cohorts, choosing the only defensible mode for the inputs."""
    left = generate_cohort(condition, n, seed=left_seed, as_of=as_of)
    right = generate_cohort(condition, n, seed=right_seed, as_of=as_of)

    left_ids = {p.patient_id for p in left}
    shared = sorted(left_ids & {p.patient_id for p in right})
    summary_diff = diff_artifacts(cohort_summary(left), cohort_summary(right))

    if shared:
        return _identity_comparison(
            condition, left, right, shared, left_seed, right_seed, summary_diff
        )

    if allow_determinism_debug:
        # Positional, and it says so. For checking generation reproducibility,
        # never for reading population difference.
        return CohortComparison(
            left=f"{condition}@seed{left_seed}", right=f"{condition}@seed{right_seed}",
            mode="determinism_debug", n=len(left),
            marginals=_marginal_comparison(condition, left_seed, right_seed, n, as_of),
            summary_diff=summary_diff,
            persona_changes=[],
            note=(
                "DETERMINISM DEBUG ONLY. Personas are paired by position, but two "
                "seeds draw independent samples — per-pair deltas here are "
                "sampling noise, not population difference. Per-persona rows are "
                "withheld deliberately."
            ),
        )

    return CohortComparison(
        left=f"{condition}@seed{left_seed}", right=f"{condition}@seed{right_seed}",
        mode="distributional", n=len(left),
        marginals=_marginal_comparison(condition, left_seed, right_seed, n, as_of),
        summary_diff=summary_diff,
        persona_changes=[],
        note=(
            "Compared distributionally. These cohorts share no persona identities, "
            "so persona i on each side is an independent draw — a per-pair delta "
            "would be sampling noise wearing the flip table's clothes. Both sides "
            "are scored against the same pack targets and tolerances instead."
        ),
    )


def _identity_comparison(
    condition: str,
    left: list[PatientDNA],
    right: list[PatientDNA],
    shared: list[str],
    left_seed: int,
    right_seed: int,
    summary_diff: ArtifactDiff,
) -> CohortComparison:
    left_by_id = {p.patient_id: p.model_dump(mode="json") for p in left}
    right_by_id = {p.patient_id: p.model_dump(mode="json") for p in right}

    changes = []
    for patient_id in shared:
        diff = diff_artifacts(left_by_id[patient_id], right_by_id[patient_id])
        if diff.changed:
            changes.append(PersonaChange(
                patient_id=patient_id, changed_paths=diff.paths()[:12]))

    return CohortComparison(
        left=f"{condition}@seed{left_seed}", right=f"{condition}@seed{right_seed}",
        mode="identity", n=len(shared),
        marginals=[], summary_diff=summary_diff, persona_changes=changes,
        note=(
            "Paired by persona identity: the same person on both sides, so a "
            "per-persona delta is signal."
        ),
    )


def _marginal_comparison(
    condition: str, left_seed: int, right_seed: int, n: int, as_of: date | None
) -> list[MarginalComparison]:
    """The contract machinery pointed at two cohorts rather than one."""
    left_bands = _bands_by_key(studio_view(condition, n=n, seed=left_seed, as_of=as_of).bands)
    right_bands = _bands_by_key(studio_view(condition, n=n, seed=right_seed, as_of=as_of).bands)

    out: list[MarginalComparison] = []
    for key in sorted(set(left_bands) & set(right_bands), key=lambda k: (k[0], k[1] or "")):
        left_band, right_band = left_bands[key], right_bands[key]
        out.append(MarginalComparison(
            field=left_band.field, category=left_band.category,
            target=left_band.target, tolerance=left_band.tolerance,
            left=left_band.observed, right=right_band.observed,
            source=left_band.source, confidence=left_band.confidence,
        ))
    return out
