"""The verdict: does this protocol change regress retention?

Runs the candidate under the baseline's exact seeds — common random numbers — so
the two runs are paired per persona and the difference is the design change
rather than a redraw. Reuses the existing paired-diff and closed-form Shapley
code; nothing statistical is invented here.

**The gate rule that matters:** FAIL requires the drop to exceed the threshold
*and* be sign-stable across two seeds. A drop that flips direction when the
population is redrawn is below the paired design's resolution, and failing a
build on it would be failing on noise — so it downgrades to WARN. The system
refuses to assert what its own method cannot distinguish.

Thresholds live in `ci/gates.json`, committed, chosen before any number exists.
Same discipline as `pass_bars.json`: a bar picked after seeing the result is not
a bar.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from ..cohort import generate_cohort
from ..foundation.events import JourneyStage, fold
from ..protocol import attribute_eligibility, screen
from ..simulation.counterfactual import diff_runs
from .baseline import Baseline, ConfigStamp, build_schedule, run_scenario
from .scenario_file import ScenarioFile

VERDICT_SCHEMA_VERSION = 1
DEFAULT_SECOND_SEED_OFFSET = 1192  # 42 -> 1234, the repo's existing pattern

Outcome = Literal["PASS", "WARN", "FAIL"]


class Gates(BaseModel):
    """Pre-registered thresholds. Never chosen after seeing numbers."""

    retention_drop_pp: dict[str, float] = Field(
        default_factory=lambda: {"fail": 1.0, "warn": 0.25}
    )
    require_sign_stability_for_fail: bool = True
    max_new_sole_reason_share: dict[str, float] = Field(
        default_factory=lambda: {"warn": 0.15}
    )

    @classmethod
    def load(cls, path: str | Path) -> Gates:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        payload.pop("$comment", None)
        payload.pop("description", None)
        return cls.model_validate(payload)


class FlipRow(BaseModel):
    patient_id: str
    direction: str
    diverged_at_event: int | None = None
    diverged_at_day: int | None = None
    baseline_exit_reason: str | None = None
    variant_exit_reason: str | None = None


class AttributionDelta(BaseModel):
    criterion: str
    kind: str
    baseline_share: float
    candidate_share: float
    baseline_sole_reason: int
    candidate_sole_reason: int

    @property
    def share_delta(self) -> float:
        return round(self.candidate_share - self.baseline_share, 6)

    @property
    def sole_reason_delta(self) -> int:
        return self.candidate_sole_reason - self.baseline_sole_reason

    @property
    def is_new(self) -> bool:
        return self.baseline_share == 0.0 and self.candidate_share > 0.0


class SignStability(BaseModel):
    seeds: list[int] = Field(default_factory=list)
    net_flips: list[int] = Field(default_factory=list)
    stable: bool = False

    def describe(self) -> str:
        if self.stable:
            return f"sign-stable across seeds {self.seeds} ({self.net_flips})"
        return (
            f"NOT sign-stable across seeds {self.seeds} ({self.net_flips}) — "
            "below the resolution of the paired design"
        )


class Verdict(BaseModel):
    verdict_schema_version: int = VERDICT_SCHEMA_VERSION
    outcome: Outcome
    reason: str

    scenario_name: str
    baseline_hash: str
    candidate_hash: str
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    config: ConfigStamp

    baseline_retention: float
    candidate_retention: float
    retention_delta_pp: float

    baseline_eligible: int
    candidate_eligible: int

    recovered: list[FlipRow] = Field(default_factory=list)
    lost: list[FlipRow] = Field(default_factory=list)
    unchanged: int = 0
    perturbed: int = 0

    attribution_deltas: list[AttributionDelta] = Field(default_factory=list)
    sign_stability: SignStability = Field(default_factory=SignStability)
    gates: Gates = Field(default_factory=Gates)
    ledger: dict = Field(default_factory=dict)

    @property
    def net_flips(self) -> int:
        return len(self.recovered) - len(self.lost)

    @property
    def failed(self) -> bool:
        return self.outcome == "FAIL"

    @property
    def exit_code(self) -> int:
        """WARN exits 0 with an annotation; only FAIL blocks."""
        return 1 if self.outcome == "FAIL" else 0


def _outcomes(logs) -> dict[str, str]:
    return {
        persona_id: ("dropped" if fold(log).stage == JourneyStage.DROPPED else "retained")
        for persona_id, log in logs.items()
    }


def _sign_stability(
    scenario: ScenarioFile, baseline_scenario: ScenarioFile, offset: int
) -> SignStability:
    """Re-run both sides under a second master seed and compare direction.

    The honesty guard. A design change whose net flip count does not keep its
    sign when the population is redrawn is not distinguishable from sampling
    variation, whatever the first number said.
    """
    seeds = [scenario.seed, scenario.seed + offset]
    nets: list[int] = []

    for seed in seeds:
        variant = scenario.model_copy(update={"seed": seed})
        control = baseline_scenario.model_copy(update={"seed": seed})
        nets.append(_net_flips(control, variant))

    signs = {(n > 0) - (n < 0) for n in nets}
    return SignStability(
        seeds=seeds, net_flips=nets, stable=len(signs) == 1 and 0 not in signs
    )


def _net_flips(control: ScenarioFile, variant: ScenarioFile) -> int:
    """Paired net flips between two scenarios at the same seed."""
    control_run = run_scenario(control)
    variant_run = run_scenario(variant)

    shared = sorted(set(control_run["logs"]) & set(variant_run["logs"]))
    if not shared:
        return 0

    diff = diff_runs(
        {pid: control_run["logs"][pid] for pid in shared},
        {pid: variant_run["logs"][pid] for pid in shared},
        control.duration_days,
    )
    return diff.net_flips


def evaluate(
    baseline: Baseline,
    candidate: ScenarioFile,
    baseline_scenario: ScenarioFile,
    gates: Gates | None = None,
    check_sign_stability: bool = True,
    second_seed_offset: int = DEFAULT_SECOND_SEED_OFFSET,
) -> Verdict:
    """Compare a candidate against its committed baseline and gate the result."""
    gates = gates or Gates()
    config = ConfigStamp.of(candidate)
    baseline.require_compatible(config)

    result = run_scenario(candidate)
    screening = result["screening"]
    stats = result["retention"]
    candidate_outcomes = _outcomes(result["logs"])

    # Pair on persona identity — the ids are globally unique, so a mismatch here
    # would mean genuinely different populations, which require_compatible has
    # already refused.
    shared = sorted(set(baseline.outcomes) & set(candidate_outcomes))
    recovered: list[FlipRow] = []
    lost: list[FlipRow] = []

    exit_reasons = {
        persona_id: next(
            (
                str(event.payload.get("reason"))
                for event in log
                if event.type.value == "dropped_out"
            ),
            None,
        )
        for persona_id, log in result["logs"].items()
    }

    for persona_id in shared:
        before, after = baseline.outcomes[persona_id], candidate_outcomes[persona_id]
        if before == after:
            continue
        row = FlipRow(
            patient_id=persona_id,
            direction=f"{before} -> {after}",
            variant_exit_reason=exit_reasons.get(persona_id),
        )
        (recovered if after == "retained" else lost).append(row)

    # Personas the candidate screened out entirely count as lost coverage, but
    # they are not flips — they never entered the paired comparison.
    baseline_retention = baseline.retention_rate
    candidate_retention = stats.get("retention_rate", 0.0)
    delta_pp = round((candidate_retention - baseline_retention) * 100, 4)

    stability = (
        _sign_stability(candidate, baseline_scenario, second_seed_offset)
        if check_sign_stability
        else SignStability()
    )

    outcome, reason = _gate(delta_pp, stability, gates)

    return Verdict(
        outcome=outcome, reason=reason,
        scenario_name=candidate.name,
        baseline_hash=baseline.scenario_hash,
        candidate_hash=candidate.scenario_hash(),
        config=config,
        baseline_retention=baseline_retention,
        candidate_retention=candidate_retention,
        retention_delta_pp=delta_pp,
        baseline_eligible=baseline.eligible,
        candidate_eligible=screening.n_eligible,
        recovered=recovered, lost=lost,
        unchanged=len(shared) - len(recovered) - len(lost),
        attribution_deltas=_attribution_deltas(baseline, screening),
        sign_stability=stability,
        gates=gates,
        ledger=baseline.ledger,
    )


def _attribution_deltas(baseline: Baseline, screening) -> list[AttributionDelta]:
    candidate = attribute_eligibility(screening)
    before = {row["criterion"]: row for row in baseline.attribution}
    after = {rule.criterion: rule for rule in candidate.rules}

    deltas = []
    for criterion in sorted(set(before) | set(after)):
        old, new = before.get(criterion), after.get(criterion)
        deltas.append(AttributionDelta(
            criterion=criterion,
            kind=(new.kind if new else old["kind"]),
            baseline_share=float(old["shapley_share"]) if old else 0.0,
            candidate_share=float(new.shapley_share) if new else 0.0,
            baseline_sole_reason=int(old["sole_reason"]) if old else 0,
            candidate_sole_reason=int(new.sole_reason) if new else 0,
        ))
    deltas.sort(key=lambda d: -abs(d.share_delta))
    return deltas


def _gate(delta_pp: float, stability: SignStability, gates: Gates) -> tuple[Outcome, str]:
    """Apply the pre-registered thresholds.

    The rule worth stating plainly: a drop big enough to fail is downgraded to
    WARN when it is not sign-stable. Failing a build on a delta the method cannot
    distinguish from noise would make the gate untrustworthy in exactly the way
    the paired design was built to avoid.
    """
    drop_pp = -delta_pp  # positive means retention got worse
    fail_at = gates.retention_drop_pp.get("fail", 1.0)
    warn_at = gates.retention_drop_pp.get("warn", 0.25)

    if drop_pp >= fail_at:
        if gates.require_sign_stability_for_fail and not stability.stable:
            return "WARN", (
                f"retention dropped {drop_pp:.2f}pp (fail threshold {fail_at}pp), "
                f"but the direction is not stable across seeds "
                f"{stability.net_flips} — reported as a warning rather than a "
                "failure, because the paired design cannot distinguish it from noise"
            )
        return "FAIL", (
            f"retention regression {drop_pp:.2f}pp vs baseline "
            f"(fail threshold {fail_at}pp), {stability.describe()}"
        )

    if drop_pp >= warn_at:
        return "WARN", (
            f"retention dropped {drop_pp:.2f}pp (warn threshold {warn_at}pp, "
            f"fail {fail_at}pp)"
        )

    if delta_pp > 0:
        return "PASS", f"retention improved {delta_pp:.2f}pp vs baseline"
    return "PASS", f"retention within tolerance ({delta_pp:+.2f}pp vs baseline)"


def write_verdict(verdict: Verdict, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(verdict.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path
