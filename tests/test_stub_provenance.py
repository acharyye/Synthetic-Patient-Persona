"""The offline graph stub must not impersonate a retrieved fact.

**Why this file exists.** `graph/client.py::_stub_neighborhood` returns four
invented edges whenever Neo4j is absent — which is the default, and the only path
CI ever runs. They cited `kg:hetionet`, `kg:opentargets`, `kg:sider` and
`kg:reactome`: four databases this module never queries, in a format that did not
match `schema.citation()` (no metaedge code), over three relationship types that
do not exist in the Hetionet schema at all. `TREATED_BY` is a real rel type — in
the *owned* graph, `knowledge/ontology.py` — so the stub was mixing both
vocabularies into one edge list.

The marker that said "this is a stub" lived one level up, in the response
(`narration_synthetic`, `narration_backend`, `/health.graph_live`), while
`grounded_edges` is the part that gets printed by `scripts/quickstart.py`,
pasted into a design review and screenshotted. A marker that does not travel with
the fact gets separated from the fact.

**Tested the strong way.** `TestTheOldStubFails` runs the shipped values through
these validators and requires them to be rejected. An assertion that the current
stub passes is worth nothing unless the previous one is shown to fail.
"""
from __future__ import annotations

import pytest

from spp.graph.client import GraphClient, _stub_neighborhood
from spp.graph.schema import (
    ALLOWED_REL_TYPES,
    METAEDGE_BY_CODE,
    NOISY_METAEDGES,
    citation,
)
from spp.graphrag.grounding import build_grounding

# The stub as shipped through v0.5, kept here so the regression is checkable.
OLD_STUB_CITES = ["kg:hetionet", "kg:opentargets", "kg:sider", "kg:reactome"]
OLD_STUB_RELS = [
    "PRESENTS_SYMPTOM", "TREATED_BY", "CAUSES_AE", "ASSOCIATED_PATHWAY",
]


def _stub_edges() -> list[dict]:
    return _stub_neighborhood("type 2 diabetes")


class TestEveryStubEdgeNamesItselfAsFake:
    def test_the_flag_travels_on_the_edge(self):
        """Not in the response wrapper. On the edge."""
        edges = _stub_edges()
        assert edges, "a stub that returns nothing cannot be checked"
        for edge in edges:
            assert edge.get("synthetic") is True, (
                f"{edge} carries no synthetic marker; a consumer that receives "
                f"this list alone cannot tell it was not retrieved"
            )

    def test_the_marker_survives_a_consumer_that_takes_only_the_edges(self):
        """quickstart.py iterates `grounded_edges` and nothing else. Simulate it."""
        edges = GraphClient().neighborhood("COPD")
        assert edges
        assert all(e.get("synthetic") for e in edges)

    def test_the_grounding_block_says_so_to_the_model(self):
        """The prompt is the consumer that matters. A flag in the JSON never
        reaches a model that reads only this string."""
        block = build_grounding(_stub_edges())
        assert "PLACEHOLDER" in block
        assert "not facts retrieved" in block
        assert "Do not build an answer on them" in block

    def test_every_placeholder_edge_is_marked_in_the_block(self):
        edges = _stub_edges()
        block = build_grounding(edges)
        assert block.count("placeholder, not a retrieved fact") == len(edges)

    def test_real_edges_get_no_placeholder_notice(self):
        """The inverse. A blanket warning would teach the model to distrust the
        grounding it is supposed to be constrained by, which is worse than the
        bug it prevents."""
        real = [{"source": "COPD", "rel": "PRESENTS_SYMPTOM", "target": "dyspnoea",
                 "cite": citation("DpS")}]
        block = build_grounding(real)
        assert "placeholder" not in block.lower()
        assert "PLACEHOLDER" not in block


