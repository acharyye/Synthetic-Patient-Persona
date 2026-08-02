"""Knowledge pack: a versioned, validated, provenance-carrying graph.

Treated exactly like a prior pack — schema_version, per-entry provenance,
validated at load with loud diagnostics — because it is the same kind of object:
data that determines output and must be defensible afterwards.

Load-time integrity gate, the analogue of the correlation PSD gate:

  * every edge endpoint exists (no dangling references)
  * every edge respects its ontology signature
  * every fact carries a source and a confidence
  * fact ids are unique and stable

A dangling edge here would surface as a persona citing a fact about a node that
does not exist — a grounding failure that looks like a model problem and isn't.
Failing at load points at the pack instead.

Backed by NetworkX rather than a server. At this scale — a graph we author, in
the low thousands of nodes — an embedded structure is the right call: no
dependency to babysit, and the retrieval contract keeps the substrate swappable
if that ever stops being true.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import networkx as nx
from pydantic import BaseModel, Field, model_validator

from ..foundation.ledger import Confidence
from .ontology import EDGE_KINDS, EDGE_SIGNATURES, NODE_KINDS, phrase

KNOWLEDGE_SCHEMA_VERSION = 1
KNOWLEDGE_DIR = Path(__file__).resolve().parents[3] / "data" / "knowledge"


class GraphError(ValueError):
    """A knowledge pack failed validation. Carries what to fix."""


class Provenance(BaseModel):
    source: str
    confidence: Confidence = Confidence.EXPERT_GUESS
    as_of: date | None = None

    @property
    def quotable(self) -> bool:
        return self.confidence not in {Confidence.EXPERT_GUESS}


class Node(BaseModel):
    model_config = {"frozen": True}

    id: str
    kind: str
    name: str
    aliases: list[str] = Field(default_factory=list)
    note: str = ""

    @model_validator(mode="after")
    def _check_kind(self) -> Node:
        if self.kind not in NODE_KINDS:
            raise ValueError(f"node {self.id!r} has unknown kind {self.kind!r}")
        return self


class Fact(BaseModel):
    """One edge, addressable by a stable id. The unit a persona cites.

    Frozen: a fact handed to the narration layer must be exactly the fact the
    citation checker later verifies against.
    """

    model_config = {"frozen": True}

    id: str
    subject: str
    predicate: str
    object: str
    provenance: Provenance
    qualifier: str = ""

    @model_validator(mode="after")
    def _check_predicate(self) -> Fact:
        if self.predicate not in EDGE_KINDS:
            raise ValueError(f"fact {self.id!r} has unknown predicate {self.predicate!r}")
        return self


class KnowledgePack(BaseModel):
    schema_version: int = KNOWLEDGE_SCHEMA_VERSION
    name: str
    description: str = ""
    nodes: list[Node]
    facts: list[Fact]

    @model_validator(mode="after")
    def _validate(self) -> KnowledgePack:
        if self.schema_version != KNOWLEDGE_SCHEMA_VERSION:
            raise ValueError(
                f"knowledge pack {self.name!r} is schema v{self.schema_version}, "
                f"this build reads v{KNOWLEDGE_SCHEMA_VERSION}"
            )

        node_ids = [node.id for node in self.nodes]
        duplicates = {i for i in node_ids if node_ids.count(i) > 1}
        if duplicates:
            raise ValueError(f"duplicate node ids: {sorted(duplicates)}")

        fact_ids = [fact.id for fact in self.facts]
        duplicate_facts = {i for i in fact_ids if fact_ids.count(i) > 1}
        if duplicate_facts:
            raise ValueError(f"duplicate fact ids: {sorted(duplicate_facts)}")

        kinds = {node.id: node.kind for node in self.nodes}
        dangling: list[str] = []
        mistyped: list[str] = []
        for fact in self.facts:
            for endpoint in (fact.subject, fact.object):
                if endpoint not in kinds:
                    dangling.append(f"{fact.id}: {endpoint!r} is not a node")
            if fact.subject in kinds and fact.object in kinds:
                expected = EDGE_SIGNATURES[fact.predicate]
                actual = (kinds[fact.subject], kinds[fact.object])
                if actual != expected:
                    mistyped.append(
                        f"{fact.id}: {fact.predicate} expects {expected}, got {actual}"
                    )

        if dangling:
            raise ValueError("dangling edge endpoints:\n  " + "\n  ".join(dangling))
        if mistyped:
            raise ValueError("edges violating the ontology:\n  " + "\n  ".join(mistyped))
        return self

    def unquotable(self) -> list[str]:
        return sorted(f.id for f in self.facts if not f.provenance.quotable)


class KnowledgeGraph:
    """NetworkX-backed store over one or more validated packs."""

    def __init__(self, packs: list[KnowledgePack] | None = None) -> None:
        self._graph = nx.MultiDiGraph()
        self._nodes: dict[str, Node] = {}
        self._facts: dict[str, Fact] = {}
        self._alias_index: dict[str, str] = {}
        for pack in packs or []:
            self.add_pack(pack)

    def add_pack(self, pack: KnowledgePack) -> None:
        for node in pack.nodes:
            if node.id in self._nodes and self._nodes[node.id] != node:
                raise GraphError(f"node {node.id!r} redefined differently across packs")
            self._nodes[node.id] = node
            self._graph.add_node(node.id, kind=node.kind, name=node.name)
            for handle in (node.id, node.name, *node.aliases):
                self._alias_index[handle.strip().casefold()] = node.id

        for fact in pack.facts:
            if fact.id in self._facts and self._facts[fact.id] != fact:
                raise GraphError(f"fact {fact.id!r} redefined differently across packs")
            self._facts[fact.id] = fact
            self._graph.add_edge(
                fact.subject, fact.object, key=fact.id, predicate=fact.predicate
            )

    # -- accessors ----------------------------------------------------------

    def __len__(self) -> int:
        return len(self._nodes)

    @property
    def live(self) -> bool:
        """True once a pack is loaded. Kept for API-surface compatibility."""
        return bool(self._nodes)

    def node(self, node_id: str) -> Node:
        return self._nodes[node_id]

    def fact(self, fact_id: str) -> Fact:
        return self._facts[fact_id]

    def has_fact(self, fact_id: str) -> bool:
        return fact_id in self._facts

    def resolve(self, name: str, kind: str | None = None) -> Node | None:
        """Name/alias -> node. Exact then containment; never a wild guess."""
        if not name:
            return None
        key = name.strip().casefold()
        node_id = self._alias_index.get(key)
        if node_id is None:
            candidates = [
                handle for handle in self._alias_index
                if key in handle or handle in key
            ]
            if not candidates:
                return None
            node_id = self._alias_index[min(candidates, key=len)]

        node = self._nodes[node_id]
        return node if kind is None or node.kind == kind else None

    def out_facts(self, node_id: str, predicate: str | None = None) -> list[Fact]:
        if node_id not in self._graph:
            return []
        return [
            self._facts[key]
            for _, _, key in self._graph.out_edges(node_id, keys=True)
            if predicate is None or self._facts[key].predicate == predicate
        ]

    def render(self, fact: Fact) -> str:
        """Human/LLM-readable phrasing, using node display names."""
        subject = self._nodes[fact.subject].name
        object_ = self._nodes[fact.object].name
        text = phrase(fact.predicate, subject, object_)
        return f"{text} ({fact.qualifier})" if fact.qualifier else text

    def stats(self) -> dict:
        by_kind: dict[str, int] = {}
        for node in self._nodes.values():
            by_kind[node.kind] = by_kind.get(node.kind, 0) + 1
        by_predicate: dict[str, int] = {}
        for fact in self._facts.values():
            by_predicate[fact.predicate] = by_predicate.get(fact.predicate, 0) + 1
        return {
            "live": self.live,
            "nodes": len(self._nodes),
            "facts": len(self._facts),
            "by_kind": dict(sorted(by_kind.items())),
            "by_predicate": dict(sorted(by_predicate.items())),
        }


def load_pack(path: str | Path) -> KnowledgePack:
    path = Path(path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GraphError(f"could not read knowledge pack {path}: {exc}") from exc
    try:
        return KnowledgePack.model_validate(payload)
    except Exception as exc:
        raise GraphError(f"knowledge pack {path.name} is invalid: {exc}") from exc


_CACHE: KnowledgeGraph | None = None


def load_graph(directory: Path = KNOWLEDGE_DIR, refresh: bool = False) -> KnowledgeGraph:
    """Load every pack in `directory` into one validated graph. Cached."""
    global _CACHE
    if _CACHE is not None and not refresh:
        return _CACHE
    packs = [load_pack(path) for path in sorted(directory.glob("*.json"))]
    _CACHE = KnowledgeGraph(packs)
    return _CACHE
