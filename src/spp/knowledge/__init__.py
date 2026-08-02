"""Knowledge layer: a small owned graph behind a frozen retrieval contract."""
from .graph import (
    Fact,
    GraphError,
    KnowledgeGraph,
    KnowledgePack,
    Node,
    load_graph,
    load_pack,
)
from .ontology import EDGE_KINDS, EDGE_SIGNATURES, NODE_KINDS, TRAVERSAL_PLAN
from .retrieval import (
    FactDetail,
    RetrievalPath,
    RetrievalResult,
    RetrievedFact,
    fact_detail,
    retrieve,
)

__all__ = [
    "EDGE_KINDS",
    "EDGE_SIGNATURES",
    "Fact",
    "FactDetail",
    "GraphError",
    "KnowledgeGraph",
    "KnowledgePack",
    "NODE_KINDS",
    "Node",
    "RetrievalPath",
    "RetrievalResult",
    "RetrievedFact",
    "TRAVERSAL_PLAN",
    "load_graph",
    "fact_detail",
    "load_pack",
    "retrieve",
]
