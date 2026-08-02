"""Common random numbers: every stochastic decision seeds from stable identity.

This is the precondition for counterfactual fork-and-diff meaning anything. The
fork's promise is "identical seeds isolate the design change", and that holds
only if a draw is keyed by *what it is*, never by *when it happens*.

If a visit's hazard draw were keyed by sequence position, dropping visit 3 would
shift every later draw — visit 4 would consume visit 3's randomness — and
personas would flip outcomes for reasons unrelated to the design change. Noise
laundered as effect, and worse, noise that looks like a finding.

So: seed from (persona_seed, visit_id) where visit_id survives scenario
mutation. That is common random numbers from the simulation literature, and it
is what makes the paired diff low-variance.

Note what is and is not asserted below. Dropping a visit legitimately changes
the *state* at later visits (less accumulated burden, different missed-visit
run), so a surviving visit may well produce a different OUTCOME. That is causal
signal. What must not change is the DRAW — the seed the visit consumes.
"""
from datetime import date

import pytest

from spp.cohort import generate_cohort
from spp.foundation import EventType
from spp.protocol import ProtocolBurden
from spp.simulation import schedule_from_protocol, simulate_cohort

AS_OF = date(2026, 8, 1)


@pytest.fixture(scope="module")
def cohort():
    return generate_cohort("type 2 diabetes", 60, seed=42, as_of=AS_OF)


@pytest.fixture(scope="module")
def schedule():
    return schedule_from_protocol(ProtocolBurden(visits_per_year=6), 365)


def seed_paths_by_visit(logs) -> dict[tuple[str, str], str]:
    """(persona_id, visit_id) -> the seed path that visit consumed."""
    out: dict[tuple[str, str], str] = {}
    for persona_id, log in logs.items():
        for event in log:
            visit = event.payload.get("visit")
            if visit and event.seed_path:
                out[(persona_id, str(visit))] = event.seed_path
    return out


class TestStableVisitIdentity:
    def test_visits_carry_an_identity_distinct_from_their_position(self, schedule):
        """A visit's identity must not be derived from where it sits in the list."""
        ids = [visit.visit_id for visit in schedule.visits]
        assert len(set(ids)) == len(ids), "visit ids must be unique"

        shortened = schedule.without(schedule.visits[2].visit_id)
        surviving = [v.visit_id for v in shortened.visits]

        assert schedule.visits[2].visit_id not in surviving
        # The visits after the dropped one keep their identity — this is the
        # whole point. If ids renumbered, every later draw would shift.
        assert surviving == [
            v.visit_id for v in schedule.visits if v.visit_id != schedule.visits[2].visit_id
        ]

    def test_dropping_a_visit_does_not_disturb_earlier_or_later_identities(self, schedule):
        dropped = schedule.visits[2].visit_id
        mutated = schedule.without(dropped)

        original = {v.visit_id: v.day for v in schedule.visits if v.visit_id != dropped}
        after = {v.visit_id: v.day for v in mutated.visits}
        assert original == after, "mutation must not move surviving visits"

    def test_making_a_visit_remote_preserves_its_identity(self, schedule):
        target = schedule.visits[4].visit_id
        mutated = schedule.remote(target)

        assert [v.visit_id for v in mutated.visits] == [
            v.visit_id for v in schedule.visits
        ]
        changed = next(v for v in mutated.visits if v.visit_id == target)
        original = next(v for v in schedule.visits if v.visit_id == target)
        assert changed.remote and not original.remote
        assert changed.burden.travel < original.burden.travel


class TestCommonRandomNumbers:
    def test_surviving_visits_consume_identical_seeds_after_a_drop(
        self, cohort, schedule
    ):
        """THE test. Drop visit 3; visits 1, 2, 4, 5, 6 must draw exactly as before.

        Without this, a fork's flip table is contaminated by personas whose
        randomness merely shifted, and the diff measures the mechanism instead of
        the design change.
        """
        dropped = schedule.visits[2].visit_id
        baseline = simulate_cohort(cohort, schedule, seed=42)
        counterfactual = simulate_cohort(cohort, schedule.without(dropped), seed=42)

        before = seed_paths_by_visit(baseline)
        after = seed_paths_by_visit(counterfactual)

        compared = 0
        for (persona_id, visit_id), seed_path in after.items():
            if visit_id == dropped:
                pytest.fail(f"dropped visit {dropped} still appears for {persona_id}")
            if (persona_id, visit_id) in before:
                assert seed_path == before[(persona_id, visit_id)], (
                    f"{persona_id}/{visit_id} drew from {seed_path} but drew from "
                    f"{before[(persona_id, visit_id)]} in the baseline — seeds are "
                    "keyed by position, not identity"
                )
                compared += 1
        assert compared > 50, "too few surviving visits compared to be meaningful"

    def test_changing_one_visit_does_not_reseed_the_others(self, cohort, schedule):
        target = schedule.visits[4].visit_id
        baseline = simulate_cohort(cohort, schedule, seed=42)
        counterfactual = simulate_cohort(cohort, schedule.remote(target), seed=42)

        before = seed_paths_by_visit(baseline)
        after = seed_paths_by_visit(counterfactual)

        for (persona_id, visit_id), seed_path in after.items():
            if visit_id != target and (persona_id, visit_id) in before:
                assert seed_path == before[(persona_id, visit_id)]

    def test_a_persona_seed_does_not_depend_on_cohort_size(self, schedule):
        """Already covered for generation; asserted here for simulation too."""
        small = generate_cohort("type 2 diabetes", 10, seed=42, as_of=AS_OF)
        large = generate_cohort("type 2 diabetes", 40, seed=42, as_of=AS_OF)

        small_logs = simulate_cohort(small, schedule, seed=42)
        large_logs = simulate_cohort(large, schedule, seed=42)

        for persona in small:
            assert (
                small_logs[persona.patient_id].model_dump()
                == large_logs[persona.patient_id].model_dump()
            )


class TestNoOpFork:
    def test_an_unchanged_schedule_reproduces_the_run_exactly(self, cohort, schedule):
        """Zero personas may flip when nothing changed."""
        baseline = simulate_cohort(cohort, schedule, seed=42)
        again = simulate_cohort(cohort, schedule.model_copy(deep=True), seed=42)

        assert {k: v.model_dump() for k, v in baseline.items()} == {
            k: v.model_dump() for k, v in again.items()
        }

    def test_dropped_visit_never_appears_in_any_log(self, cohort, schedule):
        dropped = schedule.visits[2].visit_id
        logs = simulate_cohort(cohort, schedule.without(dropped), seed=42)

        seen = {
            str(event.payload.get("visit"))
            for log in logs.values()
            for event in log
            if event.payload.get("visit")
        }
        assert dropped not in seen
        assert len(seen) == len(schedule.visits) - 1
