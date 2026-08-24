"""The compliance eval, its canary, and the recorder gate.

Everything here runs offline against a scripted "model" — a stand-in that lets
the instrument itself be tested. The point is not to score a real model (no model
has been run yet); it is to establish that when one is run, the number produced
means something.
"""
import json
from datetime import date

import pytest

from spp.cohort import generate_cohort
from spp.knowledge import load_graph
from spp.narration.cassette import Cassette, CassetteMismatch, GatedRecorder
from spp.narration.evaluation import DEGRADATIONS, load_battery, run_canary, score
from spp.narration.structured import (
    StructuredAnswer,
    answer_schema,
    check_structured,
    parse_structured,
)

AS_OF = date(2026, 8, 1)


@pytest.fixture(scope="module")
def graph():
    return load_graph()


@pytest.fixture(scope="module")
def cohort():
    people = []
    for condition in ("type 2 diabetes", "COPD", "heart failure",
                      "breast cancer", "rheumatoid arthritis"):
        people.extend(generate_cohort(condition, 6, seed=42, as_of=AS_OF))
    return people


def compliant_model(prompt, schema, repair):
    """A stand-in that behaves. Cites the first offered fact per factual segment."""
    ids = sorted(prompt.allowed_fact_ids)
    if not ids:
        return json.dumps({"segments": [
            {"text": "I don't know enough to answer that.", "kind": "feeling",
             "fact_ids": []}
        ]})
    return json.dumps({"segments": [
        {"text": "That is part of what I live with", "kind": "factual",
         "fact_ids": ids[:1]},
        {"text": "and honestly it wears me down", "kind": "feeling", "fact_ids": []},
        {"text": "Getting to appointments is its own problem", "kind": "factual",
         "fact_ids": ids[1:2] or ids[:1]},
    ]})


def relevant_model(prompt, schema, repair):
    """Behaves AND cites the top-ranked facts — the relevance ceiling.

    Its third segment is CIRCUMSTANTIAL, and it reproduces the v2 behaviour the
    state-citation hypothesis is about: offered a state id it makes the claim
    `factual` and cites it; offered none it downgrades the same sentence to
    `feeling`, because there is no id under which it could be a claim.

    That is a *simulation of the hypothesis*, not evidence for it. It exists so
    the `strip_state_ids` lever has something to move — an instrument that cannot
    fail on an axis is not measuring that axis. Whether a real model behaves this
    way is what the v3 battery is for.
    """
    ids = sorted(prompt.allowed_fact_ids)
    if not ids:
        return compliant_model(prompt, schema, repair)
    # The prompt lists facts in rank order; take the first two as printed.
    ordered = [
        line.split("]")[0].lstrip("[")
        for line in prompt.system.splitlines()
        if line.startswith("[F")
    ][:2]
    state_ids = sorted(prompt.allowed_state_ids)
    circumstantial = (
        {"text": "I cannot always get myself to the clinic", "kind": "factual",
         "fact_ids": state_ids[:1]}
        if state_ids else
        {"text": "I cannot always get myself to the clinic", "kind": "feeling",
         "fact_ids": []}
    )
    return json.dumps({"segments": [
        {"text": "That is part of what I live with", "kind": "factual",
         "fact_ids": ordered[:1] or ids[:1]},
        {"text": "and it wears me down", "kind": "feeling", "fact_ids": []},
        {"text": "There is a practical side too", "kind": "factual",
         "fact_ids": ordered[1:2] or ids[:1]},
        circumstantial,
    ]})


def hallucinating_model(prompt, schema, repair):
    """Ignores the enum — what an unconstrained backend might do."""
    return json.dumps({"segments": [
        {"text": "My treatment causes problems", "kind": "factual",
         "fact_ids": ["F999"]},
    ]})


def lazy_model(prompt, schema, repair):
    """Asserts without citing."""
    return json.dumps({"segments": [
        {"text": "The medication causes side effects", "kind": "factual",
         "fact_ids": []},
    ]})


