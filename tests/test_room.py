"""Interview Room: evidence badges, memory semantics, citation click-through."""
import json
from datetime import date

import pytest
from fastapi.testclient import TestClient

from spp.api.main import app
from spp.cohort import generate_cohort
from spp.narration.cassette import Cassette, Take
from spp.narration.prompt import PROMPT_VERSION
from spp.narration.evaluation import load_battery
from spp.narration.room import (
    MEMORY_SEMANTICS,
    REPLAY_RETRIEVAL_LIMIT,
    available_questions,
    ask,
    free_text_state,
)

client = TestClient(app)
AS_OF = date(2026, 8, 1)


@pytest.fixture(scope="module")
def dna():
    return generate_cohort("type 2 diabetes", 6, seed=42, as_of=AS_OF)[0]


def recorded_cassette(dna, questions, graph=None) -> Cassette:
    """Build a cassette the way the recorder would — memory-free prompts."""
    from spp.knowledge import load_graph, retrieve
    from spp.narration.prompt import build_prompt

    graph = graph or load_graph()
    cassette = Cassette(name="t", backend="ollama", model="qwen2.5:7b-instruct",
                        prompt_version=PROMPT_VERSION)
    for question in questions:
        result = retrieve(graph, dna.condition, question,
                          limit=REPLAY_RETRIEVAL_LIMIT,
                          barriers=tuple(b.name for b in dna.barriers))
        prompt = build_prompt(dna, result, question)
        first = sorted(prompt.allowed_fact_ids)[:1]
        cassette.put(Take(
            fingerprint=prompt.fingerprint, prompt_version=PROMPT_VERSION,
            system=prompt.system, user=prompt.user,
            model="qwen2.5:7b-instruct", model_digest="sha256:abc123def456",
            response=json.dumps({"segments": [
                {"text": "That is part of it", "kind": "factual", "fact_ids": first},
                {"text": "and it wears me down", "kind": "feeling", "fact_ids": []},
            ]}),
        ))
    return cassette


class TestMemorySemantics:
    def test_semantics_are_declared_not_implied(self):
        assert MEMORY_SEMANTICS == "independent"

    def test_replay_is_order_independent(self, dna):
        """THE test. Battery takes were recorded memory-free, so replaying them
        in any order must give identical takes. If the room fed take N a
        transcript of 1..N-1, the prompt hash would diverge and every follow-up
        would miss."""
        questions = [c["question"] for c in load_battery()
                     if c["condition"] == dna.condition][:4]
        assert len(questions) >= 2
        cassette = recorded_cassette(dna, questions)

        forward = [ask(dna, q, cassette=cassette).model_dump() for q in questions]
        reverse = [ask(dna, q, cassette=cassette).model_dump()
                   for q in reversed(questions)]

        assert forward == list(reversed(reverse))

    def test_every_replayed_question_hits_its_recording(self, dna):
        """A miss here means the room's prompt drifted from the recorder's."""
        questions = [c["question"] for c in load_battery()
                     if c["condition"] == dna.condition][:4]
        cassette = recorded_cassette(dna, questions)

        for question in questions:
            answer = ask(dna, question, cassette=cassette)
            assert answer.evidence.kind == "recorded_take", question

    def test_asking_twice_gives_the_same_answer(self, dna):
        questions = [c["question"] for c in load_battery()
                     if c["condition"] == dna.condition][:1]
        cassette = recorded_cassette(dna, questions)
        first = ask(dna, questions[0], cassette=cassette)
        second = ask(dna, questions[0], cassette=cassette)
        assert first == second


class TestEvidenceIsNamed:
    def test_a_recorded_take_names_its_model_and_digest(self, dna):
        questions = [c["question"] for c in load_battery()
                     if c["condition"] == dna.condition][:1]
        answer = ask(dna, questions[0], cassette=recorded_cassette(dna, questions))

        assert answer.evidence.kind == "recorded_take"
        assert "qwen2.5:7b-instruct" in answer.evidence.label()
        assert "sha256" in answer.evidence.label()
        assert f"prompt v{PROMPT_VERSION}" in answer.evidence.label()

    def test_an_unrecorded_question_falls_to_the_skeleton_honestly(self, dna):
        """Never fabricated prose, never a generic 'loading'."""
        answer = ask(dna, "A question nobody recorded?", cassette=None)
        assert answer.evidence.kind == "citation_skeleton"
        assert answer.evidence.is_generated is False
        assert "no model" in answer.evidence.label()
        assert "[offline]" in answer.answer or answer.cited_fact_ids

    def test_skeleton_answers_still_pass_the_citation_gate(self, dna):
        answer = ask(dna, "What side effects should I expect from treatment?")
        assert answer.grounded is True
        assert set(answer.cited_fact_ids) <= set(answer.offered_fact_ids)


class TestPickerNotChat:
    def test_free_text_is_disabled_offline_with_a_reason(self):
        state = free_text_state(cassette=None, live=False)
        assert state["enabled"] is False
        assert "no recorded take" in state["reason"]
        assert "record_narration" in state["reason"]

    def test_free_text_unlocks_when_live(self):
        assert free_text_state(cassette=None, live=True)["enabled"] is True

    def test_the_recorded_questions_are_the_offered_set(self, dna):
        questions = [c["question"] for c in load_battery()
                     if c["condition"] == dna.condition]
        offered = available_questions(dna, recorded_cassette(dna, questions),
                                      load_battery())
        recorded = [q for q in offered if q.evidence.kind == "recorded_take"]
        assert len(recorded) == len(questions)

    def test_each_offered_question_carries_its_badge(self, dna):
        offered = available_questions(dna, None, load_battery())
        assert offered
        assert all(q.evidence.kind == "citation_skeleton" for q in offered)

    def test_the_picker_order_is_stable(self, dna):
        first = [q.question for q in available_questions(dna, None, load_battery())]
        second = [q.question for q in available_questions(dna, None, load_battery())]
        assert first == second == sorted(first)


