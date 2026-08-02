"""Load the Hetionet biomedical knowledge graph into Neo4j.

Hetionet v1.0 (https://het.io, CC0): 47k nodes / 2.25M edges integrating 29
public resources. We use the TSV/SIF distribution because it streams cheaply:

    hetionet-v1.0-nodes.tsv       id \t name \t kind
    hetionet-v1.0-edges.sif.gz    source \t metaedge \t target

By default only the persona-relevant metaedges are loaded (see
`graph/schema.py`) — ~270k edges rather than 2.25M. The excluded bulk is
gene-gene and gene-ontology machinery a patient persona never cites. Pass
`--all` for the full graph.

    python -m spp.ingest.kg_loader            # download if needed, then load
    python -m spp.ingest.kg_loader --all      # every metaedge
    python -m spp.ingest.kg_loader --stats    # just report what's in the graph

Re-running is safe: everything is MERGEd on stable Hetionet ids.

Other graphs worth adding later: PrimeKG (~4M relationships), Open Targets
(target-disease-drug associations).
"""
from __future__ import annotations

import argparse
import csv
import gzip
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Iterator

from ..graph import GraphClient
from ..graph.schema import (
    ALL_METAEDGES,
    ALLOWED_LABELS,
    ALLOWED_REL_TYPES,
    BASE_LABEL,
    METAEDGE_BY_CODE,
    NODE_LABELS,
    PERSONA_METAEDGES,
    MetaEdge,
)

HETIONET_BASE = "https://github.com/hetio/hetionet/raw/main/hetnet/tsv"
NODES_FILE = "hetionet-v1.0-nodes.tsv"
EDGES_FILE = "hetionet-v1.0-edges.sif.gz"
DEFAULT_DIR = Path(__file__).resolve().parents[3] / "data" / "hetionet"


def download_hetionet(dest: Path = DEFAULT_DIR) -> tuple[Path, Path]:
    """Fetch the node/edge files unless they are already cached in `dest`."""
    dest.mkdir(parents=True, exist_ok=True)
    paths = []
    for filename in (NODES_FILE, EDGES_FILE):
        target = dest / filename
        if not target.exists() or target.stat().st_size == 0:
            url = f"{HETIONET_BASE}/{filename}"
            print(f"[kg_loader] downloading {url}")
            urllib.request.urlretrieve(url, target)  # noqa: S310 - fixed https URL
        paths.append(target)
    return paths[0], paths[1]


def _open_text(path: Path):
    """Hetionet's files ship with CRLF line endings. newline='' lets the csv
    module handle the line splitting; field values still get .strip()ed below,
    which is what stops every `kind` arriving as 'Disease\\r' and matching nothing.
    """
    if path.suffix == ".gz":
        return gzip.open(path, "rt", encoding="utf-8", newline="")
    return path.open("rt", encoding="utf-8", newline="")


def iter_nodes(path: Path) -> Iterator[dict]:
    with _open_text(path) as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            kind = (row.get("kind") or "").strip()
            if kind not in NODE_LABELS:
                continue
            yield {
                "id": (row.get("id") or "").strip(),
                "name": (row.get("name") or "").strip(),
                "kind": kind,
            }


def iter_edges(path: Path, allowed: set[str]) -> Iterator[dict]:
    with _open_text(path) as handle:
        for row in csv.DictReader(handle, delimiter="\t"):
            code = (row.get("metaedge") or "").strip()
            if code not in allowed:
                continue
            yield {
                "source": (row.get("source") or "").strip(),
                "metaedge": code,
                "target": (row.get("target") or "").strip(),
            }


