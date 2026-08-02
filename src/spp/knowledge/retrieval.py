"""The retrieval contract.

`retrieve(...) -> RetrievalResult` is the boundary between "how we store
knowledge" and "how a persona speaks". It is typed, frozen, and returns fact
**ids** — never prose — so that:

  * the citation checker can verify a generated answer mechanically against
    exactly the ids that were offered;
  * the UI can render "this answer used F012 and F031 via path P2";
  * the substrate underneath is swappable without touching narration.

That last point is the real reason this exists. NetworkX today is a judgement
call about scale, not an architectural commitment; the contract is the
commitment.

Retrieval itself is deterministic — a bounded walk of the plan in `ontology.py`,
no LLM, no sampling. Which facts a persona *may* cite is a design decision, not
an emergent property of the graph.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from ..foundation.ledger import Confidence
from .graph import Fact, KnowledgeGraph
from .ontology import TRAVERSAL_PLAN


class RetrievedFact(BaseModel):
    """A fact, with everything needed to cite and verify it."""

    model_config = {"frozen": True}

    id: str
    text: str
    predicate: str
    subject: str
    object: str
    source: str
    confidence: Confidence
    # Which traversal step produced it — the provenance of the *retrieval*, as
    # distinct from the provenance of the fact.
    via: str

    @property
    def quotable(self) -> bool:
        return self.confidence not in {Confidence.EXPERT_GUESS}


class RetrievalPath(BaseModel):
    """A chain of facts, e.g. condition -> treatment -> side effect."""

    model_config = {"frozen": True}

    id: str
    fact_ids: tuple[str, ...]
    description: str


class RetrievalResult(BaseModel):
    """The frozen contract. Narration may cite nothing outside `facts`."""

    model_config = {"frozen": True}

    query: str
    anchor: str | None
    facts: tuple[RetrievedFact, ...] = ()
    paths: tuple[RetrievalPath, ...] = ()
    sources: tuple[str, ...] = ()
    # 0 when nothing anchored — the honest signal that a persona should say it
    # does not know rather than improvise.
    confidence: float = Field(0.0, ge=0.0, le=1.0)

    def __len__(self) -> int:
        return len(self.facts)

    @property
    def fact_ids(self) -> frozenset[str]:
        """The exact set a citation may reference. The checker's allowlist."""
        return frozenset(fact.id for fact in self.facts)

    def by_id(self, fact_id: str) -> RetrievedFact | None:
        return next((f for f in self.facts if f.id == fact_id), None)

    def block(self, shuffle_seed: int | None = None) -> str:
        """Numbered fact list for a prompt. Ids are the citation handles.

        `shuffle_seed` permutes the presentation order deterministically. It is
        OFF by default and exists for the position-bias diagnostic: constrained
        decode plus a fact enum invites citing whatever appears first, and if the
        eval shows citations concentrating in the top positions, permuting per
        persona breaks the artifact without breaking purity — the seed comes from
        the persona, so the prompt stays a pure function of its inputs.
        """
        if not self.facts:
            return "NO FACTS RETRIEVED."
        facts = list(self.facts)
        if shuffle_seed is not None:
            import random

            random.Random(shuffle_seed).shuffle(facts)
        return "\n".join(f"[{fact.id}] {fact.text}" for fact in facts)


# Question vocabulary -> the predicate it is really asking about. Deterministic
# and small on purpose: an embedding model here would make retrieval
# unreplayable, and the ontology is small enough that term overlap is enough.
_INTENT_TERMS: dict[str, tuple[str, ...]] = {
    "CAUSES": ("side effect", "side effects", "reaction", "reactions", "worse",
               "harm", "tolerate", "sick", "unwell"),
    "PRESENTS": ("symptom", "symptoms", "feel", "feeling", "experience",
                 "day to day", "notice"),
    "TREATED_BY": ("treatment", "treated", "taking", "medication", "medicine",
                   "drug", "drugs", "tablets", "therapy"),
    "REQUIRES": ("procedure", "test", "tests", "monitoring", "scan", "bloods"),
    "IMPOSES": ("require", "required", "requirement", "expect", "involve",
                "involves", "have to", "must"),
    "BLOCKED_BY": ("get to", "attend", "travel", "difficult", "hard", "barrier",
                   "manage", "cope", "realistic", "afford", "work", "problem"),
    "MITIGATED_BY": ("help", "helps", "easier", "support", "possible", "enable",
                     "would make", "change"),
    "HAS_STAGE": ("stage", "severity", "how bad", "advanced"),
}

