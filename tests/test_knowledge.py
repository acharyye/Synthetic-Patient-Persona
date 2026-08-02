"""Knowledge layer: pack integrity, the retrieval contract, and its eval set.

Retrieval gets its own eval set (query -> expected fact ids) for the same reason
the cohort gets a statistical contract: it is the layer whose quality decides
whether a persona's words are grounded, and "it looked fine" is not a test.
"""
import json
from pathlib import Path

import pytest

from spp.knowledge import (
    EDGE_SIGNATURES,
    GraphError,
    KnowledgeGraph,
    KnowledgePack,
    load_graph,
    retrieve,
)

EVAL_PATH = Path(__file__).parent / "eval" / "retrieval_eval.json"


@pytest.fixture(scope="module")
def graph():
    return load_graph()


def minimal_pack(**overrides) -> dict:
    payload = {
        "schema_version": 1,
        "name": "t",
        "nodes": [
            {"id": "cond:x", "kind": "Condition", "name": "x"},
            {"id": "sym:y", "kind": "Symptom", "name": "y"},
        ],
        "facts": [{
            "id": "F001", "subject": "cond:x", "predicate": "PRESENTS",
            "object": "sym:y",
            "provenance": {"source": "s", "confidence": "expert_guess"},
        }],
    }
    payload.update(overrides)
    return payload


class TestPackIntegrityGate:
    def test_a_valid_pack_loads(self):
        assert len(KnowledgePack.model_validate(minimal_pack()).facts) == 1

    def test_dangling_endpoints_are_rejected(self):
        """A dangling edge would surface as a persona citing a fact about a node
        that does not exist — a grounding failure that looks like a model bug."""
        payload = minimal_pack()
        payload["facts"][0]["object"] = "sym:does_not_exist"
        with pytest.raises(ValueError, match="dangling edge endpoints"):
            KnowledgePack.model_validate(payload)

    def test_edges_must_respect_the_ontology_signature(self):
        payload = minimal_pack()
        payload["facts"][0]["predicate"] = "CAUSES"  # Treatment -> AdverseEffect
        with pytest.raises(ValueError, match="violating the ontology"):
            KnowledgePack.model_validate(payload)

    def test_unknown_kinds_and_predicates_are_rejected(self):
        payload = minimal_pack()
        payload["nodes"][1]["kind"] = "Vibe"
        with pytest.raises(ValueError, match="unknown kind"):
            KnowledgePack.model_validate(payload)

        payload = minimal_pack()
        payload["facts"][0]["predicate"] = "VIBES_WITH"
        with pytest.raises(ValueError, match="unknown predicate"):
            KnowledgePack.model_validate(payload)

    def test_duplicate_ids_are_rejected(self):
        payload = minimal_pack()
        payload["facts"].append(dict(payload["facts"][0]))
        with pytest.raises(ValueError, match="duplicate fact ids"):
            KnowledgePack.model_validate(payload)

    def test_future_schema_versions_are_rejected(self):
        with pytest.raises(ValueError, match="schema v99"):
            KnowledgePack.model_validate(minimal_pack(schema_version=99))

    def test_a_bad_file_fails_with_a_useful_error(self, tmp_path):
        from spp.knowledge import load_pack

        path = tmp_path / "bad.json"
        path.write_text("{not json")
        with pytest.raises(GraphError, match="could not read"):
            load_pack(path)


class TestShippedGraph:
    def test_the_core_pack_loads_and_is_small(self, graph):
        """Small and owned is the design claim; assert it stays that way."""
        stats = graph.stats()
        assert stats["live"] is True
        assert 50 < stats["nodes"] < 1000, "the graph should stay hand-ownable"
        assert stats["facts"] > 100

    def test_every_ontology_edge_kind_is_actually_used(self, graph):
        used = set(graph.stats()["by_predicate"])
        assert used == set(EDGE_SIGNATURES), (
            f"unused edge kinds: {set(EDGE_SIGNATURES) - used}"
        )

    def test_every_fact_carries_a_source(self, graph):
        for fact_id in [f.id for f in graph._facts.values()]:
            assert graph.fact(fact_id).provenance.source

    def test_barrier_ids_match_the_simulation(self, graph):
        """The join between the deterministic core and the knowledge layer: a
        persona's simulated barrier must resolve to a citable node."""
        from spp.assumptions import BARRIER_SEVERITY

        for barrier in BARRIER_SEVERITY.params:
            node = graph.resolve(barrier, kind="Barrier")
            assert node is not None, f"no Barrier node for simulated barrier {barrier!r}"

    def test_condition_aliases_resolve(self, graph):
        for name in ("type 2 diabetes", "T2D", "COPD",
                     "chronic obstructive pulmonary disease", "rheumatoid arthritis"):
            assert graph.resolve(name, kind="Condition") is not None, name

    def test_heart_failure_is_present_now_that_we_own_the_graph(self, graph):
        """Hetionet had no heart-failure node. Owning the ontology fixes that."""
        assert graph.resolve("heart failure", kind="Condition") is not None