def _load_nodes(client: GraphClient, nodes_path: Path, batch_size: int) -> int:
    by_kind: dict[str, list[dict]] = defaultdict(list)
    for node in iter_nodes(nodes_path):
        by_kind[node["kind"]].append(node)

    total = 0
    for kind, rows in sorted(by_kind.items()):
        label = NODE_LABELS[kind]
        # Labels cannot be parameterised in Cypher, so this one is interpolated.
        # It comes from our own schema map and never from file input.
        assert label in ALLOWED_LABELS, label
        cypher = (
            "UNWIND $rows AS row "
            f"MERGE (n:{BASE_LABEL} {{id: row.id}}) "
            f"SET n:{label}, n.name = row.name, n.kind = row.kind"
        )
        client.write_batches(cypher, rows, batch_size)
        total += len(rows)
        print(f"[kg_loader]   {label:<24} {len(rows):>7} nodes")
    return total


def _load_edges(
    client: GraphClient,
    edges_path: Path,
    metaedges: tuple[MetaEdge, ...],
    batch_size: int,
) -> int:
    allowed = {m.code for m in metaedges}
    by_code: dict[str, list[dict]] = defaultdict(list)
    for edge in iter_edges(edges_path, allowed):
        by_code[edge["metaedge"]].append(edge)

    total = 0
    for code, rows in sorted(by_code.items(), key=lambda kv: -len(kv[1])):
        rel_type = METAEDGE_BY_CODE[code].rel_type
        assert rel_type in ALLOWED_REL_TYPES, rel_type
        cypher = (
            "UNWIND $rows AS row "
            f"MATCH (a:{BASE_LABEL} {{id: row.source}}) "
            f"MATCH (b:{BASE_LABEL} {{id: row.target}}) "
            f"MERGE (a)-[r:{rel_type}]->(b) "
            "SET r.metaedge = row.metaedge"
        )
        client.write_batches(cypher, rows, batch_size)
        total += len(rows)
        print(f"[kg_loader]   {rel_type:<32} {len(rows):>7} edges  ({code})")
    return total


def load_hetionet(
    client: GraphClient,
    data_dir: Path = DEFAULT_DIR,
    full: bool = False,
    batch_size: int = 5000,
) -> dict:
    """Download (if needed) and MERGE Hetionet into Neo4j. Idempotent."""
    if not client.live:
        print("[kg_loader] GraphClient not live; start Neo4j and set SPP_LIVE=true.")
        return {"live": False}

    nodes_path, edges_path = download_hetionet(data_dir)
    metaedges = ALL_METAEDGES if full else PERSONA_METAEDGES

    print("[kg_loader] ensuring constraints")
    client.ensure_constraints()

    print("[kg_loader] loading nodes")
    n_nodes = _load_nodes(client, nodes_path, batch_size)

    print(f"[kg_loader] loading edges ({len(metaedges)} metaedge types)")
    n_edges = _load_edges(client, edges_path, metaedges, batch_size)

    print(f"[kg_loader] done: {n_nodes} nodes, {n_edges} edges")
    return {"loaded_nodes": n_nodes, "loaded_edges": n_edges, **client.stats()}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Load Hetionet into Neo4j for GraphRAG grounding."
    )
    parser.add_argument(
        "--all", action="store_true", dest="full",
        help="load every metaedge, not just the persona-relevant slice",
    )
    parser.add_argument("--data-dir", type=Path, default=DEFAULT_DIR)
    parser.add_argument("--batch-size", type=int, default=5000)
    parser.add_argument(
        "--stats", action="store_true",
        help="report what is already in the graph and exit",
    )
    args = parser.parse_args(argv)

    client = GraphClient()
    try:
        if not client.live:
            print(
                "[kg_loader] Neo4j is not reachable. Start it with "
                "`docker compose up -d` and set SPP_LIVE=true in .env."
            )
            return 1
        if args.stats:
            stats = client.stats()
            print(f"nodes: {stats['nodes']}, relationships: {stats['relationships']}")
            for kind, count in stats["by_kind"].items():
                print(f"  {kind:<24} {count:>8}")
            for rel, count in stats["by_relationship"].items():
                print(f"  {rel:<32} {count:>8}")
            return 0
        load_hetionet(client, args.data_dir, full=args.full, batch_size=args.batch_size)
        return 0
    finally:
        client.close()


if __name__ == "__main__":
    sys.exit(main())
