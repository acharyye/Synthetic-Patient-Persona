"""Sample N plausible personas across a condition's real subpopulation.

Draws from the priors in `epidemiology.py` rather than uniform toy ranges, so a
generated panel has the age skew, sex ratio, stage mix, comorbidity load and
adherence spread you would expect to argue about in a protocol review.

Three modelling choices worth knowing about, because they are assumptions rather
than measurements:

  1. **Traits are correlated, not independent.** A Gaussian copula
     (`correlation.py`) couples age, comorbidity load, literacy, mobility,
     caregiver support, transport and financial security, so the cohort does not
     contain 92-year-old marathon runners with no comorbidities. The correlation
     structure lives in the ledger; the marginals stay with the prior packs.
  2. **Adherence is derived, not sampled.** It starts from the condition's base
     rate and is pushed around by literacy, transport, caregiver support and pill
     burden. That coupling is what makes /protocol/stress-test surface the
     patients a real site would struggle to retain.
  3. **Goals, constraints and barriers are derived deterministically** from the
     finished profile (`traits.py`), so two identical profiles always produce
     identical barriers.

Seeding goes through the named hierarchy in `foundation/rng.py`: each persona
draws from its own scope, so persona #7 is identical whether you generate 10
personas or 10,000 — and can be re-simulated alone.
"""
from __future__ import annotations

from datetime import date, timedelta

import numpy as np

from ..assumptions import (
    ADHERENCE_ACCESS,
    ADHERENCE_BOUNDS,
    ADHERENCE_LITERACY,
    ADHERENCE_PILL_BURDEN,
    COMORBIDITY_AGE_SLOPE,
    SEX_DISTRIBUTION,
    TRAIT_CORRELATIONS,
)
from ..foundation.rng import SeedScope, cohort_scope, persona_scope
from ..schemas import JourneyMilestone, Medication, PatientDNA
from .correlation import (
    CopulaSampler,
    build_correlation_matrix,
    uniform_to_choice,
    uniform_to_normal,
)
from .epidemiology import HEALTH_LITERACY_WEIGHTS, BiomarkerSpec, ConditionEpi, for_condition
from .traits import derive_persona_traits

# Small share of personas recorded outside the female/male binary, so downstream
# consumers exercise the schema's third option rather than assuming two.
OTHER_SEX_FRACTION = SEX_DISTRIBUTION.params["fraction"]

# Social-determinant option sets, ordered worst-to-best so the copula axis that
# selects them correlates in the direction its name implies. Do not reorder
# without revisiting the correlation signs in `cohort.trait_correlations`.
_TRANSPORT = {"none": 0.10, "public transport": 0.30, "lift from family": 0.15, "own car": 0.45}
_CAREGIVER = {"none": 0.35, "paid carer": 0.05, "adult child": 0.20, "spouse": 0.40}
_EMPLOYMENT = {
    "unable to work": 0.10, "shift-work": 0.13, "part-time": 0.12,
    "full-time": 0.25, "retired": 0.40,
}
_HOUSING = {"rural": 0.18, "suburban": 0.32, "urban": 0.50}


def _copula() -> CopulaSampler:
    """Build the sampler from the ledger's pairwise correlations.

    Gated, not repaired: an inconsistent correlation spec raises at import time
    with a diagnostic rather than being silently projected. Projection would move
    entries and break the invariant that the ledger number *is* the latent
    correlation sampled — see `correlation.build_correlation_matrix`.
    """
    pairs = {
        tuple(key.split("|")): value  # type: ignore[misc]
        for key, value in TRAIT_CORRELATIONS.params.items()
    }
    matrix, corrections = build_correlation_matrix(pairs, allow_projection=False)
    assert not corrections, "projection is disabled; this should be unreachable"
    return CopulaSampler(matrix)


_SAMPLER = _copula()


