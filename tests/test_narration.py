"""Narration: prompt purity, cassettes, the citation gate, and memory.

Everything here runs offline. The only untested part of the pipeline is the words
a model would put between the citations — which is the correct boundary.
"""
import json
import re
from datetime import date
from pathlib import Path

import pytest

from spp.cohort import generate_cohort
from spp.foundation.events import EventLog, EventType, PersonaState
from spp.knowledge import load_graph, retrieve
from spp.narration import (
    Cassette,
    CassetteAdapter,
    CassetteMismatch,
    CassetteMiss,
    GroundingFailure,
    Take,
    build_prompt,
    check_citations,
    derive_state_facts,
    citation_skeleton,
    extract_citations,
    interview,
    is_factual,
    prior_turns,
    strip_citations,
)

AS_OF = date(2026, 8, 1)
GOLDEN_DIR = Path(__file__).parent / "golden" / "prompts"


@pytest.fixture(scope="module")
def graph():
    return load_graph()


@pytest.fixture(scope="module")
def dna():
    return generate_cohort("type 2 diabetes", 1, seed=42, as_of=AS_OF)[0]


class TestPromptIsPure:
    def test_building_is_deterministic(self, graph, dna):
        result = retrieve(graph, dna.condition, "How are you?", limit=6)
        first = build_prompt(dna, result, "How are you?")
        second = build_prompt(dna, result, "How are you?")
        assert first == second
        assert first.fingerprint == second.fingerprint

    def test_fingerprint_changes_with_content(self, graph, dna):
        result = retrieve(graph, dna.condition, "q", limit=6)
        assert (
            build_prompt(dna, result, "one").fingerprint
            != build_prompt(dna, result, "two").fingerprint
        )

    def test_prompt_is_frozen(self, graph, dna):
        prompt = build_prompt(dna, retrieve(graph, dna.condition, limit=4), "q")
        with pytest.raises(Exception):
            prompt.system = "tampered"

    def test_allowlist_travels_with_the_prompt(self, graph, dna):
        """The checker must verify against exactly what the model was shown."""
        result = retrieve(graph, dna.condition, "q", limit=7)
        prompt = build_prompt(dna, result, "q")
        state = derive_state_facts(dna)

        assert prompt.allowed_fact_ids == result.fact_ids | state.fact_ids
        assert prompt.allowed_state_ids == state.fact_ids
        # The two halves must not overlap, or "was this grounded in the persona
        # or in the graph?" stops being answerable by set membership.
        assert not (result.fact_ids & state.fact_ids)
        for fact_id in prompt.allowed_fact_ids:
            assert f"[{fact_id}]" in prompt.system

    def test_the_canary_lever_builds_the_v2_configuration(self, graph, dna):
        """`strip_state_ids` must remove the ids, not merely hide the block."""
        result = retrieve(graph, dna.condition, "q", limit=7)
        stripped = build_prompt(dna, result, "q", include_state_facts=False)

        assert stripped.allowed_state_ids == frozenset()
        assert stripped.allowed_fact_ids == result.fact_ids
        for state_id in derive_state_facts(dna).fact_ids:
            assert f"[{state_id}]" not in stripped.system

    def test_state_slice_reflects_the_simulation(self, dna):
        from spp.foundation.events import BurdenVector, JourneyStage
        from spp.narration import render_state

        state = PersonaState(
            persona_id=dna.patient_id, stage=JourneyStage.DROPPED,
            visits_completed=3, visits_missed=2, exit_reason="travel burden",
            barriers=["transport"], burden=BurdenVector(travel=0.9, time=0.1),
        )
        text = render_state(state)
        assert "dropped" in text
        assert "3" in text and "2" in text
        assert "travel burden" in text
        assert "travel" in text

    def test_no_state_is_stated_plainly(self):
        from spp.narration import render_state

        assert "Not currently in a study" in render_state(None)

    def test_prompt_carries_the_citation_rules(self, graph, dna):
        prompt = build_prompt(dna, retrieve(graph, dna.condition, limit=4), "q")
        assert "checked automatically" in prompt.system
        assert "say you do not know" in prompt.system
        # The prompt must describe the contract the schema actually enforces.
        assert "fact_ids" in prompt.system
        assert '"kind": "factual"' in prompt.system

    def test_the_instructions_do_not_ask_for_inline_markers(self, graph, dna):
        """v1 asked for `[F012]` inline AND supplied a fact_ids field.

        The model satisfied both, so 7 of 25 takes rendered their citations
        twice. Asking for a formatting convention the schema does not use is
        what produced that, so no marker example may reappear in the
        INSTRUCTIONS — including in a well-meant illustration of what not to do.

        Scoped to the instruction section on purpose. The GROUNDED FACTS block
        still labels each fact `[F012]`, because the model has to see the ids it
        is choosing between. That labelling is the remaining candidate source of
        imitation, and v2 deliberately does not change it: one variable at a
        time. If markers survive v2 anyway, the fact block is the finding.
        """
        prompt = build_prompt(dna, retrieve(graph, dna.condition, limit=4), "q")
        instructions = prompt.system.split("GROUNDED FACTS:")[0]
        assert not re.search(r"\[(F\d+|[PBJE]-[\w.\-]+)\]", instructions), (
            "instructions contain an inline citation marker example; the model "
            "will reproduce it in `text` alongside the structured fact_ids"
        )

    def test_golden_prompt(self, graph, dna):
        """Pins the prompt. Most narration bugs live here and cost nothing to catch."""
        result = retrieve(graph, dna.condition, "What side effects should I expect?",
                          limit=6, barriers=("transport",))
        prompt = build_prompt(dna, result, "What side effects should I expect?")
        path = GOLDEN_DIR / "interview_t2d.json"

        payload = {"system": prompt.system, "user": prompt.user,
                   "fingerprint": prompt.fingerprint,
                   "allowed": sorted(prompt.allowed_fact_ids),
                   "allowed_state": sorted(prompt.allowed_state_ids)}
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
            pytest.skip("golden prompt written")

        expected = json.loads(path.read_text(encoding="utf-8"))
        assert payload == expected, (
            "prompt changed. If intended, delete tests/golden/prompts/ and re-run, "
            "then review the diff — a prompt change invalidates cassettes."
        )


