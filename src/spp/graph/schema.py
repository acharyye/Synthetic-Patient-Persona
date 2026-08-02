"""The Hetionet-derived KG schema: node labels, relationship types, and the
metaedge codes they come from.

Kept in one place because three things must agree on it — the loader that writes
the graph, the traversals that read it, and the NL->Cypher prompt/validator that
lets an LLM query it. Divergence between those is how a GraphRAG system starts
citing edges that don't exist.

Hetionet v1.0: https://het.io — 47k nodes / 2.25M edges, CC0.
"""
from __future__ import annotations

from typing import NamedTuple

# Every node carries this label in addition to its specific kind, so name lookup
# and the uniqueness constraint have a single place to live.
BASE_LABEL = "Entity"

# Hetionet node kind -> Neo4j label.
NODE_LABELS: dict[str, str] = {
    "Anatomy": "Anatomy",
    "Biological Process": "BiologicalProcess",
    "Cellular Component": "CellularComponent",
    "Compound": "Compound",
    "Disease": "Disease",
    "Gene": "Gene",
    "Molecular Function": "MolecularFunction",
    "Pathway": "Pathway",
    "Pharmacologic Class": "PharmacologicClass",
    "Side Effect": "SideEffect",
    "Symptom": "Symptom",
}


class MetaEdge(NamedTuple):
    code: str          # Hetionet metaedge abbreviation, e.g. "DpS"
    rel_type: str      # Neo4j relationship type
    source_kind: str
    target_kind: str
    description: str   # used in the NL->Cypher schema prompt


# The persona-relevant slice: everything needed to walk
# disease -> symptom / treatment -> adverse event, and disease -> gene -> pathway.
# Loading only these keeps the import to ~270k edges instead of 2.25M; the
# excluded bulk (GpBP, AeG, Gr>G, GiG, ...) is gene-gene and gene-ontology
# machinery that a patient persona never needs to cite.
PERSONA_METAEDGES: tuple[MetaEdge, ...] = (
    MetaEdge("DpS", "PRESENTS_SYMPTOM", "Disease", "Symptom",
             "a disease presents a symptom"),
    MetaEdge("CtD", "TREATS", "Compound", "Disease",
             "a compound treats a disease"),
    MetaEdge("CpD", "PALLIATES", "Compound", "Disease",
             "a compound palliates (eases without curing) a disease"),
    MetaEdge("CcSE", "CAUSES_SIDE_EFFECT", "Compound", "Side Effect",
             "a compound causes a side effect"),
    MetaEdge("DaG", "ASSOCIATES_GENE", "Disease", "Gene",
             "a disease is associated with a gene"),
    MetaEdge("DuG", "UPREGULATES_GENE", "Disease", "Gene",
             "a disease upregulates a gene"),
    MetaEdge("DdG", "DOWNREGULATES_GENE", "Disease", "Gene",
             "a disease downregulates a gene"),
    MetaEdge("GpPW", "PARTICIPATES_PATHWAY", "Gene", "Pathway",
             "a gene participates in a pathway"),
    MetaEdge("DlA", "LOCALIZES_ANATOMY", "Disease", "Anatomy",
             "a disease localises to an anatomical structure"),
    MetaEdge("DrD", "RESEMBLES_DISEASE", "Disease", "Disease",
             "a disease resembles another disease"),
    MetaEdge("CrC", "RESEMBLES_COMPOUND", "Compound", "Compound",
             "a compound resembles another compound"),
    MetaEdge("CbG", "BINDS_GENE", "Compound", "Gene",
             "a compound binds a gene product"),
)

