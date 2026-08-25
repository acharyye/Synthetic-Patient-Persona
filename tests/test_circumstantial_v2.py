"""`is_circumstantial` v2 exists, is not wired in, and does what its definition says.

The load-bearing test here is the last one. v2 is an instrument change under
review: it moves `state_coverage` on the v3 cassette without a single model call,
so wiring it into `score()` before blind labels exist would turn a metric
correction into a silent score improvement. That is the one failure this module is
arranged to prevent, so it is pinned rather than remembered.
"""
from datetime import date

import pytest

from spp.cohort import generate_cohort
from spp.knowledge import load_graph
from spp.narration.circumstantial import is_circumstantial_v2, state_only_vocabulary
from spp.narration.state_facts import derive_state_facts


@pytest.fixture(scope="module")
def persona():
    return generate_cohort("COPD", 6, seed=42, as_of=date(2026, 8, 1))[0]


@pytest.fixture(scope="module")
def graph():
    return load_graph()


class TestTheDefinition:
    def test_first_person_alone_is_not_enough(self, persona, graph):
        """A first-person sentence carrying no state-supported term asserts
        nothing that only this persona could support."""
        distinctive = state_only_vocabulary(derive_state_facts(persona), graph, [])

        assert not is_circumstantial_v2("I think so, yes.", distinctive)

    def test_third_person_is_never_circumstantial(self, persona, graph):
        distinctive = state_only_vocabulary(derive_state_facts(persona), graph, [])

        assert not is_circumstantial_v2(
            "Public transport is unreliable in rural areas.", distinctive
        )

    def test_a_state_term_in_the_first_person_is(self, persona, graph):
        distinctive = state_only_vocabulary(derive_state_facts(persona), graph, [])
        assert "rural" in distinctive, "this persona's residence is the premise"

        assert is_circumstantial_v2("I live rurally, miles from anywhere.", distinctive)

    def test_a_term_the_graph_also_supports_leaves_the_vocabulary(self, persona, graph):
        """The subtraction IS the definition, so the same sentence must be able to
        flip verdict on nothing but which facts the case was offered."""
        state = derive_state_facts(persona)
        node = graph.resolve("transport")
        offered = [f.id for f in graph.out_facts(node.id)] if node else []

        without = state_only_vocabulary(state, graph, [])
        with_offered = state_only_vocabulary(state, graph, offered)

        assert with_offered <= without, "offering facts can only remove terms"


class TestNotWiredIn:
    def test_score_still_uses_v1(self):
        """v2 must not reach the metric before blind labels exist.

        It reads 0.6000 against v1's 0.5135 on the same cassette with zero model
        calls. Adopting it quietly would publish an instrument correction as a
        model improvement — score inflation whatever the intent.
        """
        import inspect

        from spp.narration import evaluation

        source = inspect.getsource(evaluation)
        assert "is_circumstantial_v2" not in source
        assert "from .circumstantial" not in source


class TestTheMetricSplit:
    def test_all_coverable_reproduces_the_single_number(self):
        """The split must be introducible without moving anything, or it is not a
        split — it is a second change riding along with the first."""
        from spp.narration.circumstantial import coverage_split

        pairs = [(True, True), (False, True), (True, True), (False, True)]

        assert coverage_split(pairs) == (0.5, 0.0)

    def test_uncoverable_segments_leave_the_coverage_denominator(self):
        """A segment no id can cover is schema evidence, not model evidence.

        Without the split, adding an unciteable symptom claim to the battery would
        LOWER state_coverage while the model behaved identically.
        """
        from spp.narration.circumstantial import coverage_split

        blended = [(True, True), (False, True), (False, True), (False, True)]
        with_gap = [(True, True), (False, True), (False, False), (False, False)]

        assert coverage_split(blended) == (0.25, 0.0)
        assert coverage_split(with_gap) == (0.5, 0.5)

    def test_no_circumstantial_segments_is_not_a_division(self):
        from spp.narration.circumstantial import coverage_split

        assert coverage_split([]) == (0.0, 0.0)
