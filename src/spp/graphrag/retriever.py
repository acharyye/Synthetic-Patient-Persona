"""GraphRAG retrieval: turn a natural-language turn + patient context into a
grounded subgraph. KG-native (query the graph) rather than doc-chunking, so every
fact traces to an entity you can cite.

Two layers, and the order matters:

  1. **Anchored traversal** — a fixed, deterministic walk from the patient's
     primary condition (symptoms, treatments, adverse events, pathways). Always
     runs. This is the floor: grounding never depends on an LLM behaving.
  2. **NL->Cypher** — when live, an LLM writes one query for the specific
     question, which is validated by `cypher_guard` before execution and merged
     into the results. Any failure is logged and dropped; layer 1 still stands.

That split is deliberate. A retriever that only works when the query-generating
model cooperates is a retriever that fails exactly when a stakeholder is watching.
"""
from __future__ import annotations

from ..config import settings
from ..graph import GraphClient
from ..graph.schema import schema_prompt
from ..schemas import PatientDNA
from .cypher_guard import UnsafeCypher, validate_cypher

CYPHER_SYSTEM = """You write a single read-only Cypher query against a biomedical \
knowledge graph (Hetionet) to retrieve facts that help answer a patient's question.

{schema}

RULES — a query breaking any of these is discarded:
- Exactly one statement, starting with MATCH. No CREATE/MERGE/SET/DELETE/CALL/UNION.
- Refer to the patient's condition only as the parameter $condition, matched
  case-insensitively, e.g. (d:Disease) WHERE toLower(d.name) = toLower($condition)
- Use only the labels and relationship types listed above.
- RETURN exactly three aliased columns: source, rel, target — all strings.
- End with an explicit LIMIT of at most {max_limit}.

Return ONLY the Cypher. No prose, no markdown fences, no explanation."""

CYPHER_USER = """Patient: {summary}
Their question: {question}

Write the Cypher query."""


def _generate_cypher(dna: PatientDNA, question: str, max_limit: int) -> str | None:
    """Ask the LLM for one query. Returns None if the call fails — never raises."""
    try:  # pragma: no cover - requires a live API key
        from anthropic import Anthropic

        client = Anthropic(api_key=settings.anthropic_api_key)
        response = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=400,
            system=CYPHER_SYSTEM.format(schema=schema_prompt(), max_limit=max_limit),
            messages=[
                {
                    "role": "user",
                    "content": CYPHER_USER.format(
                        summary=dna.summary(), question=question
                    ),
                }
            ],
        )
        text = "".join(b.text for b in response.content if b.type == "text").strip()
        # Models fence code even when told not to.
        if text.startswith("```"):
            text = text.split("```")[1]
            if text.lower().startswith("cypher"):
                text = text[len("cypher"):]
        return text.strip() or None
    except Exception as exc:  # pragma: no cover - env dependent
        print(f"[retriever] Cypher generation failed: {exc}")
        return None


def _nl_to_cypher_edges(
    client: GraphClient, dna: PatientDNA, question: str, max_limit: int
) -> list[dict]:
    """Generate, validate and run one question-specific query. Best effort."""
    raw = _generate_cypher(dna, question, max_limit)
    if not raw:
        return []

    try:
        safe = validate_cypher(raw, max_limit=max_limit)
    except UnsafeCypher as exc:
        # Rejections are expected and unremarkable; the anchored traversal covers us.
        print(f"[retriever] rejected generated Cypher ({exc}): {raw!r}")
        return []

    try:  # pragma: no cover - requires a live graph
        rows = client.run(safe, condition=dna.condition)
    except Exception as exc:  # pragma: no cover - env dependent
        print(f"[retriever] generated Cypher failed to execute: {exc}")
        return []

    edges = []
    for row in rows:
        if {"source", "rel", "target"} <= row.keys():
            edges.append(
                {
                    "source": str(row["source"]),
                    "rel": str(row["rel"]),
                    "target": str(row["target"]),
                    "cite": "kg:hetionet:nl2cypher",
                }
            )
    return edges


def retrieve_subgraph(
    client: GraphClient,
    dna: PatientDNA,
    question: str,
    hops: int = 2,
    limit: int = 12,
    use_llm_cypher: bool | None = None,
) -> list[dict]:
    """Retrieve grounded, citeable edges for this patient and question."""
    edges = client.neighborhood(dna.condition, hops=hops, limit=limit)

    if use_llm_cypher is None:
        use_llm_cypher = bool(settings.spp_live and settings.anthropic_api_key)

    if use_llm_cypher and client.live:
        edges = edges + _nl_to_cypher_edges(client, dna, question, max_limit=limit * 2)

    seen: set[tuple[str, str, str]] = set()
    unique: list[dict] = []
    for edge in edges:
        key = (edge["source"], edge["rel"], edge["target"])
        if key not in seen:
            seen.add(key)
            unique.append(edge)
    return unique
