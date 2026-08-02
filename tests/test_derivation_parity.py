"""MIGRATION TEST — delete this file at cutover, with the Python derivation.

Pins DSL-evaluated barrier derivation against the Python-evaluated derivation in
`cohort/traits.py`, so the move from code to domain-pack data is a diff nobody
has to eyeball. Same pattern as the persona-id migration: snapshot the current
behaviour, change the mechanism, prove nothing moved.

Lifecycle: green today, green through one release after cutover, then removed
together with `traits._signals`. Its green IS the cutover signal.

EVALUATION CONTEXT — one parser, two consumers:
  * eligibility  evaluates at SCREENING time against a complete profile
  * derivation   evaluates at GENERATION time against a profile mid-build
Same grammar, different guarantees about what is populated. That difference is
why the missing-data class below is pinned separately.
"""
from datetime import date

import pytest

from spp.cohort import generate_cohort
from spp.cohort.traits import _signals
from spp.protocol import parse_criterion
from spp.schemas import PatientDNA

AS_OF = date(2026, 8, 1)

# Every predicate `traits.py` computes in Python, written in the existing DSL.
# The rule language a domain pack needs already exists — this is the proof.
DERIVATION_RULES: dict[str, str] = {
    "low_literacy": "health_literacy == low",
    "low_adherence": "adherence_baseline < 0.6",
    "polypharmacy": "n_medications >= 3",
    "multimorbidity": "n_comorbidities >= 3",
    "elderly": "age >= 75",
    "no_transport": "sdoh.transport == none",
    "public_transport": "sdoh.transport == public transport",
    "shift_work": "sdoh.employment == shift-work",
    "no_caregiver": "sdoh.caregiver == none",
    "rural": "sdoh.residence == rural",
    "low_digital": "traits.digital_literacy < 0.3",
    "low_mobility": "traits.mobility < 0.3",
    "financially_stretched": "traits.financial_security < 0.3",
}

CONDITIONS = ["type 2 diabetes", "COPD", "heart failure",
              "breast cancer", "rheumatoid arthritis"]


@pytest.fixture(scope="module")
def cohort():
    people = []
    for condition in CONDITIONS:
        people.extend(generate_cohort(condition, 20, seed=42, as_of=AS_OF))
    return people


class TestEveryPredicateIsExpressible:
    @pytest.mark.parametrize("signal,expression", sorted(DERIVATION_RULES.items()))
    def test_the_existing_dsl_parses_it(self, signal, expression):
        assert parse_criterion(expression) is not None

    def test_no_derivation_signal_is_left_behind(self):
        """If traits.py grows a signal, this fails until it has a DSL form —
        otherwise the port would silently leave a rule in Python."""
        from spp.schemas import PatientDNA as P

        probe = P(patient_id="x", age=50, sex="female", condition="COPD")
        derivable = set(_signals(probe))
        # `caregiving` and `advanced_stage`/`early_stage` feed GOALS, not
        # barriers, and port with the goal rules rather than these.
        goal_only = {"caregiving", "advanced_stage", "early_stage", "working"}
        assert derivable - goal_only - set(DERIVATION_RULES) == set()


class TestParityOnPopulatedProfiles:
    @pytest.mark.parametrize("signal,expression", sorted(DERIVATION_RULES.items()))
    def test_dsl_matches_python_exactly(self, cohort, signal, expression):
        criterion = parse_criterion(expression)
        for dna in cohort:
            assert criterion.matches(dna)[0] == _signals(dna)[signal], (
                f"{signal} diverged on {dna.patient_id}"
            )

    def test_the_whole_barrier_set_is_reproducible(self, cohort):
        """Not just per-signal: the derived barrier NAMES must match too."""
        from spp.assumptions import BARRIER_SEVERITY

        for dna in cohort:
            via_python = {b.name for b in dna.barriers}
            via_dsl = {
                barrier
                for signal, expression in DERIVATION_RULES.items()
                for barrier in [_BARRIER_FOR.get(signal)]
                if barrier and parse_criterion(expression).matches(dna)[0]
            }
            assert via_dsl <= set(BARRIER_SEVERITY.params)
            assert via_dsl == via_python & set(_BARRIER_FOR.values()), dna.patient_id


# signal -> barrier the current code derives from it.
_BARRIER_FOR = {
    "no_transport": "transport", "public_transport": "transport_fragile",
    "shift_work": "scheduling", "low_literacy": "comprehension",
    "low_digital": "digital_access", "no_caregiver": "unsupported",
    "low_adherence": "adherence", "polypharmacy": "pill_burden",
    "multimorbidity": "competing_care", "low_mobility": "mobility",
    "financially_stretched": "cost", "rural": "distance",
}


class TestMissingDataSemanticsAreUnstated:
    """The two paths agree on missing data BY COINCIDENCE, not by design.

    Python: `sdoh.get("transport")` returns None, and `None == "none"` is False.
    DSL:    the field resolves to `_MISSING`, and the clause evaluates False.

    Same answer, different reasons — and for `traits.*` the Python path is doing
    something else again: `.get(name, 0.5)` is MEDIAN IMPUTATION wearing
    missing-handling's clothes. Change that default to 0.2 and the two diverge
    silently.

    These tests pin the current behaviour so the port has to DECLARE a policy
    (`on_missing: no_barrier | barrier | flag`) rather than inherit one. A
    persona with no transport barrier and a persona whose transport is
    unrecorded are different personas to the burden model.
    """

    def test_absent_sdoh_yields_no_barrier_in_both_paths(self):
        dna = PatientDNA(patient_id="p", age=60, sex="female", condition="COPD",
                         social_determinants={"caregiver": "spouse"})
        assert _signals(dna)["no_transport"] is False
        assert parse_criterion("sdoh.transport == none").matches(dna)[0] is False

    def test_but_they_reach_it_differently(self):
        """The DSL says so explicitly; Python arrives by falsy comparison."""
        dna = PatientDNA(patient_id="p", age=60, sex="female", condition="COPD",
                         social_determinants={})
        _, detail = parse_criterion("sdoh.transport == none").matches(dna)
        assert "not recorded" in detail

    def test_absent_traits_are_imputed_not_treated_as_missing(self):
        """The load-bearing one, and it DEMONSTRATES the divergence rather than
        asserting half of it.

        Both sides agree at the shipped threshold (0.3) only because the imputed
        median 0.5 happens to sit above it. Evaluate both at a threshold ABOVE
        the median and they part company: Python's `.get(name, 0.5)` returns
        True, the DSL returns False because the field is genuinely absent.
        """
        dna = PatientDNA(patient_id="p", age=60, sex="female", condition="COPD",
                         traits={})

        # At the shipped threshold: agreement.
        assert _signals(dna)["low_mobility"] is False
        assert parse_criterion("traits.mobility < 0.3").matches(dna)[0] is False

        # Same two mechanisms at a threshold above the median, evaluated
        # explicitly rather than described.
        python_side = dna.traits.get("mobility", 0.5) < 0.9      # imputes
        dsl_side, detail = parse_criterion("traits.mobility < 0.9").matches(dna)

        assert python_side is True, "Python imputes the median"
        assert dsl_side is False, "the DSL treats absent as absent"
        assert "not recorded" in detail
        assert python_side != dsl_side, (
            "This is the unstated semantic the port must declare as "
            "`on_missing: no_barrier | barrier | flag` — inheriting the "
            "eligibility policy by default would repeat the correlation-matrix "
            "bug in miniature."
        )