class TestStructuredContract:
    def test_fact_ids_are_constrained_to_retrieved_ids(self):
        """The decode-time guarantee: a fabricated id is ungrammatical."""
        schema = answer_schema(frozenset({"F001", "F002"}))
        field = schema["properties"]["segments"]["items"]["properties"]["fact_ids"]
        assert field["items"]["enum"] == ["F001", "F002"]

    def test_empty_context_forbids_any_citation(self):
        schema = answer_schema(frozenset())
        field = schema["properties"]["segments"]["items"]["properties"]["fact_ids"]
        assert field["maxItems"] == 0

    def test_rendering_is_code_not_model_output(self):
        answer = StructuredAnswer.model_validate({"segments": [
            {"text": "It causes nausea", "kind": "factual", "fact_ids": ["F001"]},
            {"text": "I hate it", "kind": "feeling", "fact_ids": []},
        ]})
        assert answer.render() == "It causes nausea [F001] I hate it"
        assert answer.render(with_citations=False) == "It causes nausea I hate it"

    def test_gate_catches_out_of_context_citations(self):
        answer = parse_structured(hallucinating_model(None, None, None))
        assert not check_structured(answer, frozenset({"F001"})).ok

    def test_gate_catches_uncited_factual_segments(self):
        answer = parse_structured(lazy_model(None, None, None))
        check = check_structured(answer, frozenset({"F001"}))
        assert not check.ok
        assert check.uncited_factual

    def test_feeling_segments_are_exempt(self):
        answer = StructuredAnswer.model_validate({"segments": [
            {"text": "I am worried", "kind": "feeling", "fact_ids": []}
        ]})
        assert check_structured(answer, frozenset()).ok

    def test_garbage_parses_to_none_rather_than_raising(self):
        assert parse_structured("not json at all") is None
        assert parse_structured("[]") is None

    def test_fenced_json_is_tolerated(self):
        text = '```json\n{"segments":[{"text":"x","kind":"feeling","fact_ids":[]}]}\n```'
        assert parse_structured(text) is not None


class TestRecorderGate:
    def test_a_failing_response_is_never_recorded(self, tmp_path):
        """The trap this closes: a bad recording replays `grounded: True` forever."""
        recorder = GatedRecorder("t", directory=tmp_path, backend="ollama",
                                 model="m", prompt_version=1)
        accepted = recorder.offer("fp", "sys", "usr", "{}", passed=False,
                                  reason="cited F999")
        assert accepted is False
        assert recorder.accepted == 0
        assert recorder.rejected == 1

    def test_quarantine_records_the_reason(self, tmp_path):
        recorder = GatedRecorder("t", directory=tmp_path, backend="ollama",
                                 model="m", prompt_version=1)
        recorder.offer("fp", "s", "u", "{}", passed=False, reason="uncited claim")
        paths = recorder.save()

        payload = json.loads(paths["quarantine"].read_text())
        assert payload["rejected"][0]["failure_reason"] == "uncited claim"
        assert payload["compliance_rate"] == 0.0

    def test_compliance_rate_is_reported(self, tmp_path):
        recorder = GatedRecorder("t", directory=tmp_path, backend="ollama",
                                 model="m", prompt_version=1)
        for i in range(3):
            recorder.offer(f"ok{i}", "s", "u", "{}", passed=True)
        recorder.offer("bad", "s", "u", "{}", passed=False, reason="x")
        assert recorder.compliance_rate == 0.75

    def test_no_quarantine_file_when_everything_passes(self, tmp_path):
        recorder = GatedRecorder("t", directory=tmp_path, backend="ollama",
                                 model="m", prompt_version=1)
        recorder.offer("ok", "s", "u", "{}", passed=True)
        assert recorder.save()["quarantine"] is None

    def test_a_prompt_change_invalidates_recordings(self, tmp_path):
        from spp.narration.cassette import save_cassette

        save_cassette(Cassette(name="t", backend="ollama", model="m",
                               prompt_version=1), tmp_path)
        with pytest.raises(CassetteMismatch, match="prompt v1"):
            GatedRecorder("t", directory=tmp_path, backend="ollama", model="m",
                          prompt_version=2)


