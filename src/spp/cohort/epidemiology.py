"""Condition-level priors used to sample statistically plausible cohorts.

WHAT THESE NUMBERS ARE: order-of-magnitude priors compiled from published
prevalence summaries (CDC/NHANES-style surveillance, GOLD/AHA/ACR registry
reports). They are good enough to make a synthetic panel *feel* right for
design and stakeholder-simulation work — an age skew that matches the disease,
comorbidity load that isn't invented, a stage mix that isn't uniform.

WHAT THEY ARE NOT: a fitted epidemiological model. Do not quote a number that
came out of this module as a finding. Before any quantitative claim, replace
these with values derived from Synthea output or a real registry
(see `ingest/synthea_loader.py`, build-order item 1).

Known simplification: comorbidities are sampled as independent Bernoulli draws,
so the correlation structure between them (CKD given diabetes given
hypertension) is lost. That is the main thing Synthea-derived priors would fix.
"""
from __future__ import annotations

from pydantic import BaseModel, Field


class BiomarkerSpec(BaseModel):
    """A continuous lab value sampled from a bounded normal."""

    name: str
    mean: float
    sd: float
    lo: float
    hi: float
    decimals: int = 1
    # Multiplied into the sampled value as stage worsens, in stage order.
    stage_shift: list[float] = Field(default_factory=list)


class ConditionEpi(BaseModel):
    """Priors for one condition. `stage_weights` defines the stage ladder order."""

    label: str
    aliases: list[str] = Field(default_factory=list)
    source_note: str

    age_mean: float
    age_sd: float
    age_min: int
    age_max: int
    female_fraction: float

    stage_weights: dict[str, float]
    comorbidity_prevalence: dict[str, float]
    biomarkers: list[BiomarkerSpec] = Field(default_factory=list)

    # Ordered therapy ladder; later stages sit further down it.
    medication_ladder: list[tuple[str, str]] = Field(default_factory=list)

    # Mean baseline adherence before behavioural/SDOH modifiers are applied.
    base_adherence: float = 0.75
    # Plausible range, in months, between symptom onset and diagnosis.
    dx_delay_months: tuple[int, int] = (2, 18)

    @property
    def stages(self) -> list[str]:
        return list(self.stage_weights)

    @classmethod
    def from_pack(cls, pack) -> ConditionEpi:
        """Build the in-memory shape from a prior pack.

        The pack is the source of truth; this is just the projection the sampler
        wants. Keeping ConditionEpi as the interface means the generator did not
        have to change when priors moved from code to data.
        """
        sex = pack.marginal("sex").params
        age = pack.marginal("age")
        stage = pack.marginal("stage")
        ladder = pack.marginal("medication_ladder").params["rungs"]
        delay = pack.marginal("dx_delay_months").params

        biomarkers = [
            BiomarkerSpec(
                name=spec.field.split(":", 1)[1],
                mean=spec.params["mean"],
                sd=spec.params["sd"],
                lo=spec.support[0],
                hi=spec.support[1],
                decimals=spec.params.get("decimals", 1),
                stage_shift=spec.params.get("stage_shift", []),
            )
            for spec in pack.marginals
            if spec.field.startswith("biomarker:")
        ]

        return cls(
            label=pack.condition,
            aliases=list(pack.aliases),
            source_note=pack.description,
            age_mean=age.params["mean"],
            age_sd=age.params["sd"],
            age_min=int(age.support[0]),
            age_max=int(age.support[1]),
            female_fraction=float(sex["female"]),
            stage_weights={k: float(v) for k, v in stage.params.items()},
            comorbidity_prevalence={
                k: float(v) for k, v in pack.marginal("comorbidities").params.items()
            },
            biomarkers=biomarkers,
            medication_ladder=[tuple(rung) for rung in ladder],
            base_adherence=pack.marginal("base_adherence").params["value"],
            dx_delay_months=(int(delay["lo"]), int(delay["hi"])),
        )


# The per-condition table that used to live here now lives in
# data/prior_packs/*.json. It was migrated by scripts/export_prior_packs.py
# (retained for the record) and removed from code deliberately: two copies of
# the same priors drift, and the packs are the source of truth. Edit the JSON.
#
# GENERIC_EPI below stays in code as the fallback for a condition with no pack.


GENERIC_EPI = ConditionEpi(
    label="generic chronic condition",
    source_note="Fallback priors for a condition with no prior pack. "
                "Broad adult chronic-disease shape; add a real entry before relying on it.",
    age_mean=60,
    age_sd=15,
    age_min=18,
    age_max=95,
    female_fraction=0.51,
    stage_weights={"early": 0.35, "moderate": 0.40, "advanced": 0.25},
    comorbidity_prevalence={
        "hypertension": 0.45,
        "obesity": 0.30,
        "type 2 diabetes": 0.20,
        "depression": 0.18,
        "CKD": 0.12,
        "COPD": 0.10,
    },
    medication_ladder=[
        ("first-line therapy", "standard dose"),
        ("second-line therapy", "standard dose"),
        ("third-line therapy", "standard dose"),
    ],
)


# Health-literacy mix, roughly the adult population shape rather than anything
# condition-specific. Drives adherence and interview register downstream.
HEALTH_LITERACY_WEIGHTS: dict[str, float] = {"low": 0.30, "medium": 0.52, "high": 0.18}


def for_condition(condition: str) -> ConditionEpi:
    """Resolve a free-text condition to its priors.

    **Prior packs are the source of truth.** This reads `data/prior_packs/*.json`
    and falls back to GENERIC_EPI only when no pack matches. The in-code
    CONDITION_EPI table that used to live here was migrated into packs and
    removed — keeping both would have been two copies of the same numbers, which
    is exactly the drift packs exist to prevent.

    Matching is deliberately forgiving (case-insensitive, alias-aware, substring)
    because `condition` arrives from an API caller, not a controlled vocabulary.
    Swap this for KG node resolution once the graph is loaded.
    """
    from .packs import pack_for

    key = (condition or "").strip().casefold()
    if not key:
        return GENERIC_EPI

    pack = pack_for(key)
    return ConditionEpi.from_pack(pack) if pack is not None else GENERIC_EPI
