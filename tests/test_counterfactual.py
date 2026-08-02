"""Fork-and-diff, exact attribution, and sensitivity.

The invariants that make a counterfactual finding trustworthy: a no-op fork moves
nobody, a paired diff reports flips rather than subtracted aggregates, and both
attributions are exact rather than sampled.
"""
from datetime import date

import pytest
from hypothesis import HealthCheck, given, settings as hyp_settings, strategies as st

from spp.cohort import generate_cohort
from spp.protocol import (
    ProtocolBurden,
    attribute_dropout,
    attribute_eligibility,
    screen,
)
from spp.simulation import (
    diff_runs,
    fork,
    perturbed,
    run_sensitivity,
    schedule_from_protocol,
    sign_is_stable,
    simulate_cohort,
)

AS_OF = date(2026, 8, 1)
COMMON = hyp_settings(
    max_examples=25, deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)


@pytest.fixture(scope="module")
def cohort():
    return generate_cohort("type 2 diabetes", 150, seed=42, as_of=AS_OF)


@pytest.fixture(scope="module")
def schedule():
    return schedule_from_protocol(ProtocolBurden(visits_per_year=12), 365)


class TestNoOpFork:
    def test_an_identity_mutation_flips_nobody(self, cohort, schedule):
        """The first thing to check. If a no-op fork moves anyone, every
        subsequent number in the phase is contaminated."""
        result = fork(cohort, schedule, lambda s: s, label="no-op")

        assert result.recovered == []
        assert result.lost == []
        assert result.net_flips == 0
        assert result.perturbed == 0
        assert result.unchanged == len(cohort)
        assert result.retention_delta == 0.0

    def test_a_deep_copy_is_still_a_no_op(self, cohort, schedule):
        result = fork(cohort, schedule, lambda s: s.model_copy(deep=True))
        assert result.unchanged == len(cohort)


class TestFlipTable:
    def test_dropping_a_visit_is_reported_as_flips(self, cohort, schedule):
        target = schedule.visits[2].visit_id
        result = fork(cohort, schedule, lambda s: s.without(target), label="drop v003")

        assert result.n == len(cohort)
        # Fewer demands should recover people, not lose them, on balance.
        assert result.net_flips >= 0
        assert len(result.recovered) + len(result.lost) + result.perturbed + \
            result.unchanged == len(cohort)

    def test_every_flip_names_where_it_diverged(self, cohort, schedule):
        target = schedule.visits[1].visit_id
        result = fork(cohort, schedule, lambda s: s.without(target))

        for flip in [*result.recovered, *result.lost]:
            assert flip.diverged_at_event is not None
            assert flip.diverged_at_day is not None
            assert flip.baseline != flip.variant

    def test_recovered_personas_dropped_in_baseline_and_survived_in_variant(
        self, cohort, schedule
    ):
        target = schedule.visits[2].visit_id
        result = fork(cohort, schedule, lambda s: s.without(target))

        for flip in result.recovered:
            assert flip.baseline == "dropped" and flip.variant == "retained"
            assert flip.baseline_exit_reason
            assert flip.variant_exit_reason is None

    def test_making_visits_remote_recovers_travel_burdened_personas(
        self, cohort, schedule
    ):
        """The headline demo: one design change, measured in people."""
        ids = [v.visit_id for v in schedule.visits]
        result = fork(cohort, schedule, lambda s: s.remote(*ids), label="all remote")

        assert result.net_flips > 0
        assert result.burden_shift["travel"] < 0

    def test_a_paired_diff_requires_the_same_cohort(self, cohort, schedule):
        baseline = simulate_cohort(cohort, schedule, seed=42)
        smaller = simulate_cohort(cohort[:50], schedule, seed=42)

        with pytest.raises(ValueError, match="different personas"):
            diff_runs(baseline, smaller, 365)

    def test_headline_reads_in_people_not_percentages(self, cohort, schedule):
        target = schedule.visits[2].visit_id
        result = fork(cohort, schedule, lambda s: s.without(target), label="drop v003")
        assert "net" in result.headline()
        assert str(len(cohort)) in result.headline()


class TestSignStability:
    def test_a_large_change_keeps_its_sign_across_seeds(self, schedule):
        """The honesty guard: for a change this big the direction must be stable,
        or the whole mechanism is suspect."""
        ids = [v.visit_id for v in schedule.visits]
        verdict = sign_is_stable(
            lambda seed: generate_cohort("type 2 diabetes", 150, seed=seed, as_of=AS_OF),
            schedule,
            lambda s: s.remote(*ids),
            seeds=(42, 1234),
        )
        assert verdict["sign_stable"] is True
        assert all(net > 0 for net in verdict["net_flips"])

    def test_a_no_op_change_is_reported_as_unstable_not_as_an_effect(self, schedule):
        """Zero net flips must never read as a stable direction."""
        verdict = sign_is_stable(
            lambda seed: generate_cohort("type 2 diabetes", 80, seed=seed, as_of=AS_OF),
            schedule,
            lambda s: s,
            seeds=(42, 1234),
        )
        assert verdict["net_flips"] == [0, 0]
        assert verdict["sign_stable"] is False
        assert "NOT STABLE" in verdict["verdict"]