# The remaining Hetionet metaedges, loadable with --all for graph exploration.
EXTRA_METAEDGES: tuple[MetaEdge, ...] = (
    MetaEdge("GpBP", "PARTICIPATES_BIOLOGICAL_PROCESS", "Gene", "Biological Process",
             "a gene participates in a biological process"),
    MetaEdge("GpMF", "PARTICIPATES_MOLECULAR_FUNCTION", "Gene", "Molecular Function",
             "a gene participates in a molecular function"),
    MetaEdge("GpCC", "PARTICIPATES_CELLULAR_COMPONENT", "Gene", "Cellular Component",
             "a gene participates in a cellular component"),
    MetaEdge("AeG", "ANATOMY_EXPRESSES_GENE", "Anatomy", "Gene",
             "an anatomical structure expresses a gene"),
    MetaEdge("AdG", "ANATOMY_DOWNREGULATES_GENE", "Anatomy", "Gene",
             "an anatomical structure downregulates a gene"),
    MetaEdge("AuG", "ANATOMY_UPREGULATES_GENE", "Anatomy", "Gene",
             "an anatomical structure upregulates a gene"),
    MetaEdge("Gr>G", "REGULATES_GENE", "Gene", "Gene", "a gene regulates a gene"),
    MetaEdge("GiG", "INTERACTS_GENE", "Gene", "Gene", "a gene interacts with a gene"),
    MetaEdge("GcG", "COVARIES_GENE", "Gene", "Gene", "a gene covaries with a gene"),
    MetaEdge("CuG", "COMPOUND_UPREGULATES_GENE", "Compound", "Gene",
             "a compound upregulates a gene"),
    MetaEdge("CdG", "COMPOUND_DOWNREGULATES_GENE", "Compound", "Gene",
             "a compound downregulates a gene"),
    MetaEdge("PCiC", "PHARMACOLOGIC_CLASS_INCLUDES", "Pharmacologic Class", "Compound",
             "a pharmacologic class includes a compound"),
)

ALL_METAEDGES: tuple[MetaEdge, ...] = PERSONA_METAEDGES + EXTRA_METAEDGES

METAEDGE_BY_CODE: dict[str, MetaEdge] = {m.code: m for m in ALL_METAEDGES}

# Relationship types the Cypher validator will accept. Anything outside this set
# cannot exist in our graph, so a query naming one is either a hallucination or
# an attempt to reach somewhere it shouldn't.
ALLOWED_REL_TYPES: frozenset[str] = frozenset(m.rel_type for m in ALL_METAEDGES)
ALLOWED_LABELS: frozenset[str] = frozenset(NODE_LABELS.values()) | {BASE_LABEL}


# Clinical shorthand -> the exact Hetionet disease name. Hetionet carries only
# 137 diseases (a coarse DOID subset), so common abbreviations miss on a plain
# name lookup. Conditions genuinely absent from the graph — heart failure is the
# obvious one — are deliberately NOT mapped to a near neighbour: grounding a
# persona on the wrong disease is worse than grounding it on nothing.
CONDITION_ALIASES: dict[str, str] = {
    "copd": "chronic obstructive pulmonary disease",
    "emphysema": "chronic obstructive pulmonary disease",
    "t2d": "type 2 diabetes mellitus",
    "type 2 diabetes": "type 2 diabetes mellitus",
    "type ii diabetes": "type 2 diabetes mellitus",
    "t1d": "type 1 diabetes mellitus",
    "type 1 diabetes": "type 1 diabetes mellitus",
    "ra": "rheumatoid arthritis",
    "ckd": "chronic kidney failure",
    "chronic kidney disease": "chronic kidney failure",
    "sle": "systemic lupus erythematosus",
    "lupus": "systemic lupus erythematosus",
    "cad": "coronary artery disease",
    "ibd": "Crohn's disease",
    "als": "amyotrophic lateral sclerosis",
    "ms": "multiple sclerosis",
    "afib": "atrial fibrillation",
    "htn": "hypertension",
}

# Data-quality caveat worth repeating wherever these edges surface: Hetionet's
# DpS (disease-presents-symptom) edges are derived from MEDLINE co-occurrence,
# not clinical curation. They are directionally useful but noisy — "Birth Weight"
# appears as a symptom of type 2 diabetes. Treat retrieved symptoms as "things
# the literature associates with this disease", not as a curated symptom list.
NOISY_METAEDGES: frozenset[str] = frozenset({"DpS"})


def citation(code: str) -> str:
    """Provenance string attached to every retrieved fact."""
    return f"kg:hetionet:{code}"


def schema_prompt(metaedges: tuple[MetaEdge, ...] = PERSONA_METAEDGES) -> str:
    """Human/LLM-readable schema, injected into the NL->Cypher prompt."""
    lines = [
        "Node labels (every node also carries :Entity, with properties "
        "id, name, kind):",
        "  " + ", ".join(sorted(NODE_LABELS.values())),
        "",
        "Relationships:",
    ]
    lines.extend(
        f"  (:{NODE_LABELS[m.source_kind]})-[:{m.rel_type}]->"
        f"(:{NODE_LABELS[m.target_kind]})  — {m.description}"
        for m in metaedges
    )
    return "\n".join(lines)