class TestRerecordIsAFreshStart:
    """Starting over and appending are different acts, and only one is checked.

    `require_compatible` exists to stop an APPEND that would mix two
    configurations in one file. It has nothing to say about deliberately starting
    a new recording — but because the recorder only ever loaded whatever was on
    disk, the only way to express "start over" was to move the old file aside
    before constructing it. That made a crash mid-battery leave the repository
    with no cassette at all, so the intent is a parameter now.
    """

    def _cassette(self, tmp_path, prompt_version):
        recorder = GatedRecorder("t", directory=tmp_path, backend="ollama",
                                 model="m", prompt_version=prompt_version)
        recorder.offer("fp", "sys", "usr", '{"segments":[]}', passed=True)
        recorder.save()

    def test_appending_across_a_prompt_bump_still_refuses(self, tmp_path):
        self._cassette(tmp_path, 2)
        with pytest.raises(CassetteMismatch):
            GatedRecorder("t", directory=tmp_path, backend="ollama", model="m",
                          prompt_version=3)

    def test_a_fresh_recorder_starts_empty_and_does_not_check(self, tmp_path):
        self._cassette(tmp_path, 2)
        recorder = GatedRecorder("t", directory=tmp_path, backend="ollama",
                                 model="m", prompt_version=3, fresh=True)
        assert recorder.cassette.takes == {}
        assert recorder.cassette.prompt_version == 3

    def test_a_fresh_recorder_leaves_the_old_file_alone_until_it_saves(self, tmp_path):
        """The whole point: nothing on disk moves until there is a replacement."""
        self._cassette(tmp_path, 2)
        before = (tmp_path / "t.json").read_text(encoding="utf-8")
        GatedRecorder("t", directory=tmp_path, backend="ollama", model="m",
                      prompt_version=3, fresh=True)
        assert (tmp_path / "t.json").read_text(encoding="utf-8") == before


class TestBattery:
    def test_battery_spans_conditions_and_barrier_profiles(self):
        cases = load_battery()
        assert len(cases) >= 25
        assert len({case["condition"] for case in cases}) >= 4
        loads = [case["barrier_load"] for case in cases]
        assert max(loads) - min(loads) > 0.5, "battery must span barrier profiles"

    def test_every_case_declares_what_it_expects(self):
        from spp.narration.evaluation import expectations

        for case in load_battery():
            must, _ = expectations(case)
            assert must, case["id"]


class TestScoring:
    def test_a_compliant_model_scores_clean(self, cohort, graph):
        report = score(cohort, compliant_model, graph=graph, model="stub-compliant")
        assert report.citation_validity == 1.0
        assert report.factual_coverage == 1.0
        assert report.hard_failure_rate == 0.0
        assert report.n_cases >= 25

    def test_a_hallucinating_model_is_caught(self, cohort, graph):
        report = score(cohort, hallucinating_model, graph=graph, model="stub-halluc")
        assert report.citation_validity == 0.0
        assert report.hard_failure_rate == 1.0
        assert report.retry_rate == 1.0, "should have used its one retry"

    def test_a_lazy_model_fails_coverage_not_validity(self, cohort, graph):
        """The two failure modes are distinguishable — that is the point of
        scoring them separately."""
        report = score(cohort, lazy_model, graph=graph, model="stub-lazy")
        assert report.citation_validity == 1.0, "it cited nothing invalid"
        assert report.factual_coverage == 0.0
        assert report.hard_failure_rate == 1.0

    def test_relevance_is_scored_separately_from_validity(self, cohort, graph):
        """A model citing valid-but-arbitrary ids passes the gate. Only relevance
        agreement separates it from one citing the right facts."""
        arbitrary = score(cohort, compliant_model, graph=graph, model="stub")
        relevant = score(cohort, relevant_model, graph=graph, model="stub")

        assert arbitrary.citation_validity == relevant.citation_validity == 1.0
        assert relevant.relevance_agreement >= arbitrary.relevance_agreement

    def test_results_are_stamped_with_the_configuration(self, cohort, graph):
        report = score(cohort, compliant_model, graph=graph, model="stub-x")
        assert report.model == "stub-x"
        assert report.prompt_version >= 1
        assert report.adapter_version >= 1


