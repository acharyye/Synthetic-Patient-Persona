"""Property and metamorphic tests for the simulation core (roadmap §5.1).

These state invariants that must hold for *any* cohort, not just the ones we
thought to write down. They are the guardrail that lets an AI coding workflow
refactor the engine aggressively without silent regressions.
"""
from datetime import date

import pytest
from hypothesis import HealthCheck, given, settings as hyp_settings, strategies as st

from spp.cohort import generate_cohort
from spp.foundation import EventLog, EventType, fold
from spp.protocol import ProtocolBurden, burden_profile, screen
from spp.schemas import Medication, PatientDNA

AS_OF = date(2026, 8, 1)
CONDITIONS = ["type 2 diabetes", "COPD", "breast cancer", "rheumatoid arthritis"]

# Keep Hypothesis quiet about our function-scoped work; these build their own data.
COMMON = hyp_settings(
    max_examples=40,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)


personas = st.builds(
    PatientDNA,
    patient_id=st.text(min_size=1, max_size=8, alphabet="abcdefghijklmnop"),
    age=st.integers(min_value=18, max_value=100),
    sex=st.sampled_from(["female", "male", "other"]),
    condition=st.sampled_from(CONDITIONS),
    stage=st.sampled_from(["early", "moderate", "advanced", None]),
    comorbidities=st.lists(
        st.sampled_from(["hypertension", "CKD", "obesity", "depression"]),
        max_size=4, unique=True,
    ),
    medications=st.lists(
        st.builds(Medication, name=st.sampled_from(["a", "b", "c", "d"])),
        max_size=4,
    ),
    adherence_baseline=st.floats(min_value=0.0, max_value=1.0),
    health_literacy=st.sampled_from(["low", "medium", "high"]),
    social_determinants=st.fixed_dictionaries({
        "transport": st.sampled_from(["own car", "public transport", "none"]),
        "caregiver": st.sampled_from(["spouse", "none"]),
        "employment": st.sampled_from(["retired", "full-time", "shift-work"]),
        "residence": st.sampled_from(["urban", "rural"]),
    }),
)

cohorts = st.lists(personas, min_size=1, max_size=25).map(
    # patient_id must be unique for attribution to mean anything.
    lambda people: [p.model_copy(update={"patient_id": f"p{i}"}) for i, p in enumerate(people)]
)


class TestEligibilityProperties:
    @given(cohort=cohorts)
    @COMMON
    def test_relaxing_a_rule_never_reduces_eligibility(self, cohort):
        """Monotonicity. If dropping a criterion loses you patients, the
        attribution numbers in every report are wrong."""
        strict = ["age >= 50", "stage in {moderate, advanced}"]
        relaxed = ["age >= 50"]
        assert screen(cohort, relaxed).n_eligible >= screen(cohort, strict).n_eligible

    @given(cohort=cohorts)
    @COMMON
    def test_adding_an_exclusion_never_increases_eligibility(self, cohort):
        base = screen(cohort, ["age >= 18"]).n_eligible
        with_exclusion = screen(cohort, ["age >= 18"], ["CKD"]).n_eligible
        assert with_exclusion <= base

    @given(cohort=cohorts)
    @COMMON
    def test_no_criteria_admits_everyone(self, cohort):
        assert screen(cohort).n_eligible == len(cohort)

    @given(cohort=cohorts)
    @COMMON
    def test_eligibility_rate_is_a_probability(self, cohort):
        result = screen(cohort, ["age >= 50"], ["CKD"])
        assert 0.0 <= result.eligibility_rate <= 1.0
        assert result.n_eligible == sum(1 for v in result.verdicts if v.eligible)

    @given(cohort=cohorts)
    @COMMON
    def test_a_verdict_exists_for_every_persona_exactly_once(self, cohort):
        result = screen(cohort, ["age >= 50"], ["CKD"])
        ids = [v.patient_id for v in result.verdicts]
        assert sorted(ids) == sorted(p.patient_id for p in cohort)

    @given(cohort=cohorts)
    @COMMON
    def test_sole_reason_never_exceeds_screened_out(self, cohort):
        result = screen(cohort, ["age >= 50", "stage in {advanced}"], ["CKD"])
        for impact in result.criteria_impact:
            assert 0 <= impact.sole_reason <= impact.screened_out <= len(cohort)

    @given(cohort=cohorts)
    @COMMON
    def test_an_ineligible_persona_always_has_a_stated_reason(self, cohort):
        """Explainability is the product: a rejection with no reason is a bug."""
        result = screen(cohort, ["age >= 50"], ["CKD"])
        for verdict in result.verdicts:
            if not verdict.eligible:
                assert verdict.reasons
                assert verdict.failed_inclusion or verdict.matched_exclusion

    @given(cohort=cohorts, data=st.data())
    @COMMON
    def test_permuting_the_cohort_does_not_change_the_outcome(self, cohort, data):
        """Metamorphic: persona order is not information."""
        shuffled = data.draw(st.permutations(cohort))
        first = screen(cohort, ["age >= 50"], ["CKD"])
        second = screen(list(shuffled), ["age >= 50"], ["CKD"])

        assert first.n_eligible == second.n_eligible
        assert sorted(first.eligible_ids) == sorted(second.eligible_ids)