class TestRetrievalContract:
    def test_result_is_frozen(self, graph):
        result = retrieve(graph, "type 2 diabetes")
        with pytest.raises(Exception):
            result.query = "mutated"

    def test_fact_ids_are_the_citation_allowlist(self, graph):
        result = retrieve(graph, "COPD", limit=8)
        assert result.fact_ids == frozenset(f.id for f in result.facts)
        assert all(graph.has_fact(fact_id) for fact_id in result.fact_ids)

    def test_an_unknown_condition_returns_empty_with_zero_confidence(self, graph):
        result = retrieve(graph, "a condition nobody has")
        assert result.anchor is None
        assert len(result) == 0
        assert result.confidence == 0.0
        assert result.block() == "NO FACTS RETRIEVED."

    def test_results_are_deterministic(self, graph):
        first = retrieve(graph, "COPD", "why?", limit=12)
        second = retrieve(graph, "COPD", "why?", limit=12)
        assert first == second

    def test_limit_is_respected(self, graph):
        assert len(retrieve(graph, "type 2 diabetes", limit=5).facts) == 5

    def test_paths_reference_only_retrieved_facts(self, graph):
        result = retrieve(graph, "type 2 diabetes", limit=40)
        for path in result.paths:
            assert set(path.fact_ids) & result.fact_ids

    def test_barrier_steering_promotes_relevant_facts(self, graph):
        """A persona's simulated barriers should surface facts they can speak to
        from experience, not in the abstract."""
        neutral = retrieve(graph, "type 2 diabetes", limit=12)
        steered = retrieve(graph, "type 2 diabetes", limit=12,
                           barriers=("transport", "cost"))

        def barrier_facts(result):
            return {
                f.id for f in result.facts
                if f.object.startswith("barrier:") or f.subject.startswith("barrier:")
            }

        assert len(barrier_facts(steered)) > len(barrier_facts(neutral))

    def test_different_conditions_retrieve_different_facts(self, graph):
        diabetes = retrieve(graph, "type 2 diabetes", limit=15).fact_ids
        copd = retrieve(graph, "COPD", limit=15).fact_ids
        assert diabetes and copd and diabetes != copd

    def test_block_renders_citable_ids(self, graph):
        block = retrieve(graph, "COPD", limit=5).block()
        assert block.count("[F") == 5


@pytest.fixture(scope="module")
def cases():
    assert EVAL_PATH.exists(), f"missing eval set at {EVAL_PATH}"
    return json.loads(EVAL_PATH.read_text(encoding="utf-8"))["cases"]


class TestRetrievalEvalSet:
    """query -> expected fact ids, committed. The retrieval layer's own contract."""

    def test_every_case_recalls_its_expected_facts(self, graph, cases):
        failures = []
        for case in cases:
            result = retrieve(
                graph, case["anchor"], case["query"],
                limit=case.get("limit", 24),
                barriers=tuple(case.get("barriers", [])),
            )
            missing = set(case["expect_facts"]) - result.fact_ids
            if missing:
                failures.append(f"{case['id']}: missing {sorted(missing)}")
            elif case.get("expect_top_ranked"):
                # Relevance, not just recall: burying the right facts below
                # irrelevant ones is a regression even though recall passes.
                top = [f.id for f in result.facts[: len(case["expect_facts"])]]
                if top != case["expect_facts"]:
                    failures.append(
                        f"{case['id']}: expected top-ranked {case['expect_facts']}, "
                        f"got {top}"
                    )
        assert not failures, "retrieval regressed:\n  " + "\n  ".join(failures)

    def test_every_expected_fact_still_exists_in_the_graph(self, graph, cases):
        """Guards the eval set itself: a renamed fact id must fail loudly here
        rather than silently weakening every case that referenced it."""
        for case in cases:
            for fact_id in case["expect_facts"]:
                assert graph.has_fact(fact_id), f"{case['id']} references stale {fact_id}"

    def test_eval_set_covers_the_interesting_shapes(self, cases):
        anchors = {case["anchor"] for case in cases}
        assert len(anchors) >= 4, "eval set should span conditions"
        assert any(case.get("barriers") for case in cases), "no barrier-steered case"
        assert any(case["id"].startswith("neg") for case in cases), "no negative case"