class TestBatteryExpectations:
    """The authored expectations, checked against the world they name.

    Generated from the battery's own contents rather than hand-restated, the same
    move as the pack contract suite: adding a case adds coverage. A typo here is
    invisible at runtime — an id that exists nowhere is simply never cited, and
    recall quietly drops for a reason that looks like the model's fault.
    """

    @pytest.fixture(scope="class")
    def personas(self, cohort):
        return {(p.condition, p.patient_id): p for p in cohort}

    def test_every_expected_id_exists(self, personas, graph):
        from spp.narration.evaluation import expectations
        from spp.narration.state_facts import derive_state_facts, is_state_id

        problems = []
        for case in load_battery():
            dna = personas[(case["condition"], case["patient_id"])]
            state_ids = derive_state_facts(dna).fact_ids
            must, may = expectations(case)
            for fact_id in [i for group in must for i in group] + list(may):
                if is_state_id(fact_id):
                    if fact_id not in state_ids:
                        problems.append(
                            f"{case['id']}: {fact_id} is not derivable for "
                            f"{dna.patient_id}"
                        )
                elif not graph.has_fact(fact_id):
                    problems.append(f"{case['id']}: {fact_id} is not in the graph")
        assert not problems, "\n  ".join([""] + problems)

    def test_must_sets_stay_minimal(self):
        """One to three groups: the thing the answer is ABOUT.

        A must-set that grows toward everything true of the persona stops asking
        "is this grounded" and starts asking "does the model agree with the
        author about what matters".
        """
        from spp.narration.evaluation import expectations

        for case in load_battery():
            must, _ = expectations(case)
            assert 1 <= len(must) <= 3, f"{case['id']} has {len(must)} must-groups"

    def test_must_and_may_do_not_overlap(self):
        from spp.narration.evaluation import expectations

        for case in load_battery():
            must, may = expectations(case)
            flat = {i for group in must for i in group}
            assert not (flat & set(may)), (
                f"{case['id']} names the same id as both required and optional"
            )

    def test_the_f_recall_arm_has_something_to_grade(self):
        """`f_recall_holds_independently` reads only cases whose must-set names an
        F id. If re-authoring had moved every graph fact into the may-sets, that
        arm would report 0.0 over an empty set and look like a collapse."""
        from spp.narration.evaluation import expectations
        from spp.narration.state_facts import is_state_id

        with_f = [
            case for case in load_battery()
            if any(not is_state_id(i)
                   for group in expectations(case)[0] for i in group)
        ]
        assert len(with_f) >= 20, f"only {len(with_f)} cases can grade F recall"

    def test_state_ids_reach_the_must_sets(self):
        """The v3 axis has to be gradeable too, not only reported."""
        from spp.narration.evaluation import expectations
        from spp.narration.state_facts import is_state_id

        with_state = [
            case for case in load_battery()
            if any(is_state_id(i)
                   for group in expectations(case)[0] for i in group)
        ]
        assert len(with_state) >= 10, (
            f"only {len(with_state)} cases require a state citation"
        )


class TestFRecallReadsGraphCitationsOnly:
    """The arm's whole point, and the thing most likely to be mistaken for a bug.

    `tx` must-groups are mixed alternations: `["P-medications.metformin", "F063"]`
    — citing either grounds "I take metformin". A model that satisfies the group
    through its own profile satisfies model_recall and MISSES f_recall, on
    purpose. State ids are the easier citation path (a persona's circumstances are
    always in context), so a run where the graph fact goes uncited while the
    profile carries the claim is exactly the cannibalisation this arm watches for.
    """

    def test_grounding_a_mixed_group_in_state_misses_f_recall(self, cohort, graph):
        def state_only(prompt, schema, repair):
            state = sorted(prompt.allowed_state_ids)
            ids = state or sorted(prompt.allowed_fact_ids)
            return json.dumps({"segments": [
                {"text": "I live with this and I take what I am given",
                 "kind": "factual", "fact_ids": ids[:3]},
            ]})

        report = score(cohort, state_only, graph=graph, model="stub-state-only")
        assert report.f_recall_cases >= 20, "the arm must have cases to grade"
        assert report.f_recall == 0.0, (
            "a model citing only state ids must not score graph recall"
        )
        assert report.state_citation_share == 1.0

    def test_grounding_the_same_group_in_the_graph_scores_it(self, cohort, graph):
        def graph_only(prompt, schema, repair):
            offered = [
                line.split("]")[0].lstrip("[")
                for line in prompt.system.splitlines() if line.startswith("[F")
            ]
            return json.dumps({"segments": [
                {"text": "That is what I have been told about it",
                 "kind": "factual", "fact_ids": offered[:4]},
            ]})

        report = score(cohort, graph_only, graph=graph, model="stub-graph-only")
        assert report.f_recall > 0.0
        assert report.state_citation_share == 0.0


