"""Timeline simulation: determinism, isolation, and the invariants a survival
curve has to satisfy before anyone should look at it.
"""
from datetime import date

import pytest
from hypothesis import HealthCheck, given, settings as hyp_settings, strategies as st

from spp.cohort import generate_cohort
from spp.foundation import EventType, JourneyStage, fold
from spp.foundation.rng import cohort_scope, persona_scope
from spp.protocol import ProtocolBurden
from spp.simulation import (
    VisitSchedule,
    attendance_probability,
    burden_breakdown,
    burden_sensitivity,
    dropout_probability,
    retention_summary,
    schedule_from_protocol,
    simulate_cohort,
    simulate_persona,
    survival_curve,
)

AS_OF = date(2026, 8, 1)
COMMON = hyp_settings(
    max_examples=25, deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)


@pytest.fixture(scope="module")
def cohort():
    return generate_cohort("type 2 diabetes", 60, seed=42, as_of=AS_OF)


@pytest.fixture(scope="module")
def schedule():
    return schedule_from_protocol(ProtocolBurden(visits_per_year=12), 365)


class TestSchedule:
    def test_visit_count_matches_the_protocol(self):
        assert len(schedule_from_protocol(ProtocolBurden(visits_per_year=12), 365)) == 12
        assert len(schedule_from_protocol(ProtocolBurden(visits_per_year=4), 365)) == 4

    def test_visits_are_ordered_and_within_the_horizon(self, schedule):
        days = [v.day for v in schedule.visits]
        assert days == sorted(days)
        assert max(days) <= schedule.duration_days

    def test_remote_protocols_cost_less_travel(self):
        onsite = schedule_from_protocol(ProtocolBurden(visits_per_year=4), 365)
        remote = schedule_from_protocol(
            ProtocolBurden(visits_per_year=4, travel_required=False), 365
        )
        assert remote.visits[0].burden.travel < onsite.visits[0].burden.travel

    def test_washout_is_a_one_off_cost_at_the_first_visit(self):
        sched = schedule_from_protocol(
            ProtocolBurden(visits_per_year=4, washout_required=True), 365
        )
        assert sched.visits[0].burden.procedural > sched.visits[1].burden.procedural


class TestBurdenSensitivity:
    def test_the_same_protocol_is_a_different_ask_for_different_people(self):
        """The core claim of burden vector v2."""
        cohort = generate_cohort("COPD", 200, seed=5, as_of=AS_OF)
        shift = [p for p in cohort
                 if p.social_determinants.get("employment") == "shift-work"]
        retired = [p for p in cohort
                   if p.social_determinants.get("employment") == "retired"]
        assert shift and retired

        shift_mean = sum(burden_sensitivity(p).scheduling for p in shift) / len(shift)
        retired_mean = sum(burden_sensitivity(p).scheduling for p in retired) / len(retired)
        assert shift_mean > retired_mean

    def test_no_transport_amplifies_travel(self):
        cohort = generate_cohort("COPD", 200, seed=5, as_of=AS_OF)
        none = [p for p in cohort if p.social_determinants.get("transport") == "none"]
        car = [p for p in cohort if p.social_determinants.get("transport") == "own car"]
        assert none and car
        assert (sum(burden_sensitivity(p).travel for p in none) / len(none)
                > sum(burden_sensitivity(p).travel for p in car) / len(car))


class TestHazardBounds:
    @given(
        adherence=st.floats(min_value=0.0, max_value=1.0),
        burden=st.floats(min_value=0.0, max_value=50.0),
        missed=st.integers(min_value=0, max_value=20),
    )
    @COMMON
    def test_probabilities_stay_probabilities(self, adherence, burden, missed):
        """No overflow, no negative, no >1 — however extreme the state."""
        from spp.assumptions import ATTENDANCE, DROPOUT_HAZARD
        from spp.foundation.events import BurdenVector, PersonaState
        from spp.schemas import PatientDNA

        dna = PatientDNA(
            patient_id="x", age=70, sex="female", condition="COPD",
            adherence_baseline=adherence,
        )
        state = PersonaState(persona_id="x", burden=BurdenVector(travel=burden))
        increment = BurdenVector(travel=burden / 10)

        attend = attendance_probability(dna, state, increment)
        drop = dropout_probability(dna, state, increment, missed)

        assert ATTENDANCE.params["floor"] <= attend <= ATTENDANCE.params["ceiling"]
        assert 0.0 <= drop <= DROPOUT_HAZARD.params["max_per_visit"]