class TestCitationClickThrough:
    def test_a_fact_expands_to_its_provenance(self, dna):
        answer = ask(dna, "Could you get to the site twice a month?")
        fact_id = answer.cited_fact_ids[0]

        payload = client.post(f"/room/fact/{fact_id}", json={
            "condition": dna.condition, "seed": 42, "n": 6, "persona_index": 0,
        }).json()

        assert payload["id"] == fact_id
        assert payload["source"]
        assert payload["confidence"]
        assert "quotable" in payload
        assert payload["subject"]["kind"] and payload["object"]["kind"]

    def test_a_barrier_fact_links_back_to_the_simulation(self):
        """The loop closing: spoken fact -> provenance -> the persona's DERIVED
        barrier -> the profile field it came from."""
        from spp.knowledge import fact_detail, load_graph, retrieve

        graph = load_graph()
        cohort = generate_cohort("type 2 diabetes", 6, seed=42, as_of=AS_OF)
        linked = None
        for persona in cohort:
            names = {b.name for b in persona.barriers}
            result = retrieve(graph, persona.condition, "Could you attend?",
                              limit=40, barriers=tuple(names))
            for fact in result.facts:
                if (fact.object.partition(":")[2] in names
                        or fact.subject.partition(":")[2] in names):
                    linked = fact_detail(graph, fact.id, persona=persona)
                    break
            if linked and linked.simulation_link:
                break

        assert linked is not None and linked.simulation_link is not None
        link = linked.simulation_link
        assert link["kind"] == "derived_barrier"
        assert link["origin"], "must name the profile field it was derived from"
        assert 0 <= link["severity"] <= 1

    def test_no_link_when_the_persona_lacks_that_barrier(self, dna):
        """The join must not fabricate a connection that isn't there."""
        from spp.knowledge import fact_detail, load_graph

        graph = load_graph()
        absent = next(
            name for name in ("transport", "mobility", "cost")
            if name not in {b.name for b in dna.barriers}
        )
        node = graph.resolve(absent, kind="Barrier")
        fact = next(f for f in graph._facts.values() if f.object == node.id)

        detail = fact_detail(graph, fact.id, persona=dna)
        assert detail.simulation_link is None

    def test_an_unknown_fact_is_a_404(self):
        response = client.post("/room/fact/F99999", json={
            "condition": "COPD", "seed": 42, "n": 6, "persona_index": 0})
        assert response.status_code == 404


class TestRoomEndpoints:
    def test_session_reports_evidence_mode_and_semantics(self):
        payload = client.post("/room/session", json={
            "condition": "type 2 diabetes", "seed": 42, "n": 6, "persona_index": 0,
        }).json()

        assert payload["evidence_mode"] in {"cassette", "skeleton"}
        assert payload["memory_semantics"] == "independent"
        assert payload["questions"]
        assert payload["free_text"]["enabled"] is False
        assert payload["persona"]["barriers"]

    def test_ask_requires_a_question(self):
        response = client.post("/room/ask", json={
            "condition": "COPD", "seed": 42, "n": 6, "persona_index": 0})
        assert response.status_code == 400

    def test_persona_index_is_bounds_checked(self):
        response = client.post("/room/session", json={
            "condition": "COPD", "seed": 42, "n": 3, "persona_index": 99})
        assert response.status_code == 400


class TestStaleRecordingsAreNamed:
    """Absence and invalidation are different truths; the badge must say which.

    `prompt_version` is inside the prompt fingerprint, so a take recorded under
    an older prompt is UNREACHABLE rather than wrong — correctness was never at
    risk, and that is the same "make it unrepresentable" move as the fact-id
    enum. What was at risk is honesty: a fingerprint miss looks identical
    whether the recording is stale, the question is novel, or retrieval moved,
    so the room reported "no recorded take" for a cassette that was really
    invalidated by a prompt bump.

    The stamp check therefore has to run BEFORE the key lookup. Both states are
    asserted here because the second one — plain absence — is what existed
    before and silently absorbed the first.
    """

    def test_a_stale_cassette_degrades_to_skeleton_naming_the_reason(self, dna):
        questions = ["What side effects should I expect?"]
        cassette = recorded_cassette(dna, questions)
        stale = cassette.model_copy(update={"prompt_version": PROMPT_VERSION - 1})

        answer = ask(dna, questions[0], cassette=stale)

        assert answer.evidence.kind == "citation_skeleton"
        assert f"prompt v{PROMPT_VERSION - 1}" in answer.evidence.detail
        assert "invalidated" in answer.evidence.detail
        assert "invalidated" in answer.evidence.label()
        # Degrade, never crash: the recorder refuses to WRITE incompatible
        # evidence; the room's job is to DISPLAY honestly what exists.
        assert answer.answer

    def test_a_novel_question_says_absence_not_invalidation(self, dna):
        """The other honest state, and the one that used to absorb both."""
        cassette = recorded_cassette(dna, ["What side effects should I expect?"])

        answer = ask(dna, "A question nobody ever recorded?", cassette=cassette)

        assert answer.evidence.kind == "citation_skeleton"
        assert answer.evidence.detail == "no recorded take can answer this question"
        assert "invalidated" not in answer.evidence.detail

    def test_a_current_cassette_still_replays(self, dna):
        """The check must not reject what it should accept."""
        questions = ["What side effects should I expect?"]
        answer = ask(dna, questions[0], cassette=recorded_cassette(dna, questions))
        assert answer.evidence.kind == "recorded_take"
