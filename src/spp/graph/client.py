"""Thin Neo4j wrapper. Degrades gracefully to a stub subgraph when SPP_LIVE is
False or the driver is unavailable, so the rest of the pipeline always runs.

The live traversals walk the Hetionet-derived graph loaded by
`ingest/kg_loader.py`, following the clinically meaningful path:

    disease -> symptom
    disease <- treatment            (compound TREATS/PALLIATES disease)
    treatment -> adverse event      (compound CAUSES_SIDE_EFFECT)
    disease -> gene -> pathway

Every returned edge carries a `cite` naming the source graph and the Hetionet
metaedge it came from, because grounding without provenance is just a prompt.
"""
from __future__ import annotations

from ..config import settings
from .schema import (
    ALLOWED_LABELS,
    BASE_LABEL,
    CONDITION_ALIASES,
    NODE_LABELS,
    citation,
)


class GraphClient:
    def __init__(self) -> None:
        self._driver = None
        if settings.spp_live:
            try:
                from neo4j import GraphDatabase

                self._driver = GraphDatabase.driver(
                    settings.neo4j_uri,
                    auth=(settings.neo4j_user, settings.neo4j_password),
                )
                self._driver.verify_connectivity()
            except Exception as exc:  # pragma: no cover - env dependent
                print(f"[GraphClient] live mode requested but driver failed: {exc}")
                self._driver = None

    @property
    def live(self) -> bool:
        return self._driver is not None

    # -- raw access ---------------------------------------------------------

    def run(self, cypher: str, **params) -> list[dict]:
        """Execute a read query and return plain dicts."""
        if not self.live:
            raise RuntimeError("GraphClient is not live; cannot run Cypher.")
        with self._driver.session() as session:
            return [record.data() for record in session.run(cypher, **params)]

    def write_batches(self, cypher: str, rows: list[dict], batch_size: int = 5000) -> int:
        """Run a parameterised write once per batch of `rows` (bound to $rows)."""
        if not self.live:
            raise RuntimeError("GraphClient is not live; cannot write.")
        written = 0
        with self._driver.session() as session:
            for start in range(0, len(rows), batch_size):
                chunk = rows[start : start + batch_size]
                session.execute_write(lambda tx, c=chunk: tx.run(cypher, rows=c).consume())
                written += len(chunk)
        return written

    # -- schema -------------------------------------------------------------

    def ensure_constraints(self) -> None:
        """Uniqueness on :Entity(id) (which also indexes it) plus a name index."""
        self.run(
            f"CREATE CONSTRAINT entity_id IF NOT EXISTS "
            f"FOR (n:{BASE_LABEL}) REQUIRE n.id IS UNIQUE"
        )
        self.run(
            f"CREATE INDEX entity_name IF NOT EXISTS FOR (n:{BASE_LABEL}) ON (n.name)"
        )

    def stats(self) -> dict:
        """Node/relationship counts — used by /health and the loader's report."""
        if not self.live:
            return {"live": False}
        nodes = self.run(
            f"MATCH (n:{BASE_LABEL}) RETURN n.kind AS kind, count(*) AS n "
            "ORDER BY n DESC"
        )
        rels = self.run(
            "MATCH ()-[r]->() RETURN type(r) AS rel, count(*) AS n ORDER BY n DESC"
        )
        return {
            "live": True,
            "nodes": sum(row["n"] for row in nodes),
            "relationships": sum(row["n"] for row in rels),
            "by_kind": {row["kind"]: row["n"] for row in nodes},
            "by_relationship": {row["rel"]: row["n"] for row in rels},
        }

    # -- entity resolution --------------------------------------------------

    def resolve(self, name: str, kind: str = "Disease") -> dict | None:
        """Find the graph node for a free-text condition name.

        Exact match, then case-insensitive, then containment. Returns None rather
        than guessing wildly — a persona grounded on the wrong disease is worse
        than one grounded on nothing.
        """
        if not self.live or not name:
            return None
        label = NODE_LABELS.get(kind, kind)
        if label not in ALLOWED_LABELS:
            raise ValueError(f"unknown node label {label!r}")

        # Clinical shorthand ("COPD") never matches Hetionet's spelled-out names.
        name = CONDITION_ALIASES.get(name.strip().casefold(), name)

        for clause in (
            "n.name = $name",
            "toLower(n.name) = toLower($name)",
            "toLower(n.name) CONTAINS toLower($name)",
            "toLower($name) CONTAINS toLower(n.name)",
        ):
            hits = self.run(
                f"MATCH (n:{label}) WHERE {clause} "
                "RETURN n.id AS id, n.name AS name, n.kind AS kind "
                "ORDER BY size(n.name) LIMIT 1",
                name=name,
            )
            if hits:
                return hits[0]
        return None

    # -- traversal ----------------------------------------------------------

    def neighborhood(self, entity: str, hops: int = 2, limit: int = 12) -> list[dict]:
        """Return edges around `entity`. Real impl runs Cypher; stub returns a
        small, deterministic subgraph so grounding/citations have something to cite.

        `hops=1` keeps to facts directly on the disease; `hops>=2` also follows
        treatment -> adverse event and gene -> pathway.
        """
        if not self.live:
            return _stub_neighborhood(entity)

        node = self.resolve(entity, kind="Disease")
        if node is None:
            # Honest empty result. The persona prompt already instructs the model
            # to say it doesn't know rather than invent, and grounding.py renders
            # this as "No grounded facts retrieved."
            return []

        edges: list[dict] = []
        edges.extend(self._direct_edges(node["id"], limit))
        if hops >= 2:
            edges.extend(self._chained_edges(node["id"], limit))

        seen: set[tuple[str, str, str]] = set()
        unique: list[dict] = []
        for edge in edges:
            key = (edge["source"], edge["rel"], edge["target"])
            if key not in seen:
                seen.add(key)
                unique.append(edge)
        return unique

    def _direct_edges(self, disease_id: str, limit: int) -> list[dict]:
        """Symptoms, treatments and look-alike diseases, one hop from the disease."""
        queries = [
            (
                "MATCH (d:Disease {id:$id})-[:PRESENTS_SYMPTOM]->(s:Symptom) "
                "RETURN d.name AS source, 'PRESENTS_SYMPTOM' AS rel, s.name AS target "
                "LIMIT $limit",
                "DpS",
            ),
            (
                "MATCH (c:Compound)-[:TREATS]->(d:Disease {id:$id}) "
                "RETURN c.name AS source, 'TREATS' AS rel, d.name AS target "
                "LIMIT $limit",
                "CtD",
            ),
            (
                "MATCH (c:Compound)-[:PALLIATES]->(d:Disease {id:$id}) "
                "RETURN c.name AS source, 'PALLIATES' AS rel, d.name AS target "
                "LIMIT $limit",
                "CpD",
            ),
            (
                "MATCH (d:Disease {id:$id})-[:LOCALIZES_ANATOMY]->(a:Anatomy) "
                "RETURN d.name AS source, 'LOCALIZES_ANATOMY' AS rel, a.name AS target "
                "LIMIT $limit",
                "DlA",
            ),
        ]
        return self._collect(queries, disease_id, limit)

    def _chained_edges(self, disease_id: str, limit: int) -> list[dict]:
        """Two-hop chains: what the treatments cost, and what pathways are involved."""
        queries = [
            (
                "MATCH (c:Compound)-[:TREATS]->(d:Disease {id:$id}) "
                "MATCH (c)-[:CAUSES_SIDE_EFFECT]->(e:SideEffect) "
                "RETURN c.name AS source, 'CAUSES_SIDE_EFFECT' AS rel, e.name AS target "
                "LIMIT $limit",
                "CcSE",
            ),
            (
                "MATCH (d:Disease {id:$id})-[:ASSOCIATES_GENE]->(g:Gene)"
                "-[:PARTICIPATES_PATHWAY]->(p:Pathway) "
                "RETURN g.name AS source, 'PARTICIPATES_PATHWAY' AS rel, p.name AS target "
                "LIMIT $limit",
                "GpPW",
            ),
        ]
        return self._collect(queries, disease_id, limit)

    def _collect(self, queries: list[tuple[str, str]], disease_id: str, limit: int) -> list[dict]:
        out: list[dict] = []
        for cypher, code in queries:
            for row in self.run(cypher, id=disease_id, limit=limit):
                out.append({**row, "cite": citation(code)})
        return out

    def close(self) -> None:
        if self._driver:
            self._driver.close()
            self._driver = None


def _stub_neighborhood(entity: str) -> list[dict]:
    e = entity or "condition"
    return [
        {"source": e, "rel": "PRESENTS_SYMPTOM", "target": "fatigue", "cite": "kg:hetionet"},
        {"source": e, "rel": "TREATED_BY", "target": "first-line therapy", "cite": "kg:opentargets"},
        {"source": "first-line therapy", "rel": "CAUSES_AE", "target": "nausea", "cite": "kg:sider"},
        {"source": e, "rel": "ASSOCIATED_PATHWAY", "target": "example pathway", "cite": "kg:reactome"},
    ]