class TestBurdenProperties:
    @given(persona=personas)
    @COMMON
    def test_score_is_bounded(self, persona):
        assert 0.0 <= burden_profile(persona).score <= 1.0

    @given(persona=personas)
    @COMMON
    def test_a_heavier_protocol_never_lowers_burden(self, persona):
        light = burden_profile(persona, ProtocolBurden(visits_per_year=1))
        heavy = burden_profile(
            persona,
            ProtocolBurden(visits_per_year=24, daily_diary=True, washout_required=True),
        )
        assert heavy.score >= light.score

    @given(persona=personas)
    @COMMON
    def test_a_score_above_zero_always_names_its_drivers(self, persona):
        profile = burden_profile(persona)
        if profile.score > 0:
            assert profile.drivers

    @given(persona=personas)
    @COMMON
    def test_scoring_is_deterministic(self, persona):
        assert burden_profile(persona).score == burden_profile(persona).score


class TestCohortProperties:
    @given(
        condition=st.sampled_from(CONDITIONS),
        n=st.integers(min_value=1, max_value=30),
        seed=st.integers(min_value=0, max_value=10_000),
    )
    @COMMON
    def test_same_seed_gives_an_identical_cohort(self, condition, n, seed):
        first = generate_cohort(condition, n, seed=seed, as_of=AS_OF)
        second = generate_cohort(condition, n, seed=seed, as_of=AS_OF)
        assert [p.model_dump() for p in first] == [p.model_dump() for p in second]

    @given(
        condition=st.sampled_from(CONDITIONS),
        n=st.integers(min_value=1, max_value=30),
    )
    @COMMON
    def test_generated_personas_are_internally_consistent(self, condition, n):
        for persona in generate_cohort(condition, n, seed=3, as_of=AS_OF):
            assert 0.0 <= persona.adherence_baseline <= 1.0
            assert all(0.0 <= m.adherence <= 1.0 for m in persona.medications)
            assert len(set(persona.comorbidities)) == len(persona.comorbidities)
            dates = [m.when for m in persona.journey if m.when]
            assert dates == sorted(dates)
            assert max(dates) <= AS_OF

    @given(condition=st.sampled_from(CONDITIONS), n=st.integers(min_value=2, max_value=40))
    @COMMON
    def test_cohort_size_is_exactly_what_was_asked_for(self, condition, n):
        cohort = generate_cohort(condition, n, seed=11, as_of=AS_OF)
        assert len(cohort) == n
        assert len({p.patient_id for p in cohort}) == n


class TestEventLogProperties:
    events = st.lists(
        st.tuples(
            st.sampled_from([
                EventType.VISIT_COMPLETED,
                EventType.VISIT_MISSED,
                EventType.BARRIER_TRIGGERED,
                EventType.INTERVIEWED,
            ]),
            st.integers(min_value=0, max_value=365),
        ),
        max_size=20,
    ).map(lambda pairs: sorted(pairs, key=lambda pair: pair[1]))

    @given(entries=events)
    @COMMON
    def test_the_fold_is_pure(self, entries):
        log = EventLog(persona_id="p")
        for event_type, t in entries:
            log.append(event_type, t=t, payload={"barrier": "x"})
        assert fold(log) == fold(log)

    @given(entries=events)
    @COMMON
    def test_folding_a_prefix_never_overcounts(self, entries):
        log = EventLog(persona_id="p")
        for event_type, t in entries:
            log.append(event_type, t=t, payload={"barrier": "x"})

        full = fold(log)
        for cutoff in (0, 30, 180, 365):
            partial = fold(log, until=cutoff)
            assert partial.visits_completed <= full.visits_completed
            assert partial.visits_missed <= full.visits_missed
            assert partial.event_count <= full.event_count

    @given(entries=events, cutoff=st.integers(min_value=0, max_value=365))
    @COMMON
    def test_forking_then_folding_equals_folding_until(self, entries, cutoff):
        """Fork-and-replay must agree with time travel, or counterfactual diffs
        would measure the mechanism instead of the design change."""
        log = EventLog(persona_id="p")
        for event_type, t in entries:
            log.append(event_type, t=t, payload={"barrier": "x"})

        assert fold(log.fork_at(cutoff)) == fold(log, until=cutoff)


class TestMetamorphic:
    @pytest.mark.parametrize("condition", CONDITIONS)
    def test_doubling_the_cohort_roughly_preserves_rates(self, condition):
        """Rates are population properties; they must not depend on sample size."""
        small = generate_cohort(condition, 200, seed=5, as_of=AS_OF)
        large = generate_cohort(condition, 400, seed=5, as_of=AS_OF)

        criteria = ["age >= 50"]
        small_rate = screen(small, criteria).eligibility_rate
        large_rate = screen(large, criteria).eligibility_rate
        assert small_rate == pytest.approx(large_rate, abs=0.12)

    def test_a_cohort_is_a_prefix_of_a_larger_one_with_the_same_seed(self):
        """Personas are drawn in order from a seeded stream, so growing n must
        extend the cohort rather than redraw it."""
        small = generate_cohort("COPD", 10, seed=9, as_of=AS_OF)
        large = generate_cohort("COPD", 25, seed=9, as_of=AS_OF)
        assert [p.model_dump() for p in large[:10]] == [p.model_dump() for p in small]
