"""Synthea-vs-prior: the table that is read BEFORE any value is adopted.

`diff_before_adopt` in `tests/eval/synthea_targets.json` says a Synthea-derived
value is reported next to the prior it would replace, per entry, and that a large
disagreement is investigated rather than adopted. This module produces that
table and nothing else. **It writes no pack.**

Every threshold is read from where it was registered, never restated here:

* the sample-size floor comes from `sample_size_discipline.n_threshold`;
* "disagrees" means *further from the prior than the pack entry's own
  `tolerance`* (`disagreement_threshold`);
* which fields may be calibrated at all comes from `synthea_can_calibrate`.

Two properties are enforced rather than remembered.

**A structural run feeds no target.** An export whose MANIFEST declares itself
structural-validation-only — or carries no MANIFEST — yields a table marked
`feeds_targets = False`, and no row in it can read `within_tolerance` or
`disagrees`: every verdict is forced to `illustrative`. The two-run rule was
registered so nobody could size a decision on the 113-patient run; here it cannot
be done by accident.

**A row never upgrades itself.** Below the floor the verdict is `n_too_small`
whatever the value looks like. A field Synthea cannot source says `not_sourced`
with the reason. A medication row carries an observed rate and no verdict: the
pack's ladder holds an order, not a rate, so there is no prior to disagree with.
"""
from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from ..cohort.packs import PriorPack
from .synthea_loader import FIELDS_NOT_SOURCED, CodeMap, SyntheaLoad

TARGETS_PATH = Path(__file__).resolve().parents[3] / "tests" / "eval" / "synthea_targets.json"

Verdict = Literal[
    "within_tolerance", "disagrees", "n_too_small", "not_sourced",
    "no_prior", "illustrative",
]


class Row(BaseModel):
    entry: str
    n: int
    synthea: float | None = None
    prior: float | None = None
    tolerance: float | None = None
    verdict: Verdict
    note: str = ""

    @property
    def delta(self) -> float | None:
        if self.synthea is None or self.prior is None:
            return None
        return self.synthea - self.prior


class DerivationTable(BaseModel):
    condition: str
    n: int
    n_threshold: int
    feeds_targets: bool
    why_not: str = ""
    deceased_excluded: int = 0
    source: dict = Field(default_factory=dict)
    rows: list[Row] = Field(default_factory=list)

    def render(self) -> str:
        head = (f"Synthea vs prior — {self.condition} — n={self.n} "
                f"(floor {self.n_threshold}), {self.deceased_excluded} deceased excluded")
        lines = [head, "=" * len(head)]
        if not self.feeds_targets:
            lines.append(f"FEEDS NO TARGET: {self.why_not}")
        lines.append(f"{'entry':38} {'n':>4} {'synthea':>9} {'prior':>8} {'tol':>6} {'delta':>8}  verdict")
        for r in self.rows:
            fmt = lambda v: "—" if v is None else f"{v:.3f}"  # noqa: E731
            lines.append(f"{r.entry:38} {r.n:>4} {fmt(r.synthea):>9} {fmt(r.prior):>8} "
                         f"{fmt(r.tolerance):>6} {fmt(r.delta):>8}  {r.verdict}"
                         + (f"  ({r.note})" if r.note else ""))
        return "\n".join(lines)


def _is_structural(manifest: dict) -> str:
    """Why this export may not feed a target, or '' if it may."""
    if not manifest:
        return "the export carries no MANIFEST, so the run that produced it cannot be named"
    if "structural" in str(manifest.get("purpose", "")).lower():
        return "its MANIFEST declares a structural-validation run"
    return ""


def derive(load: SyntheaLoad, pack: PriorPack, targets_path: Path = TARGETS_PATH) -> DerivationTable:
    """Compare what the export says about `pack.condition` with the pack's priors."""
    targets = json.loads(Path(targets_path).read_text(encoding="utf-8"))
    floor = int(targets["sample_size_discipline"]["n_threshold"]["value"])
    may_calibrate = set(targets["synthea_can_calibrate"])
    stage_declined = "stage_is_not_sourced" in targets

    people = [p for p in load.patients if p.condition.casefold() == pack.condition.casefold()]
    n = len(people)
    why_not = _is_structural(load.report.manifest)
    table = DerivationTable(
        condition=pack.condition, n=n, n_threshold=floor,
        feeds_targets=not why_not, why_not=why_not,
        deceased_excluded=load.report.deceased_excluded,
        source={k: load.report.manifest.get(k) for k in ("jar_sha256", "seed", "population_flag")},
    )

    def verdict(value: float, prior: float, tolerance: float) -> Verdict:
        if n < floor:
            return "n_too_small"
        if why_not:
            return "illustrative"
        return "within_tolerance" if abs(value - prior) <= tolerance else "disagrees"

    by_field = {m.field: m for m in pack.marginals}

    if "age" in may_calibrate and "age" in by_field and n:
        spec = by_field["age"]
        mean = math.fsum(p.age for p in people) / n
        table.rows.append(Row(entry="age (mean)", n=n, synthea=mean,
                              prior=float(spec.params["mean"]), tolerance=spec.tolerance,
                              verdict=verdict(mean, float(spec.params["mean"]), spec.tolerance)))

    if "sex" in may_calibrate and "sex" in by_field and n:
        spec = by_field["sex"]
        for level, prior in spec.params.items():
            share = sum(1 for p in people if p.sex == level) / n
            table.rows.append(Row(entry=f"sex = {level}", n=n, synthea=share, prior=float(prior),
                                  tolerance=spec.tolerance,
                                  verdict=verdict(share, float(prior), spec.tolerance)))

    if "comorbidities" in may_calibrate and "comorbidities" in by_field and n:
        spec = by_field["comorbidities"]
        seen = {name for p in load.patients for name in p.comorbidities}
        mappable = set(CodeMap.load().comorbidity_of.values())
        for name, prior in spec.params.items():
            if name not in mappable:
                table.rows.append(Row(entry=f"comorbidity: {name}", n=n, prior=float(prior),
                                      tolerance=spec.tolerance, verdict="not_sourced",
                                      note="no Synthea code observed for it"))
                continue
            rate = sum(1 for p in people if name in p.comorbidities) / n
            table.rows.append(Row(
                entry=f"comorbidity: {name}", n=n, synthea=rate, prior=float(prior),
                tolerance=spec.tolerance, verdict=verdict(rate, float(prior), spec.tolerance),
                note="" if name in seen else "mapped, zero occurrences in this export",
            ))

    if "medication_ladder" in may_calibrate and "medication_ladder" in by_field and n:
        for drug, _dose in by_field["medication_ladder"].params["rungs"]:
            rate = sum(1 for p in people if drug in p.medications) / n
            table.rows.append(Row(entry=f"on {drug}", n=n, synthea=rate, verdict="no_prior",
                                  note="membership only — the ladder holds an order, not a rate"))

    if stage_declined and "stage" in by_field:
        table.rows.append(Row(entry="stage", n=n, verdict="not_sourced",
                              note=FIELDS_NOT_SOURCED["stage"]))
    for name in sorted(set(targets["synthea_cannot_calibrate"]) & set(by_field)):
        table.rows.append(Row(entry=name, n=n, verdict="not_sourced",
                              note="outside the registered target list"))
    return table