def _bounded_normal(
    gen: np.random.Generator, mean: float, sd: float, lo: float, hi: float, decimals: int = 1
) -> float:
    """Independent bounded normal draw, for values the copula doesn't couple.

    Clipped AFTER rounding as well as before: rounding can push a value back out
    of its support (CRP with lo=0.2 and decimals=0 rounds 0.3 to 0.0), which
    silently violates the bound the prior pack declares.
    """
    value = round(float(np.clip(gen.normal(mean, sd), lo, hi)), decimals)
    return float(np.clip(value, lo, hi))


def _sample_sex(gen: np.random.Generator, female_fraction: float) -> str:
    if gen.random() < OTHER_SEX_FRACTION:
        return "other"
    return "female" if gen.random() < female_fraction else "male"


def _sample_biomarkers(
    gen: np.random.Generator, specs: list[BiomarkerSpec], stage_index: int
) -> dict[str, float]:
    out: dict[str, float] = {}
    for spec in specs:
        mean = spec.mean
        if spec.stage_shift and stage_index < len(spec.stage_shift):
            mean *= spec.stage_shift[stage_index]
        out[spec.name] = _bounded_normal(gen, mean, spec.sd, spec.lo, spec.hi, spec.decimals)
    return out


def _sample_comorbidities(
    gen: np.random.Generator,
    epi: ConditionEpi,
    condition: str,
    age: int,
    comorbidity_load: float,
) -> list[str]:
    """Prevalence scaled by age and by this persona's latent comorbidity load.

    The load term is what carries the correlation: a persona drawn sick on the
    latent axis is more likely to clear *every* comorbidity threshold, which is
    how comorbidities end up co-occurring instead of scattering independently.
    """
    slope = COMORBIDITY_AGE_SLOPE.params
    age_factor = slope["intercept"] + slope["slope"] * max(0, age - slope["pivot_age"])
    # Map the [0,1] latent load onto a multiplier around 1.
    load_factor = 0.55 + 0.9 * comorbidity_load

    primary = condition.casefold()
    out: list[str] = []
    for name, prevalence in epi.comorbidity_prevalence.items():
        if name.casefold() == primary:
            continue
        threshold = min(slope["cap"], prevalence * age_factor * load_factor)
        if gen.random() < threshold:
            out.append(name)
    return out


def _sample_sdoh(traits: dict[str, float], age: int) -> dict[str, str]:
    """Social determinants read straight off the correlated trait vector.

    No extra RNG: these *are* the copula's job. Doing it this way is what makes
    deprivation cluster — a persona low on financial security tends to be low on
    transport access and support too, because those axes are correlated.
    """
    employment_u = traits["age"]  # older -> further along the ordered list -> retired
    if age >= 75:
        employment = "retired"
    else:
        employment = uniform_to_choice(employment_u, _EMPLOYMENT)

    return {
        "transport": uniform_to_choice(traits["transport_access"], _TRANSPORT),
        "caregiver": uniform_to_choice(traits["caregiver_support"], _CAREGIVER),
        "employment": employment,
        "residence": uniform_to_choice(traits["financial_security"], _HOUSING),
    }


def _derive_adherence(
    gen: np.random.Generator,
    epi: ConditionEpi,
    literacy: str,
    sdoh: dict[str, str],
    n_meds: int,
    age: int,
) -> float:
    """Baseline adherence as a function of the barriers this patient actually has.

    Every coefficient is read from the assumption ledger rather than written
    here, so `LEDGER.perturbed(...)` can drive sensitivity analysis and any
    exported result can carry the exact numbers that produced it.
    """
    access = ADHERENCE_ACCESS.params
    pills = ADHERENCE_PILL_BURDEN.params
    bounds = ADHERENCE_BOUNDS.params

    score = epi.base_adherence
    score += ADHERENCE_LITERACY.params[literacy]

    if sdoh.get("transport") == "none":
        score += access["transport_none"]
    elif sdoh.get("transport") == "public transport":
        score += access["transport_public"]

    if sdoh.get("caregiver") == "none":
        score += access["caregiver_none"]
    if sdoh.get("employment") == "shift-work":
        score += access["employment_shift_work"]
    if sdoh.get("residence") == "rural":
        score += access["residence_rural"]

    score += pills["per_extra_medication"] * max(0, n_meds - pills["free_medications"])

    if age >= access["age_penalty_from"]:
        score += access["age_penalty"]

    score += gen.normal(0, pills["noise_sd"])
    return round(float(np.clip(score, bounds["min"], bounds["max"])), 2)


