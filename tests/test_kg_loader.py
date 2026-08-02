"""Parsing tests for the Hetionet loader, plus schema self-consistency.

These run offline against small fixtures — no Neo4j needed. The live load is
covered by tests/test_graph_live.py.
"""
import gzip

import pytest

from spp.graph.schema import (
    ALL_METAEDGES,
    ALLOWED_LABELS,
    ALLOWED_REL_TYPES,
    NODE_LABELS,
    PERSONA_METAEDGES,
    citation,
    schema_prompt,
)
from spp.ingest.kg_loader import iter_edges, iter_nodes

# Hetionet ships CRLF line endings. Getting this wrong makes every `kind` arrive
# as 'Disease\r', match nothing, and load an empty graph — silently.
NODES_CRLF = (
    "id\tname\tkind\r\n"
    "Disease::DOID:9352\ttype 2 diabetes mellitus\tDisease\r\n"
    "Symptom::D005221\tFatigue\tSymptom\r\n"
    "Compound::DB00331\tMetformin\tCompound\r\n"
    "Gene::1234\tCCR5\tGene\r\n"
    "Nonsense::1\tmystery\tNotAKind\r\n"
)

EDGES_CRLF = (
    "source\tmetaedge\ttarget\r\n"
    "Disease::DOID:9352\tDpS\tSymptom::D005221\r\n"
    "Compound::DB00331\tCtD\tDisease::DOID:9352\r\n"
    "Gene::1234\tGpBP\tBiological Process::GO:1\r\n"
)


@pytest.fixture
def nodes_file(tmp_path):
    path = tmp_path / "nodes.tsv"
    path.write_bytes(NODES_CRLF.encode())
    return path


@pytest.fixture
def edges_file(tmp_path):
    path = tmp_path / "edges.sif.gz"
    with gzip.open(path, "wt", encoding="utf-8", newline="") as handle:
        handle.write(EDGES_CRLF)
    return path


class TestNodeParsing:
    def test_crlf_endings_do_not_corrupt_the_kind_column(self, nodes_file):
        nodes = list(iter_nodes(nodes_file))
        assert [n["kind"] for n in nodes] == ["Disease", "Symptom", "Compound", "Gene"]
        assert not any("\r" in n["name"] for n in nodes)
        assert not any("\r" in n["id"] for n in nodes)

    def test_unknown_kinds_are_skipped(self, nodes_file):
        assert all(n["kind"] in NODE_LABELS for n in iter_nodes(nodes_file))
        assert "mystery" not in [n["name"] for n in iter_nodes(nodes_file)]

    def test_ids_and_names_survive(self, nodes_file):
        disease = next(iter_nodes(nodes_file))
        assert disease == {
            "id": "Disease::DOID:9352",
            "name": "type 2 diabetes mellitus",
            "kind": "Disease",
        }


class TestEdgeParsing:
    def test_gzip_and_crlf_are_handled(self, edges_file):
        edges = list(iter_edges(edges_file, {"DpS", "CtD"}))
        assert len(edges) == 2
        assert not any("\r" in e["target"] for e in edges)

    def test_metaedge_allowlist_filters(self, edges_file):
        assert [e["metaedge"] for e in iter_edges(edges_file, {"CtD"})] == ["CtD"]
        assert list(iter_edges(edges_file, set())) == []

    def test_edge_endpoints_are_hetionet_ids(self, edges_file):
        edge = next(iter_edges(edges_file, {"DpS"}))
        assert edge["source"] == "Disease::DOID:9352"
        assert edge["target"] == "Symptom::D005221"


class TestSchemaConsistency:
    """The loader, the traversals and the Cypher validator all read this schema.
    If it contradicts itself they disagree about what a valid edge is."""

    def test_metaedge_codes_are_unique(self):
        codes = [m.code for m in ALL_METAEDGES]
        assert len(codes) == len(set(codes))

    def test_relationship_types_are_unique(self):
        rels = [m.rel_type for m in ALL_METAEDGES]
        assert len(rels) == len(set(rels))

    def test_every_metaedge_endpoint_is_a_known_node_kind(self):
        for metaedge in ALL_METAEDGES:
            assert metaedge.source_kind in NODE_LABELS, metaedge
            assert metaedge.target_kind in NODE_LABELS, metaedge

    def test_persona_slice_is_a_subset_of_all(self):
        assert set(PERSONA_METAEDGES) <= set(ALL_METAEDGES)

    def test_validator_allowlists_match_the_schema(self):
        assert ALLOWED_REL_TYPES == {m.rel_type for m in ALL_METAEDGES}
        assert set(NODE_LABELS.values()) <= ALLOWED_LABELS

    def test_the_traversal_path_in_claude_md_is_loadable(self):
        """disease -> symptom -> treatment -> adverse event -> pathway."""
        codes = {m.code for m in PERSONA_METAEDGES}
        assert {"DpS", "CtD", "CcSE", "DaG", "GpPW"} <= codes

    def test_schema_prompt_names_labels_and_relationships(self):
        prompt = schema_prompt()
        assert "Disease" in prompt and "PRESENTS_SYMPTOM" in prompt
        assert "CAUSES_SIDE_EFFECT" in prompt

    def test_citations_identify_the_source_graph_and_metaedge(self):
        assert citation("DpS") == "kg:hetionet:DpS"
