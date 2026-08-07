"""The baseline: a repo's pinned expectation for a protocol design.

`ci/baseline.json` is committed, the way a golden file is. It records what the
current design does — retention, per-persona outcomes, survival curve,
attribution — plus every stamp needed to reproduce it.

Two disciplines inherited from elsewhere in the repo, both load-bearing:

**Compatibility is refused loudly, never worked around.** A baseline generated
from a different pack version, seed, cohort size or engine version is not a
baseline for the candidate — it is a different population, and comparing against
it would produce a confident number about nothing. Same reasoning as
`EventLog.require_compatible()`.

**Regeneration is explicit and its diff is printed.** The golden-file reading
rule applies unchanged: a baseline diff you intended is a redesign; a baseline
diff you did not expect is something to investigate before committing. A baseline
that silently refreshed itself would gate on whatever the code happens to do
today, which is not a gate at all.

Per-persona outcomes are keyed by the globally unique persona id, so an outcome
map can never be silently matched against a different condition's cohort.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from pydantic import BaseModel, Field

from ..cohort import generate_cohort
from ..cohort.packs import pack_for
from ..foundation.ledger import LEDGER, LEDGER_SCHEMA_VERSION
from ..protocol import attribute_eligibility, screen
from ..simulation import (
    VisitSchedule,
    retention_summary,
    schedule_from_protocol,
    simulate_cohort,
    survival_curve,
)
from ..simulation.schedule import ScheduledVisit
from .scenario_file import ENGINE_VERSION, ScenarioFile

BASELINE_SCHEMA_VERSION = 1


class IncompatibleBaseline(RuntimeError):
    """The baseline does not describe the same population as the candidate."""


class ConfigStamp(BaseModel):
    """Everything that must match for a comparison to mean anything.

    A verdict that cannot name its configuration is not evidence — so this is
    the object every artifact carries, and the object `require_compatible`
    compares field by field.
    """

    engine_version: int = ENGINE_VERSION
    baseline_schema_version: int = BASELINE_SCHEMA_VERSION
    ledger_schema_version: int = LEDGER_SCHEMA_VERSION
    condition: str
    pack_id: str
    pack_version: int
    cohort_size: int
    master_seed: int
    duration_days: int

    @classmethod
    def of(cls, scenario: ScenarioFile) -> ConfigStamp:
        pack = pack_for(scenario.condition)
        return cls(
            condition=scenario.condition,
            pack_id=pack.name if pack else f"generic:{scenario.condition}",
            pack_version=pack.schema_version if pack else 0,
            cohort_size=scenario.cohort_size,
            master_seed=scenario.seed,
            duration_days=scenario.duration_days,
        )

    def describe(self) -> str:
        return (
            f"{self.pack_id}@v{self.pack_version} seed={self.master_seed} "
            f"n={self.cohort_size} days={self.duration_days} "
            f"engine=v{self.engine_version}"
        )


class Baseline(BaseModel):
    """The committed expectation. Diff it like a golden file."""

    baseline_schema_version: int = BASELINE_SCHEMA_VERSION
    scenario_name: str
    scenario_hash: str
    # The scenario this baseline was generated FROM, stored in full.
    #
    # Without it, the sign-stability control has nothing to compare against and
    # the only available fallback is the candidate itself — which yields zero
    # flips at every seed, reports "not sign-stable", and downgrades every FAIL
    # to WARN. That is a gate that can never fail. Storing the scenario is what
    # makes the second-seed run a real control.
    scenario: dict = Field(default_factory=dict)
    generated_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    config: ConfigStamp

    screened: int
    eligible: int
    eligibility_rate: float
    retained: int
    retention_rate: float

    # persona_id -> "retained" | "dropped". Keyed by the globally unique id, so
    # an outcome map cannot be matched against a different condition's cohort.
    outcomes: dict[str, str] = Field(default_factory=dict)
    survival_curve: list[dict] = Field(default_factory=list)
    attribution: list[dict] = Field(default_factory=list)
    ledger: dict = Field(default_factory=dict)

    def require_compatible(self, candidate: ConfigStamp) -> Baseline:
        """Raise unless the candidate describes the same population."""
        mismatches = [
            f"{field}: baseline={getattr(self.config, field)!r} "
            f"candidate={getattr(candidate, field)!r}"
            for field in (
                "engine_version", "ledger_schema_version", "condition",
                "pack_id", "pack_version", "cohort_size", "master_seed",
                "duration_days",
            )
            if getattr(self.config, field) != getattr(candidate, field)
        ]
        if mismatches:
            raise IncompatibleBaseline(
                "baseline does not describe the same population as the candidate:\n  "
                + "\n  ".join(mismatches)
                + "\n\nA baseline from a different population is not a baseline. "
                "Regenerate it with `spp ci baseline <scenario>` and review the diff."
            )
        return self


def build_schedule(scenario: ScenarioFile) -> VisitSchedule:
    """The schedule a scenario implies.

    Explicit `visits` win when present; otherwise it is derived from `burden`.
    Either way visit_ids are stable identities, which is what makes the paired
    flip table signal rather than reshuffled randomness.
    """
    derived = schedule_from_protocol(scenario.burden, duration_days=scenario.duration_days)
    if not scenario.visits:
        return derived

    template = derived.visits[0].burden if derived.visits else None
    if template is None:
        raise ValueError("cannot build an explicit schedule without a burden template")

    return VisitSchedule(
        name=scenario.name,
        duration_days=scenario.duration_days,
        visits=[
            ScheduledVisit(
                visit_id=spec.visit_id, day=spec.day, label=spec.label,
                remote=spec.remote,
                burden=template.model_copy(
                    update={"travel": template.travel * (0.1 if spec.remote else 1.0)}
                ),
            )
            for spec in sorted(scenario.visits, key=lambda v: (v.day, v.visit_id))
        ],
    )


def run_scenario(scenario: ScenarioFile) -> dict:
    """Screen then simulate. Pure core — no LLM anywhere on this path."""
    cohort = generate_cohort(scenario.condition, scenario.cohort_size, seed=scenario.seed)
    screening = screen(cohort, scenario.inclusion, scenario.exclusion)

    eligible_ids = set(screening.eligible_ids)
    eligible = [p for p in cohort if p.patient_id in eligible_ids]

    schedule = build_schedule(scenario)
    logs = simulate_cohort(
        eligible, schedule, seed=scenario.seed, condition=scenario.condition,
        washout=scenario.burden.washout_required,
    )
    stats = retention_summary(logs)

    return {
        "cohort": cohort,
        "screening": screening,
        "attribution": attribute_eligibility(screening),
        "schedule": schedule,
        "logs": logs,
        "retention": stats,
        "curve": survival_curve(logs, schedule.duration_days),
    }


def build_baseline(scenario: ScenarioFile) -> Baseline:
    """Run the scenario and capture it as the pinned expectation."""
    result = run_scenario(scenario)
    screening = result["screening"]
    stats = result["retention"]

    from ..foundation.events import JourneyStage, fold

    outcomes = {
        persona_id: (
            "dropped" if fold(log).stage == JourneyStage.DROPPED else "retained"
        )
        for persona_id, log in result["logs"].items()
    }

    return Baseline(
        scenario_name=scenario.name,
        scenario_hash=scenario.scenario_hash(),
        scenario=scenario.model_dump(mode="json"),
        config=ConfigStamp.of(scenario),
        screened=screening.n_screened,
        eligible=screening.n_eligible,
        eligibility_rate=screening.eligibility_rate,
        retained=stats.get("retained", 0),
        retention_rate=stats.get("retention_rate", 0.0),
        outcomes=outcomes,
        survival_curve=result["curve"],
        attribution=[
            {
                "criterion": rule.criterion, "kind": rule.kind,
                "shapley": round(rule.shapley, 6),
                "shapley_share": round(rule.shapley_share, 6),
                "screened_out": rule.screened_out,
                "sole_reason": rule.sole_reason,
            }
            for rule in result["attribution"].rules
        ],
        ledger=LEDGER.snapshot(),
    )


def write_baseline(baseline: Baseline, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = baseline.model_dump(mode="json")
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def read_baseline(path: str | Path) -> Baseline:
    path = Path(path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise IncompatibleBaseline(f"could not read baseline {path}: {exc}") from None
    except json.JSONDecodeError as exc:
        raise IncompatibleBaseline(f"baseline {path.name} is not valid JSON: {exc}") from None

    version = payload.get("baseline_schema_version")
    if version != BASELINE_SCHEMA_VERSION:
        raise IncompatibleBaseline(
            f"baseline {path.name} is schema v{version}, this build reads "
            f"v{BASELINE_SCHEMA_VERSION}. Regenerate it."
        )
    return Baseline.model_validate(payload)


def diff_summary(old: Baseline | None, new: Baseline) -> str:
    """What regeneration changed. Printed so a surprise is visible immediately.

    The golden-file reading rule, applied to baselines: an expected diff is a
    redesign; an unexpected one is something to investigate before committing.
    """
    if old is None:
        return (
            f"new baseline for {new.scenario_name!r}\n"
            f"  config    {new.config.describe()}\n"
            f"  scenario  {new.scenario_hash[:12]}\n"
            f"  eligible  {new.eligible}/{new.screened} ({new.eligibility_rate:.1%})\n"
            f"  retained  {new.retained}/{new.eligible} ({new.retention_rate:.1%})"
        )

    flips = sum(
        1 for persona_id, outcome in new.outcomes.items()
        if old.outcomes.get(persona_id, outcome) != outcome
    )
    lines = [f"baseline diff for {new.scenario_name!r}"]
    if old.scenario_hash != new.scenario_hash:
        lines.append(f"  scenario  {old.scenario_hash[:12]} -> {new.scenario_hash[:12]}")
    else:
        lines.append(f"  scenario  {new.scenario_hash[:12]} (unchanged)")
    if old.config.describe() != new.config.describe():
        lines.append(f"  config    {old.config.describe()}")
        lines.append(f"         -> {new.config.describe()}")
    lines.append(
        f"  eligible  {old.eligible} -> {new.eligible} "
        f"({(new.eligibility_rate - old.eligibility_rate) * 100:+.2f}pp)"
    )
    lines.append(
        f"  retained  {old.retained} -> {new.retained} "
        f"({(new.retention_rate - old.retention_rate) * 100:+.2f}pp)"
    )
    lines.append(f"  personas whose outcome moved: {flips}")
    return "\n".join(lines)
