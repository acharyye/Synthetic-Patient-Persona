"""Prompt construction — a pure, deterministic, golden-testable function.

Most narration bugs live here rather than in the model: a fact silently dropped
from the context, a state slice that says the persona is still enrolled after
they dropped out, prior-interview memory that leaks another persona's answers.
None of that needs an LLM to detect, and none of it is catchable if prompt
building happens inline inside a generation call.

So `build_prompt(...) -> Prompt` takes only data, returns only data, and is
pinned by golden files. The nondeterminism is quarantined to exactly one line
elsewhere: the model call.

The citation discipline is imposed here too, but as of PROMPT_VERSION 2 it
describes the contract that is actually enforced. Citations are a **decode
constraint**: the model emits segments whose `fact_ids` is a JSON-schema enum
over exactly the retrieved ids, so a fabricated id is ungrammatical rather than
merely detectable (`structured.py`). The prompt's job is to say which segments
need ids and where they go — not to ask for a formatting convention the schema
does not use.

v1 still carried the pre-structured-decode instruction to cite inline with
`[F012]`. The model dutifully satisfied BOTH contracts, so 7 of 25 accepted
takes carried literal markers inside `text` while the renderer appended the same
ids from `fact_ids` — every one of those answers rendering its citations twice.
The renderer strips stray markers as defence in depth; v2's success criterion is
that it has nothing to strip.

PROMPT_VERSION 3 adds the ABOUT YOU block: the persona's own state, carrying
P/B/J ids from `state_facts.py`, offered on the same terms as graph facts. Until
v3 a persona could cite what is true of its *condition* and nothing about its own
*circumstances*, so a sentence about having no car could not be `factual` without
breaking the contract — which is the collapse v2 measured. The block goes AFTER
GROUNDED FACTS deliberately: closest to the question, and outside the instruction
section, so the no-marker-examples rule keeps a clean slice to assert over.
"""
from __future__ import annotations

import hashlib

from pydantic import BaseModel, Field

from ..foundation.events import EventType, PersonaState
from ..knowledge.retrieval import RetrievalResult
from ..schemas import PatientDNA
from .state_facts import StateCitations, derive_state_facts

# v2: the inline-citation instruction is gone.
# v3: the ABOUT YOU block and the P/B/J ids in the enum. Bumping this invalidates
# every recorded cassette via require_compatible(), which is the invalidation
# machinery working rather than collateral — v1's and v2's takes measured
# different configurations and stay as the comparison baselines.
PROMPT_VERSION = 3

SYSTEM_TEMPLATE = """You are a SYNTHETIC PATIENT taking part in a research design \
exercise. You are not a real person and must never claim to be.

Answer in the first person as the patient described below. Be specific and \
concrete. Short paragraphs. Speak the way this person would speak, given their \
health literacy.

CITATION RULES — these are checked automatically and a reply that breaks them is \
rejected:
- Attribute facts using each segment's `fact_ids` field. NEVER write ids, \
brackets or reference markers inside `text` — the text is spoken aloud.
- Every segment you mark `"kind": "factual"` MUST name at least one id in \
`fact_ids`, drawn from GROUNDED FACTS or ABOUT YOU below.
- Anything you say about your own situation — what you take, what you cannot get \
to, what has happened to you — is `"kind": "factual"` and cites an id from ABOUT \
YOU. Being personal does not make it a feeling.
- Segments about your own feelings, worries or preferences take \
`"kind": "feeling"` and need no ids.
- If neither list covers something you are asked, say you do not know. Do not \
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

ABOUT YOU (your own situation, on the same citation terms):
{state_facts}
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
    # The state half of that allowlist, kept separately so the eval can ask
    # "was this segment grounded in the persona or in the graph?" by set
    # membership rather than by re-deriving anything from the id string.
    allowed_state_ids: frozenset[str] = Field(default_factory=frozenset)

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
    include_state_facts: bool = True,
) -> Prompt:
    """Pure function: data in, prompt out. No I/O, no clock, no RNG.

    `shuffle_facts` permutes fact presentation order using a seed derived from
    the persona id — deterministic, so purity holds. Off by default; enable only
    if the compliance eval's position-bias diagnostic shows citations
    concentrating in the first offered positions.

    `include_state_facts=False` is the `strip_state_ids` canary lever: it builds
    the v2 configuration — graph ids only — so the eval can be shown to fail on
    the axis v3 adds. It is threaded through here rather than applied afterwards
    so the degraded run traverses exactly this code path, the same reason
    `degrade` is threaded through `evaluation.score`.
    """
    seed = (
        int(hashlib.blake2b(dna.patient_id.encode(), digest_size=4).hexdigest(), 16)
        if shuffle_facts else None
    )
    state_facts: StateCitations = (
        derive_state_facts(dna) if include_state_facts
        else StateCitations(persona_id=dna.patient_id)
    )
    system = SYSTEM_TEMPLATE.format(
        profile=dna.context(),
        state=render_state(state),
        facts=retrieval.block(shuffle_seed=seed),
        state_facts=state_facts.block(),
        memory=render_memory(memory or []),
    )
    return Prompt(
        system=system,
        user=USER_TEMPLATE.format(question=question.strip()),
        allowed_fact_ids=retrieval.fact_ids | state_facts.fact_ids,
        allowed_state_ids=state_facts.fact_ids,
    )