class TestExactEligibilityShapley:
    def test_values_sum_to_the_number_excluded(self, cohort):
        """Efficiency. This is what makes 'responsible for 34% of attrition' a
        real share rather than a heuristic."""
        result = screen(
            cohort,
            ["age >= 55", "biomarkers.HbA1c_pct >= 7.5"],
            ["CKD", "adherence_baseline < 0.5"],
        )
        attribution = attribute_eligibility(result)

        total = sum(rule.shapley for rule in attribution.rules)
        assert total == pytest.approx(attribution.n_excluded, abs=1e-6)
        assert attribution.n_excluded == sum(
            1 for v in result.verdicts if not v.eligible
        )

    def test_shares_sum_to_one(self, cohort):
        result = screen(cohort, ["age >= 55"], ["CKD"])
        attribution = attribute_eligibility(result)
        assert sum(r.shapley_share for r in attribution.rules) == pytest.approx(1.0, abs=1e-6)

    def test_sole_reason_is_the_singleton_case(self, cohort):
        """sole_reason counts |F| = 1; Shapley generalises it to any |F|."""
        result = screen(cohort, ["age >= 55"], ["CKD"])
        attribution = attribute_eligibility(result)

        for rule in attribution.rules:
            assert rule.sole_reason <= rule.screened_out
            # A rule blamed only on its own always has shapley == screened_out.
            if rule.sole_reason == rule.screened_out:
                assert rule.shapley == pytest.approx(rule.screened_out)

    def test_a_single_rule_takes_all_the_blame(self, cohort):
        result = screen(cohort, ["age >= 200"])
        attribution = attribute_eligibility(result)
        assert len(attribution.rules) == 1
        assert attribution.rules[0].shapley_share == pytest.approx(1.0)
        assert attribution.rules[0].shapley == pytest.approx(len(cohort))

    def test_two_rules_failing_together_split_the_blame_evenly(self):
        """Symmetric players in a veto game get 1/|F| each — exactly."""
        from spp.schemas import PatientDNA

        people = [
            PatientDNA(patient_id="both", age=20, sex="female", condition="COPD",
                       comorbidities=["CKD"]),
        ]
        result = screen(people, ["age >= 50"], ["CKD"])
        attribution = attribute_eligibility(result)

        assert {r.criterion: r.shapley for r in attribution.rules} == {
            "age >= 50": pytest.approx(0.5),
            "CKD": pytest.approx(0.5),
        }

    def test_no_criteria_attributes_nothing(self, cohort):
        attribution = attribute_eligibility(screen(cohort))
        assert attribution.n_excluded == 0
        assert attribution.rules == []
        assert "no criteria" in attribution.headline()

    @given(
        n=st.integers(min_value=5, max_value=40),
        age_cut=st.integers(min_value=20, max_value=90),
    )
    @COMMON
    def test_efficiency_holds_for_any_cohort_and_criteria(self, n, age_cut):
        people = generate_cohort("COPD", n, seed=7, as_of=AS_OF)
        result = screen(people, [f"age >= {age_cut}"], ["CKD", "lung cancer"])
        attribution = attribute_eligibility(result)
        assert sum(r.shapley for r in attribution.rules) == pytest.approx(
            attribution.n_excluded, abs=1e-6
        )


class TestExactDropoutAttribution:
    def test_terms_reconstruct_the_logit_exactly(self, cohort):
        """Linear model, so decomposition is exact — not an approximation."""
        from spp.foundation.events import BurdenVector, PersonaState

        dna = cohort[0]
        state = PersonaState(persona_id=dna.patient_id, t=120,
                             burden=BurdenVector(travel=0.5, time=0.2))
        increment = BurdenVector(travel=0.08)

        attribution = attribute_dropout(dna, state, increment, consecutive_missed=2)
        rebuilt = attribution.intercept + sum(t.contribution for t in attribution.terms)
        assert rebuilt == pytest.approx(attribution.logit, abs=1e-9)

    def test_shares_of_positive_risk_sum_to_one(self, cohort):
        from spp.foundation.events import BurdenVector, PersonaState

        dna = cohort[0]
        state = PersonaState(persona_id=dna.patient_id, burden=BurdenVector(travel=0.6))
        attribution = attribute_dropout(dna, state, BurdenVector(travel=0.1), 1)

        shares = attribution.shares()
        assert shares
        assert sum(shares.values()) == pytest.approx(1.0, abs=1e-6)

    def test_dominant_term_is_the_largest_contributor(self, cohort):
        from spp.foundation.events import BurdenVector, PersonaState

        dna = cohort[0]
        state = PersonaState(persona_id=dna.patient_id, burden=BurdenVector(travel=2.0))
        attribution = attribute_dropout(dna, state, BurdenVector(travel=0.9), 0)

        dominant = attribution.dominant
        assert dominant is not None
        assert dominant.contribution == max(t.contribution for t in attribution.terms)