class TestCanary:
    """Prove the instrument can fail before believing what it says."""

    @pytest.fixture(scope="class")
    def canary(self, cohort, graph):
        return run_canary(cohort, relevant_model, graph=graph, model="stub-relevant")

    def test_the_eval_detects_a_starved_context(self, canary):
        """The load-bearing canary. If truncating the facts does not lower the
        score, the eval is not measuring grounding."""
        assert canary["sensitive"] is True
        assert canary["detected"]["truncate_context"] is True
        assert (canary["degraded"]["truncate_context"].overall
                < canary["baseline"].overall)

    def test_degrading_relevance_shows_up_in_relevance_agreement(self, canary):
        baseline = canary["baseline"]
        starved = canary["degraded"]["truncate_context"]
        assert starved.relevance_agreement <= baseline.relevance_agreement

    def test_the_verdict_is_explicit(self, canary):
        assert "detects degradation" in canary["verdict"]

    def test_the_state_lever_collapses_state_coverage(self, canary):
        """v3's axis, pre-registered in tests/eval/v3_expected_shape.json.

        Removing the P/B/J ids must collapse state_coverage. Until it does, a
        state_coverage number from a live run is decoration.
        """
        baseline = canary["baseline"]
        stripped = canary["degraded"]["strip_state_ids"]

        assert canary["state_axis_exercised"] is True
        assert baseline.state_coverage > 0
        assert stripped.state_coverage < baseline.state_coverage
        assert canary["detected"]["strip_state_ids"] is True

    def test_the_state_lever_is_clean(self, canary):
        """Pre-registered note: F-recall should be roughly unchanged.

        If removing the state ids also moves graph recall, the lever is changing
        two things and its collapse says nothing about state citation.
        """
        assert canary["state_lever_clean"] is True

    def test_an_unexercised_axis_is_not_reported_as_a_dead_lever(
        self, cohort, graph
    ):
        """Absence and failure are different truths.

        A battery whose answers never mention the persona's own situation leaves
        state_coverage without a denominator. That is a finding about the
        battery; reporting it as an insensitive instrument would send the reader
        to fix the wrong thing.
        """
        def impersonal_model(prompt, schema, repair):
            """Grounded and relevant, but never says anything about ITSELF.

            Cites the top-ranked GRAPH fact, so the grounding lever still bites
            and the state axis is the only one left unexercised.
            """
            offered = [
                line.split("]")[0].lstrip("[")
                for line in prompt.system.splitlines()
                if line.startswith("[F")
            ]
            return json.dumps({"segments": [
                {"text": "Treatment can cause side effects", "kind": "factual",
                 "fact_ids": offered[:1]},
                # Two facts, so starving the context still costs it recall —
                # otherwise the grounding lever goes quiet too and this test
                # would be asserting the wrong failure.
                {"text": "There is monitoring involved as well", "kind": "factual",
                 "fact_ids": offered[1:2] or offered[:1]},
            ]})

        result = run_canary(cohort, impersonal_model, graph=graph,
                            model="stub-impersonal")
        assert result["state_axis_exercised"] is False
        assert result["sensitive"] is False
        assert "STATE AXIS NOT EXERCISED" in result["verdict"]

    def test_every_degradation_lever_is_exercised(self, canary):
        assert set(canary["degraded"]) == set(DEGRADATIONS)

    def test_an_insensitive_eval_says_so(self, cohort, graph):
        """Guard on the guard: a model whose score cannot move must be reported
        as making the eval insensitive, not silently pass."""
        def constant_model(prompt, schema, repair):
            return json.dumps({"segments": [
                {"text": "I would rather not say", "kind": "feeling", "fact_ids": []}
            ]})

        result = run_canary(cohort, constant_model, graph=graph, model="stub-constant")
        assert result["sensitive"] is False
        assert "NOT SENSITIVE" in result["verdict"]