class TestCitationChecking:
    def test_extracts_single_and_grouped_citations(self):
        assert extract_citations("a [F001] b [F002, F003].") == ["F001", "F002", "F003"]
        assert extract_citations("no citations here") == []

    def test_unknown_ids_are_caught(self):
        check = check_citations("The medication causes nausea [F999].",
                                frozenset({"F001"}))
        assert not check.ok
        assert check.unknown_citations == ["F999"]

    def test_uncited_factual_sentence_is_caught(self):
        check = check_citations("The medication causes nausea.", frozenset({"F001"}))
        assert not check.ok
        assert check.uncited_sentences

    def test_feelings_need_no_citation(self):
        for sentence in (
            "I feel exhausted by all of it.",
            "Honestly, it is a lot.",
            "I don't know how I would manage.",
            "I'm worried about what comes next.",
        ):
            assert not is_factual(sentence), sentence
            assert check_citations(sentence, frozenset()).ok

    def test_a_well_formed_answer_passes(self):
        text = ("My treatment can cause nausea [F001]. I feel worn down by it. "
                "Getting to the clinic is hard for me [F002].")
        check = check_citations(text, frozenset({"F001", "F002"}))
        assert check.ok
        assert check.cited == ["F001", "F002"]

    def test_citations_are_stripped_for_display(self):
        text = "My treatment can cause nausea [F001]. I feel worn down."
        assert strip_citations(text) == "My treatment can cause nausea. I feel worn down."

    def test_questions_are_not_factual_claims(self):
        assert not is_factual("Would the clinic visits be in the evening?")


