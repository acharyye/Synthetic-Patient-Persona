"""The P/B/J/E namespaces: what a persona may cite about itself.

The claim under test in v3 is that a persona could not label its own
circumstances `factual` because it had no id for them. These tests do not
adjudicate that claim — the battery does. They pin the properties the claim
depends on: the ids are stable identity, they cannot collide with graph ids, the
surface is declared rather than emergent, and `E-` stays shut.
"""
from datetime import date

import pytest

from spp.cohort import generate_cohort
from spp.knowledge import load_graph, retrieve
from spp.narration import build_prompt
from spp.narration.state_facts import (
    NAMESPACE_MEANING,
    PROFILE_FIELDS,
    RESERVED_NAMESPACES,
    derive_state_facts,
    is_state_id,
    namespace_of,
    state_detail,
)
from spp.schemas import PatientDNA

AS_OF = date(2026, 8, 1)


@pytest.fixture(scope="module")
def graph():
    return load_graph()


@pytest.fixture(scope="module")
def cohort():
    people = []
    for condition in ("type 2 diabetes", "COPD", "breast cancer"):
        people.extend(generate_cohort(condition, 6, seed=42, as_of=AS_OF))
    return people


@pytest.fixture(scope="module")
def dna(cohort):
    return cohort[0]


class TestDerivationIsPure:
    def test_the_same_persona_derives_the_same_ids(self, dna):
        assert derive_state_facts(dna) == derive_state_facts(dna)

    def test_it_reads_nothing_but_the_persona(self, dna):
        """No clock, no RNG, no I/O — the same discipline as `build_prompt`."""
        first = derive_state_facts(dna.model_copy(deep=True))
        assert first.fact_ids == derive_state_facts(dna).fact_ids

    def test_every_persona_has_something_to_say_about_itself(self, cohort):
        for person in cohort:
            citations = derive_state_facts(person)
            assert citations.facts, f"{person.patient_id} derived no state ids"
            assert citations.persona_id == person.patient_id


class TestTheReservedNamespace:
    """`E-` is declared and deliberately empty. This is the pin.

    Folding journey milestones into `E-` would cost nothing today and would make
    every v3 recording ambiguous the day simulated personas enter the battery
    carrying real event logs — two provenance types under one prefix, in an
    artifact nobody can go back and disambiguate. So the emptiness is asserted
    rather than remembered.
    """

    def test_e_is_declared(self):
        assert "E" in NAMESPACE_MEANING
        assert RESERVED_NAMESPACES == frozenset({"E"})

    def test_no_persona_emits_an_event_log_id(self, cohort):
        for person in cohort:
            for fact in derive_state_facts(person).facts:
                assert fact.namespace != "E", (
                    "an E- id was emitted. E means simulation event-log entries "
                    "and nothing else; if event-log citation is being built, that "
                    "is a deliberate change to the pre-registered v3 shape and "
                    "belongs in its own commit."
                )

    def test_the_gap_is_a_coverage_finding_not_a_stretched_id(self, dna):
        """A persona has no id for "I missed visit 3" and must not fake one.

        The consequence is recorded in tests/eval/v3_expected_shape.json rather
        than repaired by widening J- to cover visits.
        """
        journey_ids = {
            f.id for f in derive_state_facts(dna).facts if f.namespace == "J"
        }
        assert not any("visit" in fact_id for fact_id in journey_ids)


class TestIdsAreStableIdentity:
    def test_ids_are_names_not_positions(self, dna):
        """Dropping one comorbidity must not renumber the others.

        Same rule as visit ids in the simulation: an id derived from a list index
        moves when anything ahead of it moves, and every artifact keyed on it
        silently points somewhere else.
        """
        before = derive_state_facts(dna).fact_ids
        if len(dna.comorbidities) < 2:
            pytest.skip("persona has too few comorbidities to test the shift")

        shortened = dna.model_copy(update={"comorbidities": dna.comorbidities[1:]})
        after = derive_state_facts(shortened).fact_ids

        dropped = before - after
        assert len(dropped) == 1, f"dropping one field moved {len(dropped)} ids"
        assert after < before

    def test_ids_are_unique_within_a_persona(self, cohort):
        for person in cohort:
            facts = derive_state_facts(person).facts
            ids = [f.id for f in facts]
            assert len(ids) == len(set(ids)), f"duplicate state id in {person.patient_id}"

    def test_a_repeated_journey_stage_gets_a_stable_suffix(self, dna):
        doubled = dna.model_copy(update={"journey": list(dna.journey) + list(dna.journey)})
        ids = [f.id for f in derive_state_facts(doubled).facts if f.namespace == "J"]
        assert len(ids) == len(set(ids))
        assert any(fact_id.endswith("-2") for fact_id in ids)

    def test_ids_are_url_safe(self, cohort):
        """They become path segments: /room/fact/{id}."""
        import string

        allowed = set(string.ascii_letters + string.digits + "-_.")
        for person in cohort:
            for fact in derive_state_facts(person).facts:
                assert set(fact.id) <= allowed, fact.id