_STOPWORDS = frozenset({
    "the", "a", "an", "is", "are", "was", "were", "do", "does", "did", "you",
    "your", "i", "me", "my", "what", "how", "would", "could", "should", "can",
    "about", "for", "with", "of", "to", "and", "or", "any", "it", "that", "this",
    "on", "in", "be", "have", "has", "if", "at", "from", "there",
})


def _query_terms(query: str) -> frozenset[str]:
    lowered = (query or "").casefold()
    words = {
        word.strip(".,?!;:'\"")
        for word in lowered.split()
    }
    return frozenset(w for w in words if w and w not in _STOPWORDS and len(w) > 2)


def _relevance(fact: RetrievedFact, terms: frozenset[str], query: str) -> int:
    """Deterministic score: intent match on the predicate plus term overlap.

    Phrases are matched against the RAW query, not against the term set: joining
    a set of terms reorders them, so "side effect" could never match a query
    containing exactly those two words side by side.
    """
    if not terms:
        return 0

    # Multi-word intent phrases outrank single words, so "side effects from
    # treatment" resolves to CAUSES rather than TREATED_BY — the more specific
    # phrase wins instead of whichever traversal chain happened to be shorter.
    lowered = (query or "").casefold()
    score = max(
        (
            2 * len(phrase_.split()) + 1
            for phrase_ in _INTENT_TERMS.get(fact.predicate, ())
            if phrase_ in lowered or phrase_ in terms
        ),
        default=0,
    )

    text_words = {
        word.strip(".,?!;:'\"") for word in fact.text.casefold().split()
    }
    score += len(terms & text_words)
    return score


def _to_retrieved(graph: KnowledgeGraph, fact: Fact, via: str) -> RetrievedFact:
    return RetrievedFact(
        id=fact.id,
        text=graph.render(fact),
        predicate=fact.predicate,
        subject=fact.subject,
        object=fact.object,
        source=fact.provenance.source,
        confidence=fact.provenance.confidence,
        via=via,
    )


def retrieve(
    graph: KnowledgeGraph,
    anchor: str,
    query: str = "",
    limit: int = 24,
    barriers: tuple[str, ...] = (),
) -> RetrievalResult:
    """Walk the bounded plan from `anchor`, returning a frozen result.

    `barriers` lets a persona's *simulated* barriers steer retrieval toward the
    participation subgraph — the point where the deterministic core and the
    knowledge layer meet. Barrier node ids match the simulation's barrier names
    by construction.
    """
    node = graph.resolve(anchor, kind="Condition")
    if node is None:
        return RetrievalResult(query=query, anchor=None, confidence=0.0)

    facts: dict[str, RetrievedFact] = {}
    paths: list[RetrievalPath] = []

    for step_index, chain in enumerate(TRAVERSAL_PLAN):
        frontier = [node.id]
        chain_facts: list[str] = []
        for predicate in chain:
            next_frontier: list[str] = []
            for current in frontier:
                for fact in graph.out_facts(current, predicate):
                    if fact.id not in facts:
                        facts[fact.id] = _to_retrieved(graph, fact, via="->".join(chain))
                    chain_facts.append(fact.id)
                    next_frontier.append(fact.object)
            frontier = next_frontier
            if not frontier:
                break

        if len(chain) > 1 and chain_facts:
            paths.append(RetrievalPath(
                id=f"P{step_index + 1}",
                fact_ids=tuple(dict.fromkeys(chain_facts)),
                description=" -> ".join(chain),
            ))

    # Ranking, in priority order:
    #   1. how well the fact answers the QUESTION asked
    #   2. whether it touches a barrier this persona actually has
    #   3. how short the chain that produced it was
    #
    # Query relevance leads because without it a question about side effects
    # returns whatever the traversal happened to surface first — the facts are
    # grounded but they are not an answer. Matching is deterministic term
    # overlap, not an embedding: retrieval must stay replayable and testable.
    relevant = {b.strip().casefold() for b in barriers}

    def _is_barrier(node_id: str) -> bool:
        head, _, tail = node_id.partition(":")
        return head == "barrier" and tail.casefold() in relevant

    terms = _query_terms(query)

    def rank(fact: RetrievedFact) -> tuple[int, int, int, str]:
        return (
            -_relevance(fact, terms, query),
            0 if (_is_barrier(fact.object) or _is_barrier(fact.subject)) else 1,
            len(fact.via),
            fact.id,
        )

    ordered = tuple(sorted(facts.values(), key=rank)[:limit])
    sources = tuple(sorted({fact.source for fact in ordered}))

    # Confidence reflects how much of the plan actually resolved, not how sure
    # we are that the facts are true — that is what `confidence` per fact is for.
    coverage = len({f.via for f in ordered}) / len(TRAVERSAL_PLAN)

    return RetrievalResult(
        query=query,
        anchor=node.id,
        facts=ordered,
        paths=tuple(p for p in paths if set(p.fact_ids) & {f.id for f in ordered}),
        sources=sources,
        confidence=round(min(1.0, coverage), 4),
    )