def _sample_journey(
    gen: np.random.Generator,
    epi: ConditionEpi,
    stage_index: int,
    n_meds: int,
    as_of: date,
) -> list[JourneyMilestone]:
    """Onset -> diagnosis -> treatment -> follow-up, with later stages implying a
    longer history. Gives the persona engine something concrete to narrate.
    """
    years_since_dx = max(0.2, float(gen.normal(1.5 + 2.2 * stage_index, 1.2)))
    dx = as_of - timedelta(days=int(365 * years_since_dx))
    delay_days = 30 * int(gen.integers(epi.dx_delay_months[0], epi.dx_delay_months[1] + 1))
    onset = dx - timedelta(days=delay_days)
    first_contact = dx - timedelta(days=max(7, int(delay_days * gen.uniform(0.2, 0.7))))

    first_drug = epi.medication_ladder[0][0] if epi.medication_ladder else None
    journey = [
        JourneyMilestone(
            stage="symptom_onset",
            when=onset,
            note=f"First noticed symptoms roughly {delay_days // 30} months before diagnosis.",
        ),
        JourneyMilestone(stage="first_contact", when=first_contact,
                         note="Raised it with primary care."),
        JourneyMilestone(stage="diagnosis", when=dx, note=f"Diagnosed with {epi.label}."),
        JourneyMilestone(
            stage="treatment_start",
            when=dx + timedelta(days=int(gen.integers(3, 61))),
            note=f"Started {first_drug}." if first_drug else "Treatment started.",
        ),
    ]

    if n_meds > 1 and gen.random() < 0.25 + 0.12 * stage_index:
        journey.append(
            JourneyMilestone(
                stage="adverse_event",
                when=dx + timedelta(
                    days=int(gen.integers(60, max(91, int(365 * years_since_dx))))
                ),
                note="Side effects prompted a regimen change.",
            )
        )

    journey.append(
        JourneyMilestone(
            stage="follow_up",
            when=as_of - timedelta(days=int(gen.integers(14, 181))),
            note="Most recent routine review.",
        )
    )
    return sorted(journey, key=lambda m: m.when or as_of)


def make_patient_id(condition: str, cohort_seed: int, index: int) -> str:
    """Globally unique persona id.

    `synthetic-0000` was unique only WITHIN a cohort, so the same id existed in
    every condition. Any dict, file, report or route keyed on it was a latent
    collision — the compliance eval hit exactly that, silently scoring one
    condition's personas against another's expected facts. Encoding
    (condition, cohort_seed, index) makes every downstream consumer correct by
    construction rather than each needing its own compound key, and makes
    /persona/{id} unambiguous once there are routes.
    """
    slug = "".join(
        char if char.isalnum() else "-" for char in condition.strip().casefold()
    ).strip("-")
    while "--" in slug:
        slug = slug.replace("--", "-")
    return f"{slug or 'condition'}-s{cohort_seed}-{index:04d}"