class TestNamespacesDoNotCollide:
    def test_state_ids_are_recognised_and_graph_ids_are_not(self):
        assert is_state_id("P-age") and namespace_of("P-age") == "P"
        assert is_state_id("B-transport") and namespace_of("B-transport") == "B"
        assert is_state_id("J-diagnosis") and namespace_of("J-diagnosis") == "J"
        assert not is_state_id("F057")
        assert namespace_of("F057") is None
        assert not is_state_id("")
        assert namespace_of("X-something") is None

    def test_no_persona_collides_with_the_graph(self, cohort, graph):
        """The two halves of the allowlist must stay separable by membership."""
        for person in cohort:
            result = retrieve(graph, person.condition, "How do you cope?", limit=24)
            state = derive_state_facts(person)
            assert not (result.fact_ids & state.fact_ids)


class TestTheCitableSurfaceIsDeclared:
    def test_every_profile_id_names_a_declared_field(self, cohort):
        """`PROFILE_FIELDS` is the surface, the way TRAVERSAL_PLAN is the walk.

        What a persona may cite is a design decision. If a new field starts
        appearing here without being declared, that is the surface growing
        silently.
        """
        for person in cohort:
            for fact in derive_state_facts(person).facts:
                if fact.namespace != "P":
                    continue
                field = fact.id[2:].split(".")[0]
                assert field in PROFILE_FIELDS, f"{fact.id} is not declared"

    def test_biomarkers_are_outside_the_surface(self, dna):
        """A persona quoting a lab value is making a clinical claim.

        Deliberately excluded. A battery question that needs one is a coverage
        finding to log, not a reason to widen this quietly.
        """
        assert "biomarkers" not in PROFILE_FIELDS
        assert not any(
            f.id.startswith("P-biomarkers") for f in derive_state_facts(dna).facts
        )


class TestBarrierIdsKeepTheJoin:
    def test_a_barrier_id_is_the_barrier_name(self, cohort):
        """`traits.barrier_severity` derives the name, the graph's Barrier node
        is keyed on it, and `B-` must not rewrite it — that shared identity IS
        the join between a simulated barrier and a citable fact."""
        for person in cohort:
            ids = {f.id for f in derive_state_facts(person).facts if f.namespace == "B"}
            for barrier in person.barriers:
                assert f"B-{barrier.name}" in ids

    def test_a_barrier_id_expands_back_to_the_profile_field(self, dna):
        if not dna.barriers:
            pytest.skip("persona derived no barriers")
        barrier = dna.barriers[0]
        detail = state_detail(dna, f"B-{barrier.name}")

        assert detail is not None
        assert detail.simulation_link["barrier"] == barrier.name
        assert detail.simulation_link["origin"] == barrier.origin

    def test_severity_is_worded_not_quoted(self, dna):
        """A persona saying "transport is a 62% problem" is the register failure
        the narration layer exists to prevent."""
        for fact in derive_state_facts(dna).facts:
            if fact.namespace == "B":
                assert "%" not in fact.text


class TestClickThrough:
    def test_every_derived_id_resolves(self, cohort):
        for person in cohort:
            for fact in derive_state_facts(person).facts:
                detail = state_detail(person, fact.id)
                assert detail is not None, fact.id
                assert detail.persona_id == person.patient_id
                assert detail.origin
                assert detail.namespace_meaning

    def test_an_id_this_persona_lacks_does_not_resolve(self, dna):
        assert state_detail(dna, "P-not_a_field") is None
        assert state_detail(dna, "F057") is None

    def test_one_personas_id_does_not_resolve_against_another(self, cohort):
        """State ids are per-persona; nothing here may leak across them."""
        first, second = cohort[0], cohort[-1]
        only_first = derive_state_facts(first).fact_ids - derive_state_facts(second).fact_ids
        if not only_first:
            pytest.skip("these two personas derived the same surface")
        assert state_detail(second, sorted(only_first)[0]) is None


class TestThePromptOffersThem:
    def test_every_offered_id_appears_in_the_prompt(self, dna, graph):
        result = retrieve(graph, dna.condition, "How do you cope?", limit=8)
        prompt = build_prompt(dna, result, "How do you cope?")

        state = derive_state_facts(dna)
        assert prompt.allowed_state_ids == state.fact_ids
        for fact in state.facts:
            assert f"[{fact.id}]" in prompt.system

    def test_the_rules_say_circumstance_is_factual(self, dna, graph):
        """The prompt has to say it, or the ids exist and go unused."""
        prompt = build_prompt(dna, retrieve(graph, dna.condition, limit=4), "q")
        instructions = prompt.system.split("GROUNDED FACTS:")[0]
        assert "ABOUT YOU" in instructions
        assert "Being personal does not make it a feeling." in instructions

    def test_a_persona_with_nothing_on_file_says_so(self, graph):
        """No silent empty block: an absent surface is stated."""
        bare = PatientDNA(patient_id="bare", age=40, sex="other", condition="x")
        prompt = build_prompt(bare, retrieve(graph, "x", limit=4), "q")
        # Even a bare persona has age, sex and condition, so the block is never
        # actually empty — but the empty rendering must still be honest.
        from spp.narration.state_facts import StateCitations

        assert "NOTHING ON FILE" in StateCitations(persona_id="bare").block()
        assert "[P-age]" in prompt.system