class FactDetail(BaseModel):
    """A fact expanded for click-through, with its provenance and neighbours.

    The `simulation_link` field is where the architecture becomes visible: when
    the fact concerns a Barrier, it names which of this persona's *derived*
    barriers resolves to it. A spoken sentence, its fact, that fact's provenance,
    and the simulated barrier it grounds — the participation-subgraph join, made
    clickable.
    """

    id: str
    text: str
    predicate: str
    subject: dict
    object: dict
    source: str
    confidence: Confidence
    as_of: str | None = None
    quotable: bool
    neighbours: list[dict] = Field(default_factory=list)
    simulation_link: dict | None = None


def fact_detail(
    graph: KnowledgeGraph, fact_id: str, persona=None
) -> FactDetail | None:
    """Expand one fact for the Interview Room's citation click-through."""
    if not graph.has_fact(fact_id):
        return None

    fact = graph.fact(fact_id)
    subject = graph.node(fact.subject)
    object_ = graph.node(fact.object)

    def describe(node) -> dict:
        return {"id": node.id, "kind": node.kind, "name": node.name,
                "note": node.note}

    # One hop out from each endpoint, so a reader can keep walking.
    neighbours = [
        {"id": neighbour.id, "predicate": neighbour.predicate,
         "text": graph.render(neighbour)}
        for endpoint in (fact.subject, fact.object)
        for neighbour in graph.out_facts(endpoint)
        if neighbour.id != fact_id
    ][:8]

    link = None
    if persona is not None:
        for endpoint in (fact.subject, fact.object):
            head, _, tail = endpoint.partition(":")
            if head != "barrier":
                continue
            match = next(
                (b for b in persona.barriers if b.name.casefold() == tail.casefold()),
                None,
            )
            if match is not None:
                link = {
                    "kind": "derived_barrier",
                    "persona_id": persona.patient_id,
                    "barrier": match.name,
                    "severity": match.severity,
                    # The profile field the simulation derived it from.
                    "origin": match.origin,
                    "note": match.note,
                    "explanation": (
                        f"This persona's simulated barrier {match.name!r} was derived "
                        f"from {match.origin} and resolves to this graph node — the "
                        "same identity the retriever used to steer toward this fact."
                    ),
                }
                break

    return FactDetail(
        id=fact.id, text=graph.render(fact), predicate=fact.predicate,
        subject=describe(subject), object=describe(object_),
        source=fact.provenance.source, confidence=fact.provenance.confidence,
        as_of=fact.provenance.as_of.isoformat() if fact.provenance.as_of else None,
        quotable=fact.provenance.quotable,
        neighbours=neighbours, simulation_link=link,
    )
