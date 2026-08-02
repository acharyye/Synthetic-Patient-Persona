from datetime import date

import pytest

from spp.cohort import cohort_summary, for_condition, generate_cohort
from spp.cohort.epidemiology import GENERIC_EPI

AS_OF = date(2026, 8, 1)


def test_seed_makes_cohorts_reproducible():
    a = generate_cohort("type 2 diabetes", 20, seed=7, as_of=AS_OF)
    b = generate_cohort("type 2 diabetes", 20, seed=7, as_of=AS_OF)
    c = generate_cohort("type 2 diabetes", 20, seed=8, as_of=AS_OF)

    assert [p.model_dump() for p in a] == [p.model_dump() for p in b]
    assert [p.model_dump() for p in a] != [p.model_dump() for p in c]


def test_condition_resolution_is_forgiving():
    assert for_condition("Type 2 Diabetes").label == "type 2 diabetes"
    assert for_condition("T2D").label == "type 2 diabetes"
    assert for_condition("chronic obstructive pulmonary disease").label == "COPD"
    assert for_condition("").label == GENERIC_EPI.label
    assert for_condition("a condition nobody has heard of").label == GENERIC_EPI.label


def test_ages_respect_the_condition_bounds():
    epi = for_condition("COPD")
    cohort = generate_cohort("COPD", 200, seed=1, as_of=AS_OF)
    assert all(epi.age_min <= p.age <= epi.age_max for p in cohort)


def test_stages_and_biomarkers_come_from_the_condition_priors():
    epi = for_condition("heart failure")
    cohort = generate_cohort("heart failure", 50, seed=3, as_of=AS_OF)

    assert {p.stage for p in cohort} <= set(epi.stages)
    expected = {b.name for b in epi.biomarkers}
    assert all(set(p.biomarkers) == expected for p in cohort)
    for spec in epi.biomarkers:
        assert all(spec.lo <= p.biomarkers[spec.name] <= spec.hi for p in cohort)


def test_sex_ratio_tracks_the_prior():
    """Breast cancer is ~99% female; the sampler must not hand back a coin flip."""
    cohort = generate_cohort("breast cancer", 300, seed=5, as_of=AS_OF)
    female = sum(1 for p in cohort if p.sex == "female") / len(cohort)
    assert female > 0.9


def test_disease_severity_moves_biomarkers_in_the_right_direction():
    cohort = generate_cohort("COPD", 400, seed=11, as_of=AS_OF)
    mild = [p.biomarkers["FEV1_pct_predicted"] for p in cohort if p.stage == "GOLD1"]
    severe = [p.biomarkers["FEV1_pct_predicted"] for p in cohort if p.stage == "GOLD4"]

    assert mild and severe
    assert sum(mild) / len(mild) > sum(severe) / len(severe)


def test_barriers_drag_adherence_down():
    """The coupling that makes the stress-test worth running."""
    cohort = generate_cohort("type 2 diabetes", 400, seed=13, as_of=AS_OF)
    low = [p.adherence_baseline for p in cohort if p.health_literacy == "low"]
    high = [p.adherence_baseline for p in cohort if p.health_literacy == "high"]

    assert low and high
    assert sum(low) / len(low) < sum(high) / len(high)


def test_journey_is_ordered_and_ends_before_today():
    cohort = generate_cohort("rheumatoid arthritis", 30, seed=17, as_of=AS_OF)
    for patient in cohort:
        dates = [m.when for m in patient.journey if m.when]
        assert dates == sorted(dates)
        assert max(dates) <= AS_OF
        stages = [m.stage for m in patient.journey]
        assert stages.index("symptom_onset") < stages.index("diagnosis")
        assert stages.index("diagnosis") < stages.index("treatment_start")


def test_medications_deepen_with_stage():
    epi = for_condition("type 2 diabetes")
    cohort = generate_cohort("type 2 diabetes", 300, seed=19, as_of=AS_OF)
    early = [len(p.medications) for p in cohort if p.stage == "early"]
    advanced = [len(p.medications) for p in cohort if p.stage == "advanced"]

    assert sum(early) / len(early) < sum(advanced) / len(advanced)
    assert all(len(p.medications) <= len(epi.medication_ladder) for p in cohort)


def test_summary_reports_the_panel_shape():
    cohort = generate_cohort("type 2 diabetes", 40, seed=23, as_of=AS_OF)
    summary = cohort_summary(cohort)

    assert summary["n"] == 40
    assert summary["age_range"][0] <= summary["age_mean"] <= summary["age_range"][1]
    assert sum(summary["sex"].values()) == 40
    assert 0 <= summary["adherence_mean"] <= 1
    assert summary["comorbidity_prevalence"]


def test_empty_and_invalid_sizes():
    assert generate_cohort("COPD", 0) == []
    assert cohort_summary([]) == {"n": 0}
    with pytest.raises(ValueError):
        generate_cohort("COPD", -1)