class TestCassettes:
    def test_replay_returns_the_recording(self, tmp_path):
        cassette = Cassette(name="c", backend="ollama", model="m")
        cassette.put(Take(fingerprint="abc", prompt_version=1, system="s",
                          user="u", response="recorded"))
        from spp.narration.cassette import save_cassette

        save_cassette(cassette, tmp_path)
        adapter = CassetteAdapter("c", mode="replay", directory=tmp_path,
                                  backend="ollama", model="m")
        assert adapter.generate("s", "u", "abc") == "recorded"

    def test_a_miss_in_replay_mode_is_a_hard_failure(self, tmp_path):
        adapter = CassetteAdapter("c", mode="replay", directory=tmp_path,
                                  backend="ollama", model="m")
        with pytest.raises(CassetteMiss, match="no recording"):
            adapter.generate("s", "u", "missing")

    def test_a_model_swap_invalidates_the_cassette(self, tmp_path):
        """The model is an assumption; swapping it must not silently replay."""
        from spp.narration.cassette import save_cassette

        save_cassette(Cassette(name="c", backend="ollama", model="old"), tmp_path)
        with pytest.raises(CassetteMismatch, match="model is an assumption"):
            CassetteAdapter("c", mode="replay", directory=tmp_path,
                            backend="ollama", model="new")

    def test_a_version_bump_invalidates_the_cassette(self, tmp_path):
        path = tmp_path / "c.json"
        path.write_text(json.dumps({
            "cassette_version": 99, "name": "c", "backend": "ollama",
            "model": "m", "takes": {},
        }))
        with pytest.raises(CassetteMismatch, match="Re-record"):
            CassetteAdapter("c", mode="replay", directory=tmp_path,
                            backend="ollama", model="m")


class TestInterviewOffline:
    def test_null_backend_emits_a_verifiable_citation_skeleton(self, dna, graph):
        """The whole pipeline is exercised offline; only the prose is missing."""
        turn = interview(dna, "What side effects should I expect?", graph=graph)

        assert turn.grounded is True
        assert turn.synthetic is True
        assert turn.cited_fact_ids
        assert turn.attempts == 1
        assert "[offline]" in turn.answer_with_citations

    def test_skeleton_citations_are_all_in_the_allowlist(self, dna, graph):
        result = retrieve(graph, dna.condition, "q", limit=16,
                          barriers=tuple(b.name for b in dna.barriers))
        text = citation_skeleton(dna, "q", result)
        assert check_citations(text, result.fact_ids).ok

    def test_an_ungrounded_condition_makes_the_persona_say_so(self, graph):
        from spp.schemas import PatientDNA

        stranger = PatientDNA(patient_id="x", age=50, sex="female",
                              condition="a condition nobody has")
        turn = interview(stranger, "How are you?", graph=graph)
        assert turn.retrieval_confidence == 0.0
        assert "don't know" in turn.answer

    def test_a_hallucinating_model_gets_exactly_one_retry(self, dna, graph):
        calls = []

        def generate(prompt, repair):
            calls.append(repair)
            return "The medication causes nausea [F999].", "fake", False

        turn = interview(dna, "q", graph=graph, generate=generate)
        assert turn.attempts == 2, "retry must be capped at one"
        assert calls[0] is None and calls[1] is not None
        assert "must not appear" in calls[1]
        assert turn.grounded is False

    def test_strict_mode_raises_instead_of_returning_ungrounded(self, dna, graph):
        def generate(prompt, repair):
            return "The medication causes nausea [F999].", "fake", False

        with pytest.raises(GroundingFailure, match="failed citation checks"):
            interview(dna, "q", graph=graph, generate=generate, strict=True)

    def test_a_repaired_answer_is_accepted(self, dna, graph):
        state = {"n": 0}

        def generate(prompt, repair):
            state["n"] += 1
            if state["n"] == 1:
                return "The medication causes nausea [F999].", "fake", False
            good = sorted(prompt.allowed_fact_ids)[0]
            return f"My treatment can cause problems [{good}].", "fake", False

        turn = interview(dna, "q", graph=graph, generate=generate)
        assert turn.grounded is True
        assert turn.attempts == 2


