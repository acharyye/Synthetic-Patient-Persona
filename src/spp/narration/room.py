"""Interview Room: replay over recorded evidence, with the evidence named.

Two consequences of cassette mode shape this entire surface.

**1. The store can only answer what it has heard, so the input is a picker.**
Cassettes key on a prompt hash, and the prompt embeds the persona, the retrieved
facts and the prompt version. A free-text box in cassette mode is therefore a
machine for cache misses — almost any typed question falls through to the
skeleton, and the room feels broken while working exactly as designed. So in
cassette mode the *recorded questions are the interface*, each badged with the
digest and prompt version of the take behind it. Free text is offered but
disabled, with the reason stated. The UI affords precisely what the evidence
supports; when a live backend appears, the picker stays as "asked before,
replayable" and free text opens beside it.

**2. Battery takes were recorded memory-free, so replay must be memory-free.**
`evaluation.score()` and `record_narration.py` both build prompts with no prior
turns and no state slice. If the room fed take N a transcript of takes 1..N-1,
the prompt hash would diverge from the recording and every follow-up would miss.
So `MEMORY_SEMANTICS = "independent"` is declared here and asserted by a test
that replays the battery in permuted order and demands identical takes.

Genuine multi-turn recorded sessions are a *different artifact* — a session
cassette recording a fixed question sequence — and would be named as such. The
bug to avoid is a room that silently mixes both semantics; either is fine
declared, the blend is not.
"""
from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ..knowledge.graph import KnowledgeGraph, load_graph
from ..knowledge.retrieval import retrieve
from ..schemas import PatientDNA
from .cassette import Cassette, load_cassette
from .interview import citation_skeleton
from .prompt import PROMPT_VERSION, build_prompt
from .structured import StructuredAnswer, check_structured, parse_structured

# MUST match what the recorder used, or every fingerprint misses. Hoisted here so
# the room and the recorder cannot drift apart silently.
REPLAY_RETRIEVAL_LIMIT = 16

# Declared, not implied. See the module docstring.
MEMORY_SEMANTICS: Literal["independent", "sequential"] = "independent"

EvidenceKind = Literal["recorded_take", "citation_skeleton", "live"]


class Evidence(BaseModel):
    """What produced this answer. Rendered as a badge, never omitted."""

    kind: EvidenceKind
    model: str = ""
    model_digest: str = ""
    prompt_version: int = PROMPT_VERSION
    detail: str = ""

    def label(self) -> str:
        if self.kind == "recorded_take":
            identity = (
                f"{self.model}@{self.model_digest[:19]}"
                if self.model_digest else self.model
            )
            return f"recorded take — {identity}, prompt v{self.prompt_version}"
        if self.kind == "live":
            return f"live — {self.model}, prompt v{self.prompt_version}"
        return "citation skeleton — no model"

    @property
    def is_generated(self) -> bool:
        return self.kind in {"recorded_take", "live"}


class RoomQuestion(BaseModel):
    """A question the room can actually answer, and with what."""

    question: str
    fingerprint: str
    evidence: Evidence
    answerable: bool = True


class RoomAnswer(BaseModel):
    persona_id: str
    question: str
    answer: str
    cited_fact_ids: list[str] = Field(default_factory=list)
    grounded: bool = True
    evidence: Evidence
    offered_fact_ids: list[str] = Field(default_factory=list)
    memory_semantics: str = MEMORY_SEMANTICS


def _prompt_for(dna: PatientDNA, question: str, graph: KnowledgeGraph):
    """Rebuild exactly the prompt the recorder hashed.

    No memory, no state slice — see MEMORY_SEMANTICS. Any divergence here turns
    every replay into a cache miss.
    """
    retrieval = retrieve(
        graph, dna.condition, question,
        limit=REPLAY_RETRIEVAL_LIMIT,
        barriers=tuple(barrier.name for barrier in dna.barriers),
    )
    return build_prompt(dna, retrieval, question), retrieval


def available_questions(
    dna: PatientDNA,
    cassette: Cassette | None,
    battery: list[dict] | None = None,
    graph: KnowledgeGraph | None = None,
) -> list[RoomQuestion]:
    """The selectable set. In cassette mode this IS the interface."""
    graph = graph if graph is not None else load_graph()
    battery = battery or []
    questions: list[RoomQuestion] = []

    for case in battery:
        if case.get("condition") and case["condition"] != dna.condition:
            continue
        question = case["question"]
        prompt, _ = _prompt_for(dna, question, graph)
        take = cassette.get(prompt.fingerprint) if cassette else None

        if take is not None:
            evidence = Evidence(
                kind="recorded_take", model=take.model or (cassette.model if cassette else ""),
                model_digest=take.model_digest, prompt_version=take.prompt_version,
            )
        else:
            evidence = Evidence(
                kind="citation_skeleton",
                detail="no recorded take for this persona and question",
            )
        questions.append(RoomQuestion(
            question=question, fingerprint=prompt.fingerprint, evidence=evidence,
        ))

    # Stable order so the picker does not reshuffle between loads.
    questions.sort(key=lambda q: q.question)
    return questions


def ask(
    dna: PatientDNA,
    question: str,
    cassette: Cassette | None = None,
    graph: KnowledgeGraph | None = None,
) -> RoomAnswer:
    """Answer from a recorded take when one exists, otherwise the skeleton.

    Never fabricates prose and never shows a generic "loading" for a question
    nothing can answer — the skeleton is returned and the badge says so.
    """
    graph = graph if graph is not None else load_graph()
    prompt, retrieval = _prompt_for(dna, question, graph)
    take = cassette.get(prompt.fingerprint) if cassette else None

    if take is not None:
        answer: StructuredAnswer | None = parse_structured(take.response)
        if answer is not None:
            check = check_structured(answer, prompt.allowed_fact_ids)
            return RoomAnswer(
                persona_id=dna.patient_id, question=question,
                answer=answer.render(with_citations=False),
                cited_fact_ids=answer.cited_fact_ids,
                grounded=check.ok,
                evidence=Evidence(
                    kind="recorded_take",
                    model=take.model or (cassette.model if cassette else ""),
                    model_digest=take.model_digest,
                    prompt_version=take.prompt_version,
                ),
                offered_fact_ids=sorted(prompt.allowed_fact_ids),
            )

    text = citation_skeleton(dna, question, retrieval)
    from .citations import check_citations, extract_citations, strip_citations

    return RoomAnswer(
        persona_id=dna.patient_id, question=question,
        answer=strip_citations(text),
        cited_fact_ids=extract_citations(text),
        grounded=check_citations(text, prompt.allowed_fact_ids).ok,
        evidence=Evidence(
            kind="citation_skeleton",
            detail="no recorded take can answer this question",
        ),
        offered_fact_ids=sorted(prompt.allowed_fact_ids),
    )


def free_text_state(cassette: Cassette | None, live: bool) -> dict:
    """Whether the room should accept an unscripted question, and why not."""
    if live:
        return {"enabled": True, "reason": ""}
    return {
        "enabled": False,
        "reason": (
            "Requires a live model — no recorded take can answer an unscripted "
            "question. Pick from the recorded questions, or run "
            "scripts/record_narration.py against a live backend."
        ),
    }


def load_room_cassette(name: str = "narration_battery") -> Cassette | None:
    """Load the battery cassette if one has been recorded. None is normal."""
    try:
        return load_cassette(name)
    except Exception:
        return None
