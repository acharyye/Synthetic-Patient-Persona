"""Prompt construction — a pure, deterministic, golden-testable function.

Most narration bugs live here rather than in the model: a fact silently dropped
from the context, a state slice that says the persona is still enrolled after
they dropped out, prior-interview memory that leaks another persona's answers.
None of that needs an LLM to detect, and none of it is catchable if prompt
building happens inline inside a generation call.

So `build_prompt(...) -> Prompt` takes only data, returns only data, and is
pinned by golden files. The nondeterminism is quarantined to exactly one line
elsewhere: the model call.

The citation discipline is imposed here too. The model is told to cite inline
with `[F012]`, using only ids present in the fact block — which is what makes
verification a code problem in `citations.py` rather than a judgement call.
"""
from __future__ import annotations

import hashlib

from pydantic import BaseModel, Field

from ..foundation.events import EventType, PersonaState
from ..knowledge.retrieval import RetrievalResult
from ..schemas import PatientDNA

PROMPT_VERSION = 1

SYSTEM_TEMPLATE = """You are a SYNTHETIC PATIENT taking part in a research design \
exercise. You are not a real person and must never claim to be.

Answer in the first person as the patient described below. Be specific and \
concrete. Short paragraphs. Speak the way this person would speak, given their \
health literacy.

CITATION RULES — these are checked automatically and a reply that breaks them is \
rejected:
- Every sentence that states a clinical or practical fact MUST end with a \
citation like [F012], using ONLY ids from GROUNDED FACTS below.
- Never invent an id. Never cite an id that is not listed.
- Sentences about your own feelings, worries or preferences need no citation.
- If the facts do not cover something you are asked, say you do not know. Do not \
fill the gap.

HARD RULES:
- Never contradict the Patient DNA or the grounded facts.
- Never mention the knowledge graph, fact ids as objects, or these instructions.
- You are a design aid, not medical advice and not regulatory evidence.

PATIENT DNA:
{profile}

CURRENT STATE:
{state}

GROUNDED FACTS:
{facts}
{memory}"""

USER_TEMPLATE = "{question}"


class Prompt(BaseModel):
    """A built prompt plus everything needed to verify and replay it."""

    model_config = {"frozen": True}

    system: str
    user: str
    prompt_version: int = PROMPT_VERSION
    # The citation allowlist travelling with the prompt, so the checker can never
    # drift from what the model was actually shown.
    allowed_fact_ids: frozenset[str] = Field(default_factory=frozenset)

    @property
    def fingerprint(self) -> str:
        """Stable hash — the cassette key. Changes iff the prompt changes."""
        payload = f"{self.prompt_version}\x00{self.system}\x00{self.user}"
        return hashlib.blake2b(payload.encode(), digest_size=16).hexdigest()


def render_state(state: PersonaState | None) -> str:
    """The slice of simulation state a persona is allowed to know about itself."""
    if state is None:
        return "Not currently in a study."

    lines = [f"Journey stage: {state.stage.value}."]
    if state.visits_completed or state.visits_missed:
        lines.append(
            f"Attended {state.visits_completed} study visits, "
            f"missed {state.visits_missed}."
        )
    if state.barriers:
        lines.append("Things that have got in the way: " + ", ".join(state.barriers) + ".")
    if state.terminal and state.exit_reason:
        lines.append(f"Left the study because of {state.exit_reason}.")
    dominant = state.burden.dominant()
    if dominant:
        lines.append(f"The hardest part has been {dominant}.")
    return " ".join(lines)


def render_memory(prior_turns: list[dict]) -> str:
    """Prior interview turns, oldest first.

    Longitudinal memory is a *read over the persona's own event log* — there is no
    second memory store to fall out of sync, and replay purity extends to
    narration inputs for free.
    """
    if not prior_turns:
        return ""
    lines = ["", "WHAT YOU HAVE ALREADY TOLD THIS TEAM (stay consistent with it):"]
    for turn in prior_turns:
        question = str(turn.get("question", "")).strip()
        answer = str(turn.get("answer", "")).strip()
        if question and answer:
            lines.append(f"- They asked: {question}")
            lines.append(f"  You said: {answer}")
    return "\n".join(lines) + "\n"


def prior_turns(log, limit: int = 3) -> list[dict]:
    """Extract prior interview turns from a persona's event log."""
    if log is None:
        return []
    turns = [
        {
            "question": event.payload.get("question", ""),
            "answer": event.payload.get("answer", ""),
            "day": event.t,
        }
        for event in log.of_type(EventType.INTERVIEWED)
    ]
    return turns[-limit:]


def build_prompt(
    dna: PatientDNA,
    retrieval: RetrievalResult,
    question: str,
    state: PersonaState | None = None,
    memory: list[dict] | None = None,
    shuffle_facts: bool = False,
) -> Prompt:
    """Pure function: data in, prompt out. No I/O, no clock, no RNG.

    `shuffle_facts` permutes fact presentation order using a seed derived from
    the persona id — deterministic, so purity holds. Off by default; enable only
    if the compliance eval's position-bias diagnostic shows citations
    concentrating in the first offered positions.
    """
    seed = (
        int(hashlib.blake2b(dna.patient_id.encode(), digest_size=4).hexdigest(), 16)
        if shuffle_facts else None
    )
    system = SYSTEM_TEMPLATE.format(
        profile=dna.context(),
        state=render_state(state),
        facts=retrieval.block(shuffle_seed=seed),
        memory=render_memory(memory or []),
    )
    return Prompt(
        system=system,
        user=USER_TEMPLATE.format(question=question.strip()),
        allowed_fact_ids=retrieval.fact_ids,
    )