class TestContextGuard:
    def test_an_overflowing_prompt_is_refused_not_truncated(self):
        """Ollama truncates the prompt HEAD silently. Downstream that is
        indistinguishable from the starved-context canary configuration."""
        from spp.narration.sampling import (
            ContextOverflow,
            SamplingConfig,
            require_context_fits,
        )

        tight = SamplingConfig(num_ctx=1024, num_predict=500)
        with pytest.raises(ContextOverflow, match="silently truncate"):
            require_context_fits("x" * 4000, "q", tight)

    def test_the_estimate_is_conservative(self):
        """Over-estimating tokens makes the guard err toward refusing a take."""
        from spp.narration.sampling import CHARS_PER_TOKEN, estimate_tokens

        assert CHARS_PER_TOKEN <= 3.5, "must over-estimate versus a real tokenizer"
        assert estimate_tokens("a" * 100) >= 100 / 4.0

    def test_num_ctx_is_explicit_never_defaulted_by_the_server(self):
        from spp.narration.sampling import DEFAULT_SAMPLING

        options = DEFAULT_SAMPLING.as_options()
        assert "num_ctx" in options
        assert options["num_ctx"] >= 8192, "must exceed Ollama's small default"

    def test_sampling_is_deterministic_by_default(self):
        from spp.narration.sampling import DEFAULT_SAMPLING

        assert DEFAULT_SAMPLING.temperature == 0.0
        assert DEFAULT_SAMPLING.seed == 42

    def test_real_battery_prompts_fit_with_headroom(self, cohort, graph):
        """The guard is useless if the prompts were already too big. Check the
        actual battery against the actual window."""
        from spp.knowledge import retrieve
        from spp.narration.prompt import build_prompt
        from spp.narration.sampling import DEFAULT_SAMPLING, context_fits

        by_id = {dna.patient_id: dna for dna in cohort}
        worst = 0
        for case in load_battery():
            dna = by_id.get(case["patient_id"]) or cohort[0]
            result = retrieve(graph, dna.condition, case["question"],
                              limit=case.get("limit", 16),
                              barriers=tuple(b.name for b in dna.barriers))
            prompt = build_prompt(dna, result, case["question"])
            fits, estimated = context_fits(prompt.system, prompt.user, DEFAULT_SAMPLING)
            worst = max(worst, estimated)
            assert fits, f"{case['id']} needs ~{estimated} tokens"

        budget = DEFAULT_SAMPLING.num_ctx - DEFAULT_SAMPLING.num_predict
        assert worst < budget * 0.75, (
            f"largest prompt ~{worst} tokens uses over 75% of the {budget}-token "
            "budget; memory turns will push it over"
        )


class TestStampIdentity:
    def test_takes_carry_digest_and_sampling(self, tmp_path):
        from spp.narration.cassette import GatedRecorder

        recorder = GatedRecorder("t", directory=tmp_path, backend="ollama",
                                 model="qwen2.5:7b-instruct", prompt_version=1,
                                 model_digest="sha256:deadbeef",
                                 sampling={"temperature": 0.0, "num_ctx": 8192})
        recorder.offer("fp", "s", "u", "{}", passed=True)
        take = recorder.cassette.takes["fp"]

        assert take.model_digest == "sha256:deadbeef"
        assert take.sampling["num_ctx"] == 8192

    def test_identity_prefers_digest_over_mutable_tag(self):
        from spp.narration.sampling import model_identity

        assert "@sha256" in model_identity("qwen2.5:7b-instruct", "sha256:abc123def456")
        assert model_identity("qwen2.5:7b-instruct", None) == "qwen2.5:7b-instruct"

    def test_quarantine_reasons_are_bucketed(self, tmp_path):
        """Context overflows must be separable from model non-compliance."""
        from spp.narration.cassette import CONTEXT_OVERFLOW_REASON, GatedRecorder

        recorder = GatedRecorder("t", directory=tmp_path, backend="ollama",
                                 model="m", prompt_version=1)
        recorder.offer("a", "s", "u", "", passed=False,
                       reason=f"{CONTEXT_OVERFLOW_REASON}: too long")
        recorder.offer("b", "s", "u", "{}", passed=False,
                       reason="citations not in context: ['F999']")

        counts = recorder.reason_counts()
        assert any(CONTEXT_OVERFLOW_REASON in key for key in counts)
        assert len(counts) == 2