class TestTheStubSpeaksTheSchema:
    """The second defect: the edges did not match the ontology they cited."""

    def test_every_rel_type_exists_in_the_hetionet_schema(self):
        for edge in _stub_edges():
            assert edge["rel"] in ALLOWED_REL_TYPES, (
                f"{edge['rel']!r} is not a Hetionet rel type. It may exist in the "
                f"owned graph — TREATED_BY does — and a citation naming one "
                f"substrate over another's vocabulary is the disagreement "
                f"CLAUDE.md says makes the system cite edges that do not exist."
            )

    def test_every_cite_is_a_well_formed_metaedge_citation(self):
        for edge in _stub_edges():
            code = edge["cite"].rsplit(":", 1)[-1]
            assert edge["cite"] == citation(code), (
                f"{edge['cite']!r} does not match schema.citation()'s format "
                f"('kg:hetionet:<code>')"
            )
            assert code in METAEDGE_BY_CODE, (
                f"{code!r} names no metaedge, so nothing can resolve the citation"
            )

    def test_no_cite_names_a_database_this_module_never_queries(self):
        """The specific impersonation: opentargets, sider, reactome."""
        for edge in _stub_edges():
            assert edge["cite"].startswith("kg:hetionet:"), edge["cite"]
            assert edge["cite"] not in OLD_STUB_CITES

    def test_the_noise_caveat_is_not_spent_on_placeholders(self):
        """DpS is a NOISY_METAEDGES member because Hetionet's symptom edges are
        MEDLINE co-occurrence. Warning about literature curation on an edge no
        literature produced is a different false statement, not a harmless one."""
        block = build_grounding(_stub_edges())
        assert "literature co-occurrence" not in block

    def test_the_noise_caveat_still_fires_on_a_real_noisy_edge(self):
        real = [{"source": "COPD", "rel": "PRESENTS_SYMPTOM", "target": "Birth Weight",
                 "cite": citation("DpS")}]
        assert "literature co-occurrence" in build_grounding(real)

    def test_mixed_edges_carry_both_notes_independently(self):
        """One placeholder beside one real noisy edge: each warning must name its
        own population, or a reader cannot tell which half to distrust."""
        edges = _stub_edges() + [
            {"source": "COPD", "rel": "PRESENTS_SYMPTOM", "target": "dyspnoea",
             "cite": citation("DpS")},
        ]
        block = build_grounding(edges)
        assert f"{len(edges) - 1} of these {len(edges)} links are PLACEHOLDERS" in block
        assert "literature co-occurrence" in block
        assert NOISY_METAEDGES == frozenset({"DpS"})

    def test_the_offline_path_is_the_one_that_returns_these(self):
        """Guards the guard: if GraphClient ever went live-by-default this whole
        file would test an unreachable branch."""
        assert GraphClient().live is False, (
            "SPP_LIVE must be false for the offline suite; these tests describe "
            "the stub, and a live client would make them vacuous"
        )


class TestTheOldStubFails:
    """The canary. Values as shipped through v0.5, run through the rules above."""

    @pytest.mark.parametrize("rel", OLD_STUB_RELS[1:], ids=lambda r: r)
    def test_the_old_rel_types_are_not_in_the_schema(self, rel):
        assert rel not in ALLOWED_REL_TYPES

    def test_treated_by_exists_in_the_owned_graph_but_not_here(self):
        """The confusion that made the old values plausible: TREATED_BY is real,
        somewhere else. Naming the cross-vocabulary mistake explicitly is the
        point — a reviewer 'fixing' the stub toward the owned graph is wrong."""
        from spp.knowledge.ontology import EDGE_KINDS

        assert "TREATED_BY" in EDGE_KINDS
        assert "TREATED_BY" not in ALLOWED_REL_TYPES

    @pytest.mark.parametrize("cite", OLD_STUB_CITES, ids=lambda c: c)
    def test_the_old_cites_are_malformed_or_borrowed(self, cite):
        code = cite.rsplit(":", 1)[-1]
        assert cite != citation(code) or code not in METAEDGE_BY_CODE

    def test_the_old_edges_would_have_failed_the_synthetic_check(self):
        old = [{"source": "x", "rel": rel, "target": "y", "cite": cite}
               for rel, cite in zip(OLD_STUB_RELS, OLD_STUB_CITES)]
        assert not any(e.get("synthetic") for e in old)

    def test_the_old_grounding_block_would_have_been_unmarked(self):
        """Renders the old edges through the CURRENT renderer minus the flag —
        which is exactly what a reader saw: four confident facts, no caveat."""
        old = [{"source": "type 2 diabetes", "rel": rel, "target": "y", "cite": cite}
               for rel, cite in zip(OLD_STUB_RELS, OLD_STUB_CITES)]
        block = build_grounding(old)
        assert "PLACEHOLDER" not in block
        assert "placeholder" not in block
