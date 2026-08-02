"""Tests against a real, loaded Neo4j. Skipped unless one is reachable.

    docker compose up -d
    SPP_LIVE=true PYTHONPATH=src python -m spp.ingest.kg_loader
    SPP_LIVE=true pytest tests/test_graph_live.py

They are the only thing that catches a Cypher syntax error or a schema drift
between the loader and the traversals, since the offline stub can't.
"""
import os

import pytest

from spp.graph import GraphClient
from spp.graphrag import retrieve_subgraph
from spp.schemas import PatientDNA

pytestmark = pytest.mark.skipif(
    os.getenv("SPP_LIVE", "").lower() != "true",
    reason="needs SPP_LIVE=true and a loaded Neo4j",
)


@pytest.fixture(scope="module")
def graph():
    client = GraphClient()
    if not client.live:
        pytest.skip("Neo4j not reachable")
    if client.stats().get("nodes", 0) == 0:
        pytest.skip("graph is empty — run python -m spp.ingest.kg_loader")
    yield client
    client.close()


class TestLoadedGraph:
    def test_hetionet_is_fully_loaded(self, graph):
        stats = graph.stats()
        assert stats["nodes"] == 47031
        assert stats["by_kind"]["Disease"] == 137
        assert stats["by_relationship"]["PRESENTS_SYMPTOM"] == 3357
        assert stats["by_relationship"]["TREATS"] == 755

    def test_loading_is_idempotent(self, graph):
        """MERGE on stable ids: counts must not move if the loader reruns."""
        before = graph.stats()
        graph.ensure_constraints()
        assert graph.stats() == before


class TestResolution:
    @pytest.mark.parametrize(
        "query,expected",
        [
            ("type 2 diabetes mellitus", "type 2 diabetes mellitus"),
            ("Type 2 Diabetes Mellitus", "type 2 diabetes mellitus"),
            ("type 2 diabetes", "type 2 diabetes mellitus"),
            ("COPD", "chronic obstructive pulmonary disease"),
            ("copd", "chronic obstructive pulmonary disease"),
            ("breast cancer", "breast cancer"),
            ("rheumatoid arthritis", "rheumatoid arthritis"),
        ],
    )
    def test_condition_names_resolve(self, graph, query, expected):
        node = graph.resolve(query)
        assert node is not None, f"{query!r} did not resolve"
        assert node["name"] == expected

    def test_absent_conditions_resolve_to_nothing_rather_than_a_near_neighbour(self, graph):
        """Hetionet has no heart failure node. Grounding a persona on
        'coronary artery disease' instead would be a clinical misstatement."""
        assert graph.resolve("heart failure") is None
        assert graph.resolve("a condition that does not exist") is None

    def test_unknown_label_is_rejected(self, graph):
        with pytest.raises(ValueError, match="unknown node label"):
            graph.resolve("anything", kind="Salesforce")


class TestTraversal:
    def test_edges_are_real_and_cited(self, graph):
        edges = graph.neighborhood("type 2 diabetes", hops=2, limit=10)
        assert edges
        assert all(e["cite"].startswith("kg:hetionet:") for e in edges)
        assert all(e["source"] and e["rel"] and e["target"] for e in edges)

    def test_traversal_reaches_treatments_and_their_side_effects(self, graph):
        edges = graph.neighborhood("type 2 diabetes", hops=2, limit=25)
        rels = {e["rel"] for e in edges}
        assert "PRESENTS_SYMPTOM" in rels
        assert "TREATS" in rels
        assert "CAUSES_SIDE_EFFECT" in rels, "the treatment -> AE chain is the point"

    def test_one_hop_stays_shallow(self, graph):
        rels = {e["rel"] for e in graph.neighborhood("type 2 diabetes", hops=1, limit=25)}
        assert "CAUSES_SIDE_EFFECT" not in rels
        assert "PARTICIPATES_PATHWAY" not in rels

    def test_different_conditions_ground_differently(self, graph):
        """The stub returned identical edges for everything. This is the
        regression test for that being fixed."""
        diabetes = {e["target"] for e in graph.neighborhood("type 2 diabetes", limit=25)}
        breast = {e["target"] for e in graph.neighborhood("breast cancer", limit=25)}
        assert diabetes and breast
        assert diabetes != breast

    def test_an_ungrounded_condition_returns_nothing(self, graph):
        assert graph.neighborhood("heart failure") == []

    def test_edges_are_deduplicated(self, graph):
        edges = graph.neighborhood("breast cancer", hops=2, limit=25)
        keys = [(e["source"], e["rel"], e["target"]) for e in edges]
        assert len(keys) == len(set(keys))


class TestRetriever:
    def test_anchored_traversal_works_without_the_llm(self, graph):
        dna = PatientDNA(
            patient_id="live-1", age=64, sex="female", condition="type 2 diabetes"
        )
        edges = retrieve_subgraph(graph, dna, "What might I feel?", use_llm_cypher=False)
        assert edges
        assert all("cite" in e for e in edges)

    def test_retrieval_degrades_to_empty_for_an_ungrounded_condition(self, graph):
        dna = PatientDNA(
            patient_id="live-2", age=70, sex="male", condition="heart failure"
        )
        assert retrieve_subgraph(graph, dna, "How am I?", use_llm_cypher=False) == []