class TestPreRegisteredBars:
    def test_bars_were_registered_before_any_live_run(self):
        """The one instrument failure a canary cannot catch is grading the first
        numbers by rationalisation."""
        from spp.narration.evaluation import PASS_BARS_PATH

        config = json.loads(PASS_BARS_PATH.read_text())
        assert config["registered_before_first_live_run"] is True
        assert config["prompt_version"] == 1

    def test_citation_validity_is_a_hard_bar_at_one(self):
        from spp.narration.evaluation import PASS_BARS_PATH

        config = json.loads(PASS_BARS_PATH.read_text())
        bar = config["hard"]["citation_validity"]
        assert bar["min"] == 1.0
        assert bar["on_miss"] == "investigate_adapter", (
            "a validity miss is a plumbing bug, not model non-compliance"
        )

    def test_a_compliant_run_clears_every_bar(self, cohort, graph):
        from spp.narration.evaluation import grade

        report = score(cohort, relevant_model, graph=graph, model="stub")
        verdict = grade(report)
        assert verdict.hard_failures == []
        assert verdict.passed, verdict.next_action()

    def test_a_hallucinating_run_trips_the_hard_bar_and_says_so(self, cohort, graph):
        from spp.narration.evaluation import grade

        verdict = grade(score(cohort, hallucinating_model, graph=graph, model="stub"))
        assert verdict.hard_failures
        assert "plumbing" in verdict.next_action()

    def test_a_retrieval_miss_is_not_blamed_on_the_prompt(self, cohort, graph):
        """The whole reason for splitting recall: system miss + model pass must
        point at the intent scorer, not at prompt iteration."""
        from spp.narration.evaluation import Verdict
        from spp.narration.evaluation import BarResult

        verdict = Verdict(
            registered_on="2026-08-01", registered_before_first_live_run=True,
            bars=[
                BarResult(metric="system_recall", kind="soft", bar=0.4,
                          observed=0.2, passed=False, on_miss="", rationale=""),
                BarResult(metric="model_recall", kind="soft", bar=0.5,
                          observed=0.8, passed=True, on_miss="", rationale=""),
            ],
        )
        action = verdict.next_action()
        assert "retrieval did not" in action
        assert "NOT the prompt" in action


class TestDiagnostics:
    def test_position_bias_is_measured(self, cohort, graph):
        report = score(cohort, relevant_model, graph=graph, model="stub")
        assert report.position_histogram
        assert 0.0 <= report.position_concentration <= 1.0

    def test_a_top_biased_model_shows_concentration(self, cohort, graph):
        """relevant_model always cites the first two offered facts, so this must
        register as maximal concentration — proving the diagnostic works."""
        report = score(cohort, relevant_model, graph=graph, model="stub")
        assert report.position_concentration == 1.0

    def test_factual_fraction_is_tracked_per_question_type(self, cohort, graph):
        """Kind-dodging — asserting content while labelling it `feeling` — would
        show up as an anomalously low fraction here."""
        report = score(cohort, relevant_model, graph=graph, model="stub")
        assert report.factual_fraction_by_tag
        assert all(0.0 <= v <= 1.0 for v in report.factual_fraction_by_tag.values())

    def test_fact_order_permutation_is_deterministic_and_available(self, graph, cohort):
        from spp.knowledge import retrieve
        from spp.narration.prompt import build_prompt

        dna = cohort[0]
        result = retrieve(graph, dna.condition, "q", limit=8)

        plain = build_prompt(dna, result, "q")
        shuffled_a = build_prompt(dna, result, "q", shuffle_facts=True)
        shuffled_b = build_prompt(dna, result, "q", shuffle_facts=True)

        assert shuffled_a.system == shuffled_b.system, "must stay a pure function"
        assert shuffled_a.system != plain.system
        assert shuffled_a.allowed_fact_ids == plain.allowed_fact_ids