def generate_patient(
    condition: str,
    index: int,
    scope: SeedScope,
    epi: ConditionEpi | None = None,
    as_of: date | None = None,
    cohort_seed: int = 42,
) -> PatientDNA:
    """Sample a single persona from its own seed scope."""
    epi = epi or for_condition(condition)
    as_of = as_of or date.today()
    gen = scope.generator()

    traits = _SAMPLER.draw(gen)

    age = int(uniform_to_normal(
        traits["age"], epi.age_mean, epi.age_sd, epi.age_min, epi.age_max
    ))
    literacy = uniform_to_choice(traits["health_literacy"], HEALTH_LITERACY_WEIGHTS)
    sdoh = _sample_sdoh(traits, age)

    sex = _sample_sex(gen, epi.female_fraction)
    stage = uniform_to_choice(traits["comorbidity_load"], epi.stage_weights)
    stage_index = epi.stages.index(stage)

    ladder = epi.medication_ladder
    if ladder:
        jitter = int(gen.choice([-1, 0, 0, 1]))
        n_meds = min(len(ladder), max(1, stage_index + 1 + jitter))
    else:
        n_meds = 0

    adherence = _derive_adherence(gen, epi, literacy, sdoh, n_meds, age)
    journey = _sample_journey(gen, epi, stage_index, n_meds, as_of)
    treatment_start = next((m.when for m in journey if m.stage == "treatment_start"), None)

    medications = [
        Medication(
            name=name,
            dose=dose,
            started=treatment_start + timedelta(days=180 * i) if treatment_start else None,
            adherence=round(float(np.clip(adherence + gen.normal(0, 0.06), 0.0, 1.0)), 2),
        )
        for i, (name, dose) in enumerate(ladder[:n_meds])
    ]

    dna = PatientDNA(
        patient_id=make_patient_id(epi.label, cohort_seed, index),
        age=age,
        sex=sex,
        condition=epi.label,
        stage=stage,
        biomarkers=_sample_biomarkers(gen, epi.biomarkers, stage_index),
        comorbidities=_sample_comorbidities(
            gen, epi, epi.label, age, traits["comorbidity_load"]
        ),
        medications=medications,
        adherence_baseline=adherence,
        health_literacy=literacy,
        social_determinants=sdoh,
        traits={k: round(v, 4) for k, v in traits.items()},
        journey=journey,
    )
    return derive_persona_traits(dna)


def generate_cohort(
    condition: str,
    n: int = 10,
    seed: int | None = 42,
    as_of: date | None = None,
) -> list[PatientDNA]:
    """Sample `n` personas for `condition`, reproducibly for a given seed.

    Each persona has its own named seed scope, so growing `n` extends the cohort
    rather than redrawing it, and any one persona can be reproduced alone.
    """
    if n < 0:
        raise ValueError("n must be non-negative")
    epi = for_condition(condition)
    as_of = as_of or date.today()
    resolved_seed = 42 if seed is None else seed
    anchor = cohort_scope(resolved_seed, condition)

    return [
        generate_patient(
            condition, i, persona_scope(anchor, i), epi=epi, as_of=as_of,
            cohort_seed=resolved_seed,
        )
        for i in range(n)
    ]


def cohort_summary(cohort: list[PatientDNA]) -> dict:
    """Descriptive shape of a panel — what you'd sanity-check before using it."""
    if not cohort:
        return {"n": 0}

    n = len(cohort)
    ages = [p.age for p in cohort]
    adherence = [p.adherence_baseline for p in cohort]

    def _tally(values: list[str]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for v in values:
            counts[v] = counts.get(v, 0) + 1
        return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0])))

    comorbidities = [c for p in cohort for c in p.comorbidities]
    barriers = [b.name for p in cohort for b in p.barriers]

    return {
        "n": n,
        "age_mean": round(sum(ages) / n, 1),
        "age_range": [min(ages), max(ages)],
        "sex": _tally([p.sex for p in cohort]),
        "stage": _tally([p.stage for p in cohort if p.stage]),
        "health_literacy": _tally([p.health_literacy for p in cohort]),
        "adherence_mean": round(sum(adherence) / n, 2),
        "adherence_below_50pct": sum(1 for a in adherence if a < 0.5),
        "comorbidity_prevalence": {
            name: round(count / n, 2) for name, count in _tally(comorbidities).items()
        },
        "mean_comorbidity_count": round(len(comorbidities) / n, 2),
        "barrier_prevalence": {
            name: round(count / n, 2) for name, count in _tally(barriers).items()
        },
        "mean_barrier_load": round(sum(p.barrier_load for p in cohort) / n, 3),
    }
