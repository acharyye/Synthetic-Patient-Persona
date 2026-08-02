"""Single-persona interview: retrieval -> prompt -> generate -> verify -> event.

The whole pipeline runs offline. With no model configured the null backend emits
a **citation skeleton** rather than prose — a structured answer carrying the fact
ids it would have grounded on — which is precisely what the mechanical checker
validates. So retrieval, prompt building, citation verification and the event
append are all exercised in CI end to end; the only untested part is the words in
between, which is the correct boundary.

An interview turn appends an `INTERVIEWED` event to the persona's log, so
longitudinal memory is a read over that log rather than a second store. Replay
purity extends to narration inputs for free.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from ..foundation.events import EventLog, EventType, PersonaState
from ..knowledge.graph import KnowledgeGraph, load_graph
from ..knowledge.retrieval import RetrievalResult, retrieve
from ..schemas import PatientDNA
from .citations import (
    CitationCheck,
    GroundingFailure,
    check_citations,
    repair_instruction,
    strip_citations,
)
from .prompt import Prompt, build_prompt, prior_turns

MAX_REGENERATIONS = 1


class InterviewTurn(BaseModel):
    """One question and its verified answer."""

    patient_id: str
    question: str
    answer: str
    answer_with_citations: str
    cited_fact_ids: list[str] = Field(default_factory=list)
    grounded: bool = True
    attempts: int = 1
    backend: str = "null"
    synthetic: bool = False
    retrieval_confidence: float = 0.0
    sources: list[str] = Field(default_factory=list)
    check: CitationCheck | None = None

    def event_payload(self) -> dict:
        """What gets written to the persona's event log."""
        return {
            "question": self.question,
            "answer": self.answer,
            "cited": self.cited_fact_ids,
            "grounded": self.grounded,
            "backend": self.backend,
        }


def citation_skeleton(
    dna: PatientDNA, question: str, retrieval: RetrievalResult
) -> str:
    """The null backend's answer: structured, citing, and obviously offline.

    Deliberately passes the citation checks — that is the point. It exercises the
    verification path in CI, and it is labelled so nobody mistakes it for
    generated prose in a screenshot.
    """
    if not retrieval.facts:
        return (
            "[offline] I don't know enough to answer that, and I'd rather say so "
            "than guess."
        )

    lines = [
        f"[offline] You asked: {question.strip()}",
        "Speaking from what's on file for me:",
    ]
    for fact in retrieval.facts[:4]:
        lines.append(f"- {fact.text} [{fact.id}]")
    lines.append("I feel like that's a lot to manage on top of everything else.")
    return "\n".join(lines)


def interview(
    dna: PatientDNA,
    question: str,
    graph: KnowledgeGraph | None = None,
    state: PersonaState | None = None,
    log: EventLog | None = None,
    generate=None,
    limit: int = 16,
    strict: bool = False,
) -> InterviewTurn:
    """Ask one persona one question, verified.

    `generate(prompt: Prompt, repair: str | None) -> tuple[str, str, bool]` returns
    (text, backend_name, synthetic). Injected so the caller chooses live, cassette
    or null without this module knowing which.

    `strict=True` raises GroundingFailure instead of returning an ungrounded turn.
    Off by default: a design tool should surface a weak answer with its failure
    attached rather than refuse to produce anything.
    """
    graph = graph if graph is not None else load_graph()
    barriers = tuple(barrier.name for barrier in dna.barriers)
    retrieval = retrieve(graph, dna.condition, question, limit=limit, barriers=barriers)

    prompt = build_prompt(
        dna, retrieval, question, state=state, memory=prior_turns(log)
    )

    if generate is None:
        def generate(_prompt: Prompt, _repair: str | None):
            return citation_skeleton(dna, question, retrieval), "null", True

    attempts = 0
    repair: str | None = None
    text, backend, synthetic = "", "null", True
    check = CitationCheck(ok=False)

    while attempts <= MAX_REGENERATIONS:
        attempts += 1
        text, backend, synthetic = generate(prompt, repair)
        check = check_citations(text, prompt.allowed_fact_ids)
        if check.ok:
            break
        # Exactly one corrective attempt. A loop here would hide a model that
        # will not ground and turn a measurable compliance rate into a hidden one.
        repair = repair_instruction(check)

    if not check.ok and strict:
        raise GroundingFailure(check, attempts)

    turn = InterviewTurn(
        patient_id=dna.patient_id,
        question=question.strip(),
        answer=strip_citations(text),
        answer_with_citations=text,
        cited_fact_ids=check.cited,
        grounded=check.ok,
        attempts=attempts,
        backend=backend,
        synthetic=synthetic,
        retrieval_confidence=retrieval.confidence,
        sources=list(retrieval.sources),
        check=check,
    )

    if log is not None:
        day = log.events[-1].t if log.events else 0
        log.append(EventType.INTERVIEWED, t=day, payload=turn.event_payload())
    return turn
