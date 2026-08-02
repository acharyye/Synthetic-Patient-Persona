import pytest

from spp.protocol import CriterionError, parse_criterion, screen
from spp.schemas import Medication, PatientDNA


def make(**overrides) -> PatientDNA:
    base = dict(
        patient_id="p1",
        age=64,
        sex="female",
        condition="type 2 diabetes",
        stage="moderate",
        biomarkers={"HbA1c_pct": 8.2, "eGFR": 55},
        comorbidities=["hypertension", "CKD"],
        medications=[Medication(name="metformin", dose="1000mg", adherence=0.7)],
        adherence_baseline=0.7,
        health_literacy="low",
        social_determinants={"transport": "none", "caregiver": "spouse"},
    )
    return PatientDNA(**{**base, **overrides})


def matched(text: str, dna: PatientDNA) -> bool:
    return parse_criterion(text).matches(dna)[0]


class TestComparison:
    @pytest.mark.parametrize(
        "criterion,expected",
        [
            ("age >= 50", True),
            ("age>=50", True),
            ("age > 64", False),
            ("age <= 64", True),
            ("adherence_baseline < 0.5", False),
            ("n_comorbidities >= 2", True),
            ("n_medications == 1", True),
            ("sex == female", True),
            ("sex != female", False),
            ("condition = type 2 diabetes", True),
        ],
    )
    def test_scalar_comparisons(self, criterion, expected):
        assert matched(criterion, make()) is expected

    @pytest.mark.parametrize(
        "criterion,expected",
        [
            ("biomarkers.HbA1c_pct > 7.5", True),
            ("biomarkers.HbA1c_pct < 7.5", False),
            ("biomarkers.eGFR < 30", False),
            ("biomarkers.hba1c_pct > 7.5", True),  # key match is case-insensitive
            ("sdoh.transport == none", True),
            ("social_determinants.caregiver == spouse", True),
        ],
    )
    def test_namespaced_lookup(self, criterion, expected):
        assert matched(criterion, make()) is expected

    def test_ordinal_fields_compare_by_rank(self):
        assert matched("health_literacy < high", make()) is True
        assert matched("health_literacy >= medium", make()) is False
        assert matched("stage >= moderate", make()) is True
        assert matched("stage > moderate", make()) is False

    def test_gold_and_nyha_ladders(self):
        copd = make(condition="COPD", stage="GOLD3", biomarkers={})
        assert matched("stage >= GOLD2", copd) is True
        assert matched("stage >= GOLD4", copd) is False

    def test_ordering_unrelated_strings_is_rejected(self):
        with pytest.raises(CriterionError, match="no shared ordinal scale"):
            matched("sex > female", make())

    def test_missing_value_is_false_not_an_error(self):
        dna = make(biomarkers={}, stage=None)
        assert matched("biomarkers.HbA1c_pct > 7", dna) is False
        assert matched("stage in {early}", dna) is False


class TestMembership:
    @pytest.mark.parametrize(
        "criterion,expected",
        [
            ("stage in {moderate, advanced}", True),
            ("stage in {early}", False),
            ("stage not in {early}", True),
            ("sex not in {male}", True),
            ("health_literacy in {low, medium}", True),
        ],
    )
    def test_membership(self, criterion, expected):
        assert matched(criterion, make()) is expected


class TestPresence:
    @pytest.mark.parametrize(
        "criterion,expected",
        [
            ("CKD", True),
            ("ckd", True),
            ("hypertension", True),
            ("metformin", True),          # medication names count
            ("type 2 diabetes", True),    # the primary condition counts
            ("diabetes", True),           # containment fallback
            ("COPD", False),
            ("not COPD", True),
            ("not metformin", False),
        ],
    )
    def test_presence(self, criterion, expected):
        assert matched(criterion, make()) is expected


class TestParsingFailsLoudly:
    @pytest.mark.parametrize(
        "criterion",
        ["", "   ", "age >= ", "waist_circumference > 100", "foo.bar == 1", "stage in {}"],
    )
    def test_bad_criteria_raise(self, criterion):
        with pytest.raises(CriterionError):
            parse_criterion(criterion)

    def test_screen_raises_before_evaluating_anyone(self):
        with pytest.raises(CriterionError, match="unknown field"):
            screen([make()], inclusion=["age >= 50", "nonsense_field > 1"])


class TestScreening:
    def test_inclusion_is_anded_exclusion_is_ored(self):
        cohort = [
            make(patient_id="in", age=60, comorbidities=[]),
            make(patient_id="too-young", age=30, comorbidities=[]),
            make(patient_id="excluded", age=60, comorbidities=["CKD"]),
        ]
        result = screen(cohort, inclusion=["age >= 50"], exclusion=["CKD"])

        assert result.eligible_ids == ["in"]
        assert result.n_screened == 3
        assert result.n_eligible == 1
        assert result.eligibility_rate == pytest.approx(0.333, abs=1e-3)

    def test_verdict_records_why(self):
        result = screen([make(age=30)], inclusion=["age >= 50"], exclusion=["CKD"])
        verdict = result.verdicts[0]

        assert verdict.eligible is False
        assert verdict.failed_inclusion == ["age >= 50"]
        assert verdict.matched_exclusion == ["CKD"]
        assert any("age=30" in r for r in verdict.reasons)

    def test_sole_reason_isolates_the_expensive_criterion(self):
        cohort = [
            make(patient_id="a", age=40, comorbidities=[]),   # young only
            make(patient_id="b", age=40, comorbidities=[]),   # young only
            make(patient_id="c", age=60, comorbidities=["CKD"]),  # CKD only
            make(patient_id="d", age=30, comorbidities=["CKD"]),  # both
        ]
        result = screen(cohort, inclusion=["age >= 50"], exclusion=["CKD"])
        impact = {c.criterion: c for c in result.criteria_impact}

        assert impact["age >= 50"].screened_out == 3
        assert impact["age >= 50"].sole_reason == 2
        assert impact["CKD"].screened_out == 2
        assert impact["CKD"].sole_reason == 1
        assert impact["age >= 50"].screened_out_rate == 0.75

    def test_no_criteria_means_everyone_is_eligible(self):
        result = screen([make(patient_id=f"p{i}") for i in range(5)])
        assert result.n_eligible == 5
        assert result.eligibility_rate == 1.0
        assert result.criteria_impact == []

    def test_empty_cohort_does_not_divide_by_zero(self):
        result = screen([], inclusion=["age >= 50"])
        assert result.n_screened == 0
        assert result.eligibility_rate == 0.0
        assert result.criteria_impact[0].screened_out_rate == 0.0
