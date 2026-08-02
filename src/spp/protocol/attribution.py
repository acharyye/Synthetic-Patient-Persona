"""Exact attribution. No permutation sampling anywhere in this module.

**Eligibility is a veto game.** A persona is excluded iff at least one rule it
fails is active. For a given persona, rules it *passes* are null players — adding
them to any coalition changes nothing, so their Shapley value is 0. The rules it
*fails* are symmetric with each other: any coalition containing at least one of
them excludes the persona, and none excludes it alone-versus-together
differently. Symmetry plus efficiency gives each failing rule exactly `1/|F|`,
where `F` is that persona's failing-rule set.

So the cohort-level Shapley value of a rule is just the sum of `1/|F|` over the
personas it fails. One pass, exact. The existing `sole_reason` metric is the
`|F| = 1` special case of the same quantity.

Sampling Shapley here would be building machinery to approximate a number
computable in a list comprehension.

**Dropout attribution is also exact**, for the same kind of reason: the hazard
logit is *linear* in its inputs, so the contribution of each term is precisely
`weight_i x value_i`. If the hazard ever goes nonlinear (interactions, saturation),
this stops being exact and the honest move is to say so loudly rather than
quietly switch to sampling.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from ..assumptions import DROPOUT_HAZARD
from ..foundation.events import BurdenVector, EventLog, EventType, PersonaState
from ..schemas import PatientDNA
from .eligibility import ScreeningResult


class RuleAttribution(BaseModel):
    """Exact Shapley value of one criterion in the exclusion veto game."""

    criterion: str
    kind: str
    # Sum over personas of 1/|failing set|, in "personas' worth of exclusion".
    # Stored at FULL precision: efficiency (values summing to the number
    # excluded) is the property that makes `shapley_share` a real share, and
    # rounding here would break it — 1/3 three times is 0.9999, not 1. Round at
    # the presentation layer instead.
    shapley: float
    shapley_share: float = Field(description="fraction of all attributed exclusion")
    screened_out: int
    sole_reason: int

    @property
    def shared_blame(self) -> int:
        """Personas this rule excluded but did not exclude alone."""
        return self.screened_out - self.sole_reason


class EligibilityAttribution(BaseModel):
    n_screened: int
    n_excluded: int
    rules: list[RuleAttribution] = Field(default_factory=list)

    def headline(self) -> str:
        if not self.rules:
            return "no criteria applied"
        top = self.rules[0]
        return (
            f"{top.criterion!r} is responsible for {top.shapley_share:.0%} of total "
            f"attrition ({top.shapley:.1f} of {self.n_excluded} exclusions)"
        )


def attribute_eligibility(result: ScreeningResult) -> EligibilityAttribution:
    """Exact Shapley attribution over a completed screening.

    Values sum to the number of excluded personas (efficiency), which is the
    property that makes "rule 7 is responsible for 34% of attrition" a real
    share rather than a heuristic.
    """
    shapley: dict[str, float] = {}
    kinds: dict[str, str] = {}
    screened_out: dict[str, int] = {}
    sole: dict[str, int] = {}

    n_excluded = 0
    for verdict in result.verdicts:
        failing = [*verdict.failed_inclusion, *verdict.matched_exclusion]
        if not failing:
            continue
        n_excluded += 1
        share = 1.0 / len(failing)
        for criterion in failing:
            shapley[criterion] = shapley.get(criterion, 0.0) + share
            screened_out[criterion] = screened_out.get(criterion, 0) + 1
            if len(failing) == 1:
                sole[criterion] = sole.get(criterion, 0) + 1

    for impact in result.criteria_impact:
        kinds[impact.criterion] = impact.kind
        shapley.setdefault(impact.criterion, 0.0)
        screened_out.setdefault(impact.criterion, 0)

    total = sum(shapley.values())
    rules = [
        RuleAttribution(
            criterion=criterion,
            kind=kinds.get(criterion, "inclusion"),
            shapley=value,
            shapley_share=(value / total) if total else 0.0,
            screened_out=screened_out.get(criterion, 0),
            sole_reason=sole.get(criterion, 0),
        )
        for criterion, value in shapley.items()
    ]
    rules.sort(key=lambda rule: (-rule.shapley, rule.criterion))

    return EligibilityAttribution(
        n_screened=result.n_screened, n_excluded=n_excluded, rules=rules
    )


class HazardTerm(BaseModel):
    name: str
    weight: float
    value: float
    contribution: float

    @property
    def describe(self) -> str:
        return f"{self.name}: {self.weight:+.3f} x {self.value:.4f} = {self.contribution:+.4f}"


class DropoutAttribution(BaseModel):
    """Exact decomposition of one persona's dropout logit."""

    patient_id: str
    day: int
    logit: float
    hazard: float
    intercept: float
    terms: list[HazardTerm] = Field(default_factory=list)

    @property
    def dominant(self) -> HazardTerm | None:
        positive = [t for t in self.terms if t.contribution > 0]
        return max(positive, key=lambda t: t.contribution) if positive else None

    def shares(self) -> dict[str, float]:
        """Share of the positive (risk-increasing) contribution, per term."""
        total = sum(t.contribution for t in self.terms if t.contribution > 0)
        if total <= 0:
            return {}
        return {
            t.name: round(t.contribution / total, 4)
            for t in self.terms
            if t.contribution > 0
        }


def attribute_dropout(
    dna: PatientDNA,
    state_at_exit: PersonaState,
    increment: BurdenVector,
    consecutive_missed: int = 0,
) -> DropoutAttribution:
    """Decompose the dropout logit exactly. Linear model, so terms are exact."""
    weights = DROPOUT_HAZARD.params
    inputs = [
        ("accumulated burden", weights["cumulative_burden_weight"], state_at_exit.burden.total),
        ("this visit", weights["burden_increment_weight"], increment.total),
        ("personal barriers", weights["barrier_weight"], dna.barrier_load),
        ("adherence deficit", weights["adherence_deficit_weight"], 1.0 - dna.adherence_baseline),
        ("missed visits", weights["consecutive_missed_weight"], float(consecutive_missed)),
    ]
    terms = [
        HazardTerm(name=name, weight=weight, value=value,
                   contribution=round(weight * value, 6))
        for name, weight, value in inputs
    ]
    logit = weights["intercept"] + sum(term.contribution for term in terms)

    from ..simulation.hazard import _sigmoid

    return DropoutAttribution(
        patient_id=dna.patient_id,
        day=state_at_exit.t,
        logit=round(logit, 6),
        hazard=round(min(_sigmoid(logit), weights["max_per_visit"]), 6),
        intercept=weights["intercept"],
        terms=terms,
    )


def attribute_cohort_dropouts(
    cohort: list[PatientDNA], logs: dict[str, EventLog]
) -> dict[str, float]:
    """Population share of dropout risk by cause, read off the logs.

    Uses the reason recorded at the dropout event — already an exact
    decomposition, computed at the moment the decision was made.
    """
    reasons: dict[str, float] = {}
    total = 0
    for log in logs.values():
        for event in log.of_type(EventType.DROPPED_OUT):
            reason = str(event.payload.get("reason", "unknown"))
            reasons[reason] = reasons.get(reason, 0.0) + 1
            total += 1
    if not total:
        return {}
    return {
        reason: round(count / total, 4)
        for reason, count in sorted(reasons.items(), key=lambda kv: -kv[1])
    }
