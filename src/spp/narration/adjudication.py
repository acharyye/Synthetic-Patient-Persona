"""Adjudicate a v3 run against the shape registered before it existed.

The failure this exists to prevent is not a wrong number — it is a *reading*
chosen after the numbers arrive. "Burden recovered to 0.58, close enough" and
"the controls moved a little but so did everything" are both available to anyone
holding the report and the file at the same time, and neither is dishonest in the
moment. So the decision procedure is code: the arms come from
`tests/eval/v3_expected_shape.json`, the thresholds are read rather than
transcribed, and the verdict follows the tree the file already committed to.

Nothing here chooses a bar. If an arm turns out to be wrong, that is a separate
explicit commit against the shape file — never a change made in the same breath
as reporting a result against it.

The reading protocol the arms encode:

    recovery passes AND controls hold      -> the state ids did the work
    recovery passes AND controls move too  -> OVER-CORRECTION, however good
                                              burden looks
    recovery fails                         -> the diagnosis was incomplete;
                                              investigate what else moved, and do
                                              NOT adjust the file to fit

`state_coverage` is what the recovery has to be caused BY. Recovery without state
ids present is the over-correction signature in its purest form: the same
segments relabelled `factual`, grounded in nothing new.
"""
from __future__ import annotations

import json
from pathlib import Path

from pydantic import BaseModel, Field

from .bundle import refresh_readme
from .evaluation import BATTERY_PATH, ComplianceReport

SHAPE_PATH = BATTERY_PATH.parent / "v3_expected_shape.json"


class ArmResult(BaseModel):
    """One pre-registered arm, read against what happened."""

    arm: str
    metric: str
    observed: float
    bound: str
    passed: bool
    note: str = ""

    def line(self) -> str:
        mark = "PASS" if self.passed else "MISS"
        return f"[{mark}] {self.arm}.{self.metric}: {self.observed:.4g} ({self.bound})"


class Adjudication(BaseModel):
    """The verdict, plus everything needed to disbelieve it."""

    registered_on: str
    amendments: list[dict] = Field(default_factory=list)
    arms: list[ArmResult] = Field(default_factory=list)
    reading: str = ""
    caveats: list[str] = Field(default_factory=list)

    @property
    def failures(self) -> list[ArmResult]:
        return [arm for arm in self.arms if not arm.passed]

    def by_arm(self, name: str) -> list[ArmResult]:
        return [arm for arm in self.arms if arm.arm == name]

    def report(self) -> str:
        lines = [f"v3 adjudication against a shape registered {self.registered_on}"]
        if self.amendments:
            lines.append(
                f"  ({len(self.amendments)} amendment(s), all before any recording)"
            )
        lines.append("")
        lines.extend("  " + arm.line() for arm in self.arms)
        lines.append("")
        lines.append(f"READING: {self.reading}")
        if self.caveats:
            lines.append("")
            lines.append("CAVEATS — read these before quoting anything above:")
            lines.extend("  - " + caveat for caveat in self.caveats)
        return "\n".join(lines)


def _bounded(value: float, low: float | None, high: float | None) -> tuple[bool, str]:
    if low is not None and high is not None:
        return low <= value <= high, f"expected {low}..{high}"
    if low is not None:
        return value >= low, f"floor {low}"
    return value <= high, f"ceiling {high}"


def adjudicate(
    report: ComplianceReport,
    quarantined: int = 0,
    shape_path: Path = SHAPE_PATH,
) -> Adjudication:
    """Read one v3 report against the pre-registered arms.

    `quarantined` is the number of responses the recorder refused, which lives in
    the quarantine file rather than in the report — a take that failed the gate
    was never scored, so a run can look clean precisely because its failures went
    somewhere else. The holds_from_v2 arm exists to make that visible.
    """
    shape = json.loads(shape_path.read_text(encoding="utf-8"))
    arms_spec = shape["arms"]
    results: list[ArmResult] = []
    tags = report.factual_fraction_by_tag

    # --- recovery: burden and mitigation, each inside its own band ---
    recovery = arms_spec["recovery"]
    for tag in recovery["tags"]:
        observed = tags.get(tag, 0.0)
        passed, bound = _bounded(
            observed, recovery["floor"][tag], recovery["ceiling"][tag]
        )
        results.append(ArmResult(
            arm="recovery", metric=tag, observed=observed, bound=bound,
            passed=passed,
            note=recovery["on_miss_low"] if observed < recovery["floor"][tag]
            else (recovery["on_miss_high"] if not passed else ""),
        ))

    # --- control: graph-knowledge tags gained nothing and must not move ---
    control = arms_spec["control"]
    tolerance = control["tolerance_abs"]
    for tag in control["tags"]:
        observed = tags.get(tag, 0.0)
        reference = control["v2_reference"][tag]
        drift = abs(observed - reference)
        results.append(ArmResult(
            arm="control", metric=tag, observed=observed,
            bound=f"within {tolerance} of v2's {reference}",
            passed=drift <= tolerance,
            note=control["on_miss"] if drift > tolerance else "",
        ))

    # --- what the recovery has to be caused BY ---
    coverage = arms_spec["state_coverage"]
    passed, bound = _bounded(report.state_coverage, coverage["min"], None)
    results.append(ArmResult(
        arm="state_coverage", metric="state_coverage",
        observed=report.state_coverage, bound=bound, passed=passed,
        note=coverage["$comment"],
    ))

    # --- the persona must still be allowed to merely feel ---
    floor = arms_spec["feeling_floor"]
    passed, bound = _bounded(report.feeling_fraction, floor["min"], None)
    results.append(ArmResult(
        arm="feeling_floor", metric="feeling_fraction",
        observed=report.feeling_fraction, bound=bound, passed=passed,
        note=floor["rationale"],
    ))

    # --- graph recall must not be cannibalised by the easier citation path ---
    f_arm = arms_spec["f_recall_holds_independently"]
    passed, bound = _bounded(report.f_recall, f_arm["min"], None)
    results.append(ArmResult(
        arm="f_recall_holds_independently", metric="f_recall",
        observed=report.f_recall, bound=bound, passed=passed,
        note=f_arm["on_miss"] if not passed else "",
    ))

    # --- things that were true in v2 and must stay true ---
    holds = arms_spec["holds_from_v2"]
    observed_holds = {
        "quarantine": float(quarantined),
        "compliance_rate": 1.0 - report.hard_failure_rate,
        "citation_validity": report.citation_validity,
        "parse_failure_rate": report.parse_failure_rate,
        "inline_marker_takes": float(report.inline_marker_takes),
    }
    for metric, spec in holds.items():
        if metric not in observed_holds:
            continue
        value = observed_holds[metric]
        passed, bound = _bounded(value, spec.get("min"), spec.get("max"))
        results.append(ArmResult(
            arm="holds_from_v2", metric=metric, observed=value,
            bound=bound, passed=passed, note=spec.get("$comment", ""),
        ))

    return Adjudication(
        registered_on=shape["registered_on"],
        amendments=shape.get("amendments", []),
        arms=results,
        reading=_read(results, report),
        caveats=_caveats(report),
    )


