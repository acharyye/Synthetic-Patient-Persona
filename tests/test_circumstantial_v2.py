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


class TestTheAdoptedInstrument:
    """v2.2 is the scoring instrument, adopted 2026-08-25.

    It stayed unwired through v2 and v2.1. What threw the switch is a sheet held
    out from EVERY instrument — 50 segments from the v1-era cassette, 49 scored —
    where v2.2 reads agreement 0.6939 / kappa +0.3336 against v2.1's 0.5510 /
    +0.0972 and v1's 0.5306 / +0.0242. v2.1 failed adoption on the canary
    criterion before it ever got here; v2.2 passes it by construction.
    """

    def test_score_uses_v22(self):
        import inspect

        from spp.narration import evaluation

        assert "is_circumstantial_v22" in inspect.getsource(evaluation)

    def test_v1_survives_and_does_not_score(self):
        """Every v1-era bundle number was produced by v1. A reader re-deriving one
        needs the function that made it, not its successor."""
        import inspect

        from spp.narration import evaluation

        assert callable(evaluation.is_circumstantial)
        assert "is_circumstantial(" not in inspect.getsource(evaluation.score)


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


class TestV21FrameRule:
    """The possession/experience frame, on the rater's own R1 exemplars.

    These are the boundary R1 states, not segments picked from v2's misses: "I
    take X" asserts own medication state, "for the X, I need a test" asserts a
    property of X, and "I have to go" is an obligation wearing possession's verb.
    """

    def test_possession_frames_the_term(self):
        from spp.narration.circumstantial import _framed_terms

        assert "salbutamol" in _framed_terms("I take salbutamol PRN and tiotropium.")

    def test_a_clinical_requirement_frames_nothing(self):
        from spp.narration.circumstantial import _framed_terms

        assert _framed_terms(
            "For the metformin, I need to do fasting blood tests."
        ) == set()

    def test_have_to_is_obligation_not_possession(self):
        """Without this the frame swallows the protocol vocabulary and v2.1
        collapses back toward v1's over-inclusion."""
        from spp.narration.circumstantial import _framed_terms

        assert _framed_terms("I have to go see the doctor every few weeks.") == set()
        assert "carer" in _framed_terms("I have a paid carer who helps.")

    def test_graph_overlap_no_longer_disqualifies_inside_a_frame(self):
        """The whole v2.1 amendment in one assertion."""
        from spp.narration.circumstantial import is_circumstantial_v2, is_circumstantial_v21

        state = frozenset({"metformin"})
        graph = frozenset({"metformin"})

        assert not is_circumstantial_v2("I take metformin.", state - graph)
        assert is_circumstantial_v21("I take metformin.", state, graph)
        assert not is_circumstantial_v21(
            "For the metformin, I need fasting blood tests.", state, graph
        )