class TestSensitivity:
    def test_perturbation_is_restored_even_on_failure(self):
        from spp.assumptions import BURDEN_FACTORS

        original = dict(BURDEN_FACTORS.params)
        with pytest.raises(RuntimeError):
            with perturbed(BURDEN_FACTORS, 2.0):
                assert BURDEN_FACTORS.params != original
                raise RuntimeError("boom")
        assert BURDEN_FACTORS.params == original

    def test_ranking_identifies_the_dominant_assumption(self, cohort, schedule):
        report = run_sensitivity(cohort, schedule, perturbation=0.25, seed=42)

        assert report.entries
        impacts = [entry.impact for entry in report.entries]
        assert impacts == sorted(impacts, reverse=True)
        assert report.headline()

    def test_every_entry_carries_its_confidence(self, cohort, schedule):
        """Sensitivity to an expert_guess coefficient is the finding that matters."""
        report = run_sensitivity(
            cohort, schedule, perturbation=0.25,
            only=["timeline.visit_burden", "timeline.dropout_hazard"],
        )
        assert {e.assumption for e in report.entries} == {
            "timeline.visit_burden", "timeline.dropout_hazard"
        }
        assert all(entry.confidence for entry in report.entries)

    def test_the_ledger_is_unchanged_afterwards(self, cohort, schedule):
        from spp.assumptions import VISIT_BURDEN

        before = dict(VISIT_BURDEN.params)
        run_sensitivity(cohort, schedule, perturbation=0.3,
                        only=["timeline.visit_burden"])
        assert VISIT_BURDEN.params == before


class TestReportArtifact:
    def test_artifact_stamps_seeds_and_ledger(self, cohort, schedule):
        from spp.simulation import build_report

        ids = [v.visit_id for v in schedule.visits]
        diff = fork(cohort, schedule, lambda s: s.remote(*ids), seed=42,
                    label="all remote")
        report = build_report(
            diff, title="t", change="all remote", condition="type 2 diabetes",
            master_seed=42, schedule_name=schedule.name,
            schedule_visits=len(schedule), duration_days=365,
        )

        assert report.provenance.master_seed == 42
        assert report.provenance.cohort_size == len(cohort)
        assert report.assumptions["count"] > 0
        assert report.assumptions["unquotable"]
        assert "DIFFERENCE between designs" in report.disclaimer

    def test_artifact_is_json_serialisable(self, cohort, schedule):
        import json

        from spp.simulation import build_report

        diff = fork(cohort, schedule, lambda s: s.without(schedule.visits[1].visit_id))
        report = build_report(
            diff, title="t", change="drop", condition="type 2 diabetes",
            master_seed=42, schedule_name=schedule.name,
            schedule_visits=len(schedule), duration_days=365,
        )
        assert json.loads(json.dumps(report.model_dump()))["net_flips"] == diff.net_flips


class TestCounterfactualEndpoint:
    def _client(self):
        from fastapi.testclient import TestClient

        from spp.api.main import app

        return TestClient(app)

    def test_endpoint_returns_a_flip_table_and_provenance(self):
        body = self._client().post("/counterfactual/run", json={
            "condition": "type 2 diabetes", "n": 120, "seed": 42,
            "inclusion": ["age >= 50"],
            "burden": {"visits_per_year": 12},
            "remote_visits": ["v001", "v003", "v005"],
        }).json()

        assert body["recovered"] - body["lost"] == body["net_flips"]
        assert body["provenance"]["master_seed"] == 42
        assert body["sign_stability"]["seeds"][0] == 42
        assert body["assumptions"]["count"] > 0

    def test_unknown_visit_ids_are_rejected(self):
        response = self._client().post("/counterfactual/run", json={
            "condition": "COPD", "n": 30, "remote_visits": ["v999"],
        })
        assert response.status_code == 400
        assert "unknown visit id" in response.json()["detail"]

    def test_a_change_must_be_specified(self):
        response = self._client().post("/counterfactual/run", json={
            "condition": "COPD", "n": 30,
        })
        assert response.status_code == 400
        assert "specify" in response.json()["detail"]