class TestLongitudinalMemory:
    def test_interviews_append_to_the_event_log(self, dna, graph):
        log = EventLog(persona_id=dna.patient_id)
        interview(dna, "First question?", graph=graph, log=log)
        interview(dna, "Second question?", graph=graph, log=log)

        turns = log.of_type(EventType.INTERVIEWED)
        assert len(turns) == 2
        assert turns[0].payload["question"] == "First question?"
        assert turns[0].payload["cited"]

    def test_memory_is_a_read_over_the_log_not_a_second_store(self, dna, graph):
        log = EventLog(persona_id=dna.patient_id)
        interview(dna, "What worries you?", graph=graph, log=log)

        recalled = prior_turns(log)
        assert len(recalled) == 1
        assert recalled[0]["question"] == "What worries you?"

    def test_prior_answers_appear_in_the_next_prompt(self, dna, graph):
        log = EventLog(persona_id=dna.patient_id)
        interview(dna, "What worries you most?", graph=graph, log=log)

        result = retrieve(graph, dna.condition, "And now?", limit=6)
        prompt = build_prompt(dna, result, "And now?", memory=prior_turns(log))
        assert "ALREADY TOLD THIS TEAM" in prompt.system
        assert "What worries you most?" in prompt.system

    def test_memory_is_bounded(self, dna, graph):
        log = EventLog(persona_id=dna.patient_id)
        for i in range(6):
            interview(dna, f"Question {i}?", graph=graph, log=log)
        assert len(prior_turns(log, limit=3)) == 3

    def test_no_memory_means_no_memory_section(self, dna, graph):
        prompt = build_prompt(dna, retrieve(graph, dna.condition, limit=4), "q")
        assert "ALREADY TOLD" not in prompt.system

    def test_interview_events_survive_the_parquet_round_trip(self, dna, graph, tmp_path):
        """Longitudinal memory inherits replay purity for free."""
        from spp.foundation.store import read_logs, write_logs

        log = EventLog(persona_id=dna.patient_id)
        interview(dna, "Tell me about travel.", graph=graph, log=log)

        restored = read_logs(write_logs({dna.patient_id: log}, tmp_path / "l.parquet"))
        assert prior_turns(restored[dna.patient_id]) == prior_turns(log)


class TestPanelModerator:
    """Code decides who speaks; the model only fills in content."""

    @pytest.fixture(scope="class")
    def panel(self):
        return generate_cohort("type 2 diabetes", 6, seed=42, as_of=AS_OF)

    def test_speaking_order_is_deterministic_and_barrier_weighted(self, panel):
        from spp.narration import speaking_order

        first = [p.patient_id for p in speaking_order(panel)]
        second = [p.patient_id for p in speaking_order(list(reversed(panel)))]
        assert first == second, "order must not depend on input order"

        loads = [p.barrier_load for p in speaking_order(panel)]
        assert loads == sorted(loads, reverse=True)

    def test_a_panel_is_reproducible(self, panel, graph):
        from spp.narration import run_panel

        first = run_panel(panel, "Could you attend twice a month?", graph=graph)
        second = run_panel(panel, "Could you attend twice a month?", graph=graph)
        assert first.model_dump() == second.model_dump()

    def test_probes_fire_on_shared_citations_not_on_prose(self, graph):
        from spp.narration import should_probe
        from spp.narration.panel import PanelStatement

        shared = [
            PanelStatement(order=0, patient_id="a", prompt="q", text="t",
                           cited_fact_ids=["F001", "F002"]),
            PanelStatement(order=1, patient_id="b", prompt="q", text="t",
                           cited_fact_ids=["F002"]),
        ]
        assert should_probe(shared) == "F002"

        unshared = [
            PanelStatement(order=0, patient_id="a", prompt="q", text="t",
                           cited_fact_ids=["F001"]),
            PanelStatement(order=1, patient_id="b", prompt="q", text="t",
                           cited_fact_ids=["F003"]),
        ]
        assert should_probe(unshared) is None

    def test_the_same_persona_cited_twice_is_not_a_shared_concern(self):
        from spp.narration import should_probe
        from spp.narration.panel import PanelStatement

        same_person = [
            PanelStatement(order=0, patient_id="a", prompt="q", text="t",
                           cited_fact_ids=["F001"]),
            PanelStatement(order=1, patient_id="a", prompt="q", text="t",
                           cited_fact_ids=["F001"]),
        ]
        assert should_probe(same_person) is None

    def test_probes_are_bounded(self, panel, graph):
        from spp.narration import run_panel

        transcript = run_panel(panel, "Could you attend twice a month?",
                               graph=graph, probe_after=1, max_probes=2)
        assert len(transcript.probes) <= 2

    def test_every_statement_is_grounded_offline(self, panel, graph):
        from spp.narration import run_panel

        transcript = run_panel(panel, "Could you attend twice a month?", graph=graph)
        assert transcript.ungrounded() == []
        assert all(s.cited_fact_ids for s in transcript.statements)