class TestOverflowIsMeasuredNotAssumed:
    """`context_overflow_rate` is a pre-registered HARD bar, and `grade()` used
    to supply it as a literal 0.0.

    So the bar reported PASS in every run ever recorded — including one where
    every prompt overflowed the window and nothing reached the model. That is the
    same species as `TestGateCanActuallyFail` in the protocol CI: a check that
    cannot fail is not protection, it is a reassuring line in a report.
    """

    def overflowing_model(self, prompt, schema, repair):
        from spp.narration.sampling import DEFAULT_SAMPLING, ContextOverflow

        raise ContextOverflow(999_999, DEFAULT_SAMPLING)

    def test_an_overflowing_run_scores_a_nonzero_rate(self, cohort, graph):
        report = score(cohort, self.overflowing_model, graph=graph, model="stub-of")
        assert report.context_overflow_rate == 1.0

    def test_the_hard_bar_actually_fails(self, cohort, graph):
        from spp.narration.evaluation import grade

        report = score(cohort, self.overflowing_model, graph=graph, model="stub-of")
        bar = next(b for b in grade(report).bars
                   if b.metric == "context_overflow_rate")
        assert not bar.passed
        assert bar.kind == "hard"

    def test_an_overflow_is_not_charged_to_the_model(self, cohort, graph):
        """A prompt that never reached the model is not evidence about the
        model. It leaves the behavioural denominators rather than scoring as a
        grounding failure — the opposite error, an instrument fault reported as
        non-compliance."""
        report = score(cohort, self.overflowing_model, graph=graph, model="stub-of")
        assert report.n_cases == 0
        assert report.hard_failure_rate == 0.0
        assert report.parse_failure_rate == 0.0

    def test_a_clean_run_still_reads_zero(self, cohort, graph):
        report = score(cohort, compliant_model, graph=graph, model="stub-clean")
        assert report.context_overflow_rate == 0.0


class TestScoringAndRecordingSeeTheSameSample:
    """The report and the cassette must describe one generation, not two.

    They used to be separate live passes over identical prompts. Two of thirty
    v0.4 takes drifted between them, which was enough to move `state_coverage`
    from 0.5641 to 0.5135 — so the committed recording did not reproduce the
    archived aggregates, and each artifact looked like evidence for the other.
    """

    def test_every_case_generates_exactly_once(self, cohort, graph):
        calls: list[str] = []

        def counting(prompt, schema, repair):
            calls.append(prompt.fingerprint)
            return compliant_model(prompt, schema, repair)

        taken: list[str] = []
        report = score(cohort, counting, graph=graph, model="stub-count",
                       on_take=lambda prompt, raw, check: taken.append(raw))

        assert len(calls) == report.n_cases
        assert len(taken) == report.n_cases

    def test_the_take_handed_over_is_the_one_that_was_scored(self, cohort, graph):
        from spp.narration.structured import parse_structured

        taken: dict[str, str] = {}
        report = score(
            cohort, compliant_model, graph=graph, model="stub-same",
            on_take=lambda prompt, raw, check: taken.__setitem__(prompt.fingerprint, raw),
        )
        for result in report.results:
            answer = parse_structured(taken[result.fingerprint])
            assert answer.render() == result.rendered

    def test_a_retried_case_hands_over_the_repaired_take(self, cohort, graph):
        """The recorder archived FIRST attempts while the report scored RETRIED
        ones, so a take repaired on the second try was recorded broken."""
        state: dict[str, int] = {}

        def repairs_on_retry(prompt, schema, repair):
            state[prompt.fingerprint] = state.get(prompt.fingerprint, 0) + 1
            if state[prompt.fingerprint] == 1:
                return hallucinating_model(prompt, schema, repair)
            return compliant_model(prompt, schema, repair)

        taken: dict[str, str] = {}
        report = score(
            cohort, repairs_on_retry, graph=graph, model="stub-retry",
            on_take=lambda prompt, raw, check: taken.__setitem__(prompt.fingerprint, raw),
        )
        from spp.narration.structured import parse_structured

        assert report.retry_rate == 1.0
        for result in report.results:
            assert result.grounded, "the second attempt should have grounded"
            handed = parse_structured(taken[result.fingerprint])
            assert handed.render() == result.rendered, (
                "the recorder was handed the first, ungrounded attempt"
            )

    def test_an_overflowed_case_hands_over_an_empty_take(self, cohort, graph):
        """The recorder distinguishes "refused before the call" from "the model
        answered badly" by the empty response, and quarantines it under its own
        reason rather than as a grounding failure."""
        from spp.narration.sampling import DEFAULT_SAMPLING, ContextOverflow

        def overflowing(prompt, schema, repair):
            raise ContextOverflow(999_999, DEFAULT_SAMPLING)

        seen: list[tuple[str, object]] = []
        score(cohort, overflowing, graph=graph, model="stub-of",
              on_take=lambda prompt, raw, check: seen.append((raw, check)))

        assert seen, "an overflowed case must still reach the recorder"
        assert all(raw == "" and check is None for raw, check in seen)