class TestDeterminism:
    def test_same_seed_gives_identical_logs(self, cohort, schedule):
        first = simulate_cohort(cohort, schedule, seed=42)
        second = simulate_cohort(cohort, schedule, seed=42)
        assert {k: v.model_dump() for k, v in first.items()} == {
            k: v.model_dump() for k, v in second.items()
        }

    def test_different_seeds_diverge(self, cohort, schedule):
        first = simulate_cohort(cohort, schedule, seed=42)
        second = simulate_cohort(cohort, schedule, seed=43)
        assert first != second

    def test_a_persona_simulates_identically_alone(self, cohort, schedule):
        """Seed isolation: re-running one persona must reproduce its trajectory
        exactly, or counterfactual forking would measure RNG drift."""
        full = simulate_cohort(cohort, schedule, seed=42)

        index = 7
        dna = cohort[index]
        anchor = cohort_scope(42, dna.condition)
        alone = simulate_persona(
            dna, schedule, persona_scope(anchor, index).child("sim")
        )
        assert alone.model_dump() == full[dna.patient_id].model_dump()


class TestTrajectoryInvariants:
    def test_every_persona_enrols_and_reaches_a_terminal_state(self, cohort, schedule):
        for log in simulate_cohort(cohort, schedule, seed=42).values():
            assert log.events[0].type == EventType.ENROLLED
            assert fold(log).terminal

    def test_nothing_happens_after_dropout(self, cohort, schedule):
        for log in simulate_cohort(cohort, schedule, seed=42).values():
            types = [e.type for e in log]
            if EventType.DROPPED_OUT in types:
                assert types.index(EventType.DROPPED_OUT) == len(types) - 1

    def test_visits_never_exceed_the_schedule(self, cohort, schedule):
        for log in simulate_cohort(cohort, schedule, seed=42).values():
            state = fold(log)
            assert state.visits_completed + state.visits_missed <= len(schedule)

    def test_dropouts_record_a_reason(self, cohort, schedule):
        for log in simulate_cohort(cohort, schedule, seed=42).values():
            for event in log.of_type(EventType.DROPPED_OUT):
                assert event.payload.get("reason")
                assert event.payload.get("visit")

    def test_burden_only_accrues_on_attended_visits(self, cohort, schedule):
        for log in simulate_cohort(cohort, schedule, seed=42).values():
            state = fold(log)
            accruals = len(log.of_type(EventType.BURDEN_ACCRUED))
            assert accruals == state.visits_completed


class TestSurvival:
    def test_retention_is_monotone_non_increasing(self, cohort, schedule):
        logs = simulate_cohort(cohort, schedule, seed=42)
        retention = [p["retention"] for p in survival_curve(logs, 365)]
        assert retention == sorted(retention, reverse=True)
        assert retention[0] == 1.0

    def test_a_heavier_protocol_never_retains_more(self, cohort):
        """The property that makes design comparison meaningful."""
        light = simulate_cohort(
            cohort, schedule_from_protocol(
                ProtocolBurden(visits_per_year=4, travel_required=False), 365), seed=42)
        heavy = simulate_cohort(
            cohort, schedule_from_protocol(
                ProtocolBurden(visits_per_year=24, daily_diary=True), 365), seed=42)

        assert (retention_summary(heavy)["retention_rate"]
                <= retention_summary(light)["retention_rate"])

    def test_typical_protocol_retention_is_plausible(self, cohort, schedule):
        """Phase 1 exit criterion, pinned.

        Not a validated figure — the hazard is tuned to this range, not fitted to
        data. The test exists so a refactor can't silently drift the curve out of
        the band the assumption claims.
        """
        rate = retention_summary(simulate_cohort(cohort, schedule, seed=42))["retention_rate"]
        assert 0.70 <= rate <= 0.90, f"typical-protocol retention {rate:.1%} left the band"

    def test_summary_counts_reconcile(self, cohort, schedule):
        logs = simulate_cohort(cohort, schedule, seed=42)
        summary = retention_summary(logs)
        assert summary["retained"] + summary["dropped"] == summary["n"]
        assert sum(summary["dropout_reasons"].values()) == summary["dropped"]

    def test_burden_breakdown_identifies_the_dominant_cost(self, cohort):
        """On-site protocols should be travel-dominated — the actionable finding."""
        logs = simulate_cohort(
            cohort, schedule_from_protocol(ProtocolBurden(visits_per_year=12), 365), seed=42)
        breakdown = burden_breakdown(logs)
        assert breakdown["travel"] == max(breakdown.values())

    def test_empty_inputs_do_not_explode(self):
        assert survival_curve({}, 365) == []
        assert retention_summary({}) == {"n": 0}
        assert burden_breakdown({}) == {}


class TestNoLLMInTheCore:
    def test_simulation_never_calls_the_narration_layer(self, cohort, schedule, monkeypatch):
        """The simulate/narrate separation, enforced rather than documented."""
        import spp.foundation.llm as llm

        def explode(*args, **kwargs):
            raise AssertionError("simulation core called the LLM adapter")

        monkeypatch.setattr(llm, "generate", explode)
        monkeypatch.setattr(llm, "get_backend", explode)

        logs = simulate_cohort(cohort, schedule, seed=42)
        assert retention_summary(logs)["n"] == len(cohort)