def _read(arms: list[ArmResult], report: ComplianceReport) -> str:
    """Follow the tree the shape file committed to. No new judgement here."""
    recovery = [a for a in arms if a.arm == "recovery"]
    control = [a for a in arms if a.arm == "control"]
    coverage = next(a for a in arms if a.arm == "state_coverage")

    recovered = all(a.passed for a in recovery)
    controls_held = all(a.passed for a in control)

    def ceiling_of(arm: ArmResult) -> float:
        return float(arm.bound.split("..")[1])

    def floor_of(arm: ArmResult) -> float:
        return float(arm.bound.split()[1].split("..")[0])

    too_high = [a for a in recovery if not a.passed and a.observed > ceiling_of(a)]
    too_low = [a for a in recovery if not a.passed and a.observed < floor_of(a)]

    # Both directions at once is a collapse plus an overshoot, and the collapse is
    # the more informative half — a tag that did not recover falsifies the
    # diagnosis whatever another tag did.
    if too_high and not too_low:
        return (
            "OVER-CORRECTION: burden and/or mitigation went past the ceiling. The "
            "model is labelling feeling as factual to use the new ids. See "
            "feeling_floor."
        )
    if not recovered:
        return (
            "DIAGNOSIS INCOMPLETE: factual_fraction did not recover once the ids "
            "existed, so the v2 reclassification had a second cause. Do NOT adjust "
            "the shape file to fit — investigate what else moved and record it."
        )
    if not controls_held:
        return (
            "OVER-CORRECTION: burden and mitigation recovered, but the "
            "graph-knowledge controls moved with them. Everything rising together "
            "is not the new ids doing their job, however good the burden numbers "
            "look."
        )
    if not coverage.passed:
        return (
            "RECOVERY WITHOUT STATE CITATION: the tags recovered while "
            "state_coverage stayed below its floor, which means the segments were "
            "relabelled rather than grounded. This is the over-correction "
            "signature in its purest form."
        )
    return (
        "RECOVERY: burden and mitigation recovered, the graph-knowledge controls "
        "held flat, and the recovery came with state ids attached. The "
        "state-citation gap was the cause."
    )


def _caveats(report: ComplianceReport) -> list[str]:
    """What a reader must know before quoting any figure above.

    These are not hedges. Each one names a specific way a number here could be
    read as saying more than it does.
    """
    caveats = [
        "model_recall and system_recall are NOT comparable to v0.1 or v0.3: those "
        "graded flat sets of retrieval-derived ids, this grades authored must/may "
        "groups. The pass_bars.json bars for them were registered against the "
        "older instrument. f_recall is the graph-recall reading for v3.",
        f"State ids make up {report.state_citation_share:.0%} of the citations in "
        "this run, and roughly 64% of the enum by construction. A rise in state "
        "citation is partly a volume effect; f_recall is what separates the two.",
    ]
    if report.circumstantial_segments < 10:
        caveats.append(
            f"only {report.circumstantial_segments} circumstantial segments across "
            "the battery — state_coverage is a ratio over very little, and its "
            "verdict is correspondingly weak."
        )
    if report.single_segment_rate > 0.3:
        caveats.append(
            f"{report.single_segment_rate:.0%} of takes are a single segment. No "
            "metric here catches degeneracy; read the raw takes before believing "
            "any of this."
        )
    return caveats


def adjudicate_bundle(directory: Path, shape_path: Path = SHAPE_PATH) -> Adjudication:
    """Read an archived bundle against the shape, and leave the verdict in it.

    Deliberately a read over `compliance.json` and `quarantine.json` rather than
    a step inside recording: the run and the reading of the run are separate
    acts, and keeping them separate is what lets the verdict be re-derived from
    an archived bundle by anyone who doubts it. The written file is a
    convenience for that reader, never the source — delete it and this function
    reproduces it exactly.
    """
    compliance = json.loads((directory / "compliance.json").read_text(encoding="utf-8"))
    quarantine_path = directory / "quarantine.json"
    quarantined = (
        json.loads(quarantine_path.read_text(encoding="utf-8"))["count"]
        if quarantine_path.exists() else 0
    )
    verdict = adjudicate(
        ComplianceReport.model_validate(compliance["report"]),
        quarantined=quarantined,
        shape_path=shape_path,
    )
    (directory / "adjudication.json").write_text(
        json.dumps(verdict.model_dump(), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    refresh_readme(directory)
    return verdict