class TestMechanicalThemes:
    def test_themes_group_by_cited_fact_not_by_wording(self, graph):
        from spp.narration import extract_themes
        from spp.narration.panel import PanelStatement

        statements = [
            PanelStatement(order=0, patient_id="a", prompt="q",
                           text="totally different words", cited_fact_ids=["F011"]),
            PanelStatement(order=1, patient_id="b", prompt="q",
                           text="phrased another way entirely", cited_fact_ids=["F011"]),
            PanelStatement(order=2, patient_id="c", prompt="q",
                           text="unrelated", cited_fact_ids=["F019"]),
        ]
        themes = extract_themes(statements, graph)

        assert len(themes) == 1, "only the shared fact forms a theme"
        assert themes[0].fact_ids == ["F011"]
        assert themes[0].patient_ids == ["a", "b"]
        assert themes[0].support == 2

    def test_a_single_voice_is_not_a_theme(self, graph):
        from spp.narration import extract_themes
        from spp.narration.panel import PanelStatement

        alone = [PanelStatement(order=0, patient_id="a", prompt="q", text="t",
                                cited_fact_ids=["F011"])]
        assert extract_themes(alone, graph) == []

    def test_theme_headline_is_a_count_not_a_judgement(self, graph):
        from spp.narration import extract_themes
        from spp.narration.panel import PanelStatement

        statements = [
            PanelStatement(order=i, patient_id=pid, prompt="q", text="t",
                           cited_fact_ids=["F011"])
            for i, pid in enumerate(["a", "b", "c"])
        ]
        theme = extract_themes(statements, graph)[0]
        assert theme.headline(6).startswith("3 of 6 personas raised")

    def test_theme_labels_come_from_the_graph(self, graph):
        from spp.narration import extract_themes
        from spp.narration.panel import PanelStatement

        statements = [
            PanelStatement(order=i, patient_id=pid, prompt="q", text="t",
                           cited_fact_ids=["F011"])
            for i, pid in enumerate(["a", "b"])
        ]
        theme = extract_themes(statements, graph)[0]
        assert theme.label
        assert theme.label != "F011", "label must be human-readable, not an id"

    def test_themes_are_ordered_by_support(self, graph):
        from spp.narration import extract_themes
        from spp.narration.panel import PanelStatement

        statements = [
            PanelStatement(order=0, patient_id="a", prompt="q", text="t",
                           cited_fact_ids=["F011", "F019"]),
            PanelStatement(order=1, patient_id="b", prompt="q", text="t",
                           cited_fact_ids=["F011", "F019"]),
            PanelStatement(order=2, patient_id="c", prompt="q", text="t",
                           cited_fact_ids=["F011"]),
        ]
        themes = extract_themes(statements, graph)
        assert [t.support for t in themes] == sorted(
            (t.support for t in themes), reverse=True
        )


class TestPanelOrderSensitivity:
    """Speaking order is a named modelling choice, so check what it costs."""

    def test_the_order_strategy_is_registered(self):
        from spp.assumptions import PANEL_SPEAKING_ORDER

        assert PANEL_SPEAKING_ORDER.params["strategy"] == "barrier_load_desc"
        assert "NOT a neutral default" in PANEL_SPEAKING_ORDER.source

    def test_theme_sets_survive_a_permuted_speaking_order(self, graph):
        """Later speakers see the transcript, so the most burdened persona anchors
        every session. Emphasis may shift; the fact-ID groups must not, or a
        design review would be leaning on an artifact of turn order."""
        from spp.narration import run_panel

        panel = generate_cohort("type 2 diabetes", 6, seed=42, as_of=AS_OF)
        topic = "Could you attend the clinic twice a month?"

        baseline = run_panel(panel, topic, graph=graph)
        permuted = run_panel(list(reversed(panel)), topic, graph=graph)

        def theme_facts(transcript):
            return {tuple(sorted(theme.fact_ids)) for theme in transcript.themes}

        assert theme_facts(baseline) == theme_facts(permuted)

    def test_theme_support_counts_are_order_stable(self, graph):
        from spp.narration import run_panel

        panel = generate_cohort("COPD", 6, seed=7, as_of=AS_OF)
        topic = "Would weekday appointments be difficult?"

        baseline = run_panel(panel, topic, graph=graph)
        permuted = run_panel(sorted(panel, key=lambda p: p.patient_id), topic, graph=graph)

        def support(transcript):
            return {t.fact_ids[0]: t.support for t in transcript.themes}

        assert support(baseline) == support(permuted)
