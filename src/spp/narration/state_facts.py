"""State-citation: the P/B/J/E namespaces.

Until now a persona could cite **retrieved graph knowledge** (`F###`) and nothing
else. Its own circumstances — no car, a shift-work job, a diagnosis three years
ago — were in the prompt as prose but had no id, so a sentence about them could
not be `factual` without breaking the citation contract. The v2 reading is that
the model resolved that by labelling those segments `feeling`, which is what
`factual_fraction` collapsing on burden (0.667 -> 0.400) and mitigation
(0.933 -> 0.443) actually recorded. The hypothesis under test in v3 is that
giving those segments an id lets them be `factual` AND cited.

Four namespaces, pre-registered in `tests/eval/v3_expected_shape.json`:

    P-  profile fields        P-social_determinants.transport
    B-  derived barriers      B-transport
    J-  journey milestones    J-diagnosis
    E-  event-log entries     RESERVED — see below

**`E-` is declared and deliberately empty.** It means *simulation event-log
entries* — visits attended and missed, burden accrual, dropout — and nothing
else, ever. Folding journey milestones into it would have been free today and
ruinous later: every v3 cassette would go silently ambiguous the day simulated
personas enter the battery carrying real logs, and click-through would have to
disambiguate two provenance types under one prefix. An id namespace whose meaning
changes later is an artifact that acquires its semantics from whoever reads it.
So `derive_state_facts` takes no `PersonaState` and emits no `E-` id; that is the
extension point, and `tests/test_state_citation.py` pins the emptiness so it
cannot drift open by accident.

The consequence is recorded rather than repaired: a question that wants "you
missed visit 3" has no id for an unsimulated persona. That is a **coverage
finding to log**, not an id to stretch.

**What is citable is a declared surface, not everything true.** `PROFILE_FIELDS`
lists it, the same way `TRAVERSAL_PLAN` declares what the graph will walk — what a
persona may cite is a design decision, not an emergent property of its schema.
Biomarkers are deliberately outside it: a persona quoting a lab value is making a
clinical claim, and if a battery question turns out to need one, that is another
coverage finding.

The boundary this does not cross: state-citation lets narration **point at** core
state. It never lets narration change it.
"""
from __future__ import annotations

import re

from pydantic import BaseModel

from ..schemas import PatientDNA

# What each prefix means. Frozen vocabulary: adding one is a schema change that
# invalidates recordings, exactly like a PROMPT_VERSION bump.
NAMESPACE_MEANING: dict[str, str] = {
    "P": "profile field",
    "B": "derived barrier",
    "J": "journey milestone",
    "E": "simulation event-log entry",
}

# Declared, populated by nothing yet. See the module docstring.
RESERVED_NAMESPACES: frozenset[str] = frozenset({"E"})

# The profile surface a persona may cite, declared rather than discovered.
PROFILE_FIELDS: tuple[str, ...] = (
    "age",
    "sex",
    "condition",
    "stage",
    "comorbidities",
    "medications",
    "adherence_baseline",
    "health_literacy",
    "social_determinants",
    "goals",
    "constraints",
)

# The id grammar, shared with the marker regexes in `structured.py` and
# `citations.py` so the three cannot drift apart.
STATE_ID_PATTERN = r"[PBJE]-[A-Za-z0-9_.\-]+"
_STATE_ID_RE = re.compile(rf"^{STATE_ID_PATTERN}$")

_LITERACY_PHRASING: dict[str, str] = {
    "low": "Medical explanations are hard for you to follow.",
    "medium": "You follow medical explanations reasonably well.",
    "high": "You follow medical explanations easily.",
}

_MILESTONE_PHRASING: dict[str, str] = {
    "symptom_onset": "You first noticed something was wrong",
    "first_contact": "You first saw someone about it",
    "diagnosis": "You were diagnosed",
    "treatment_start": "You started treatment",
    "follow_up": "You had a follow-up appointment",
    "adverse_event": "You had a bad reaction",
    "outcome": "This is where things ended up",
}


def namespace_of(citation_id: str) -> str | None:
    """The namespace of a citation id, or None if it is not a state id.

    Graph ids (`F057`) carry no separator, so they fall out here rather than
    needing a second allowlist to be kept in sync.
    """
    head, separator, tail = (citation_id or "").partition("-")
    if separator and tail and head in NAMESPACE_MEANING:
        return head
    return None


def is_state_id(citation_id: str) -> bool:
    return bool(_STATE_ID_RE.match(citation_id or ""))


class StateFact(BaseModel):
    """One citable piece of a persona's own declared state.

    `origin` is the field it was derived from, which is what makes click-through
    close the loop for a derived barrier: cited id -> derived barrier -> the
    profile field the simulation computed it from.
    """

    model_config = {"frozen": True}

    id: str
    text: str
    namespace: str
    origin: str
    detail: str = ""


class StateCitations(BaseModel):
    """The state half of a persona's citation allowlist.

    Mirrors `RetrievalResult` on purpose: ids, never prose, so the checker
    verifies mechanically and the two halves compose into one enum.
    """

    model_config = {"frozen": True}

    persona_id: str
    facts: tuple[StateFact, ...] = ()

    def __len__(self) -> int:
        return len(self.facts)

    @property
    def fact_ids(self) -> frozenset[str]:
        return frozenset(fact.id for fact in self.facts)

    @property
    def namespaces_present(self) -> tuple[str, ...]:
        seen = {fact.namespace for fact in self.facts}
        return tuple(ns for ns in NAMESPACE_MEANING if ns in seen)

    def by_id(self, fact_id: str) -> StateFact | None:
        return next((f for f in self.facts if f.id == fact_id), None)

    def block(self) -> str:
        """Numbered list for a prompt, in the same shape as the fact block."""
        if not self.facts:
            return "NOTHING ON FILE ABOUT YOUR OWN SITUATION."
        return "\n".join(f"[{fact.id}] {fact.text}" for fact in self.facts)


def _slug(value: object, limit: int = 32) -> str:
    """Id-safe, and deliberately **underscore-preserving**.

    A barrier's id has to stay the barrier's name: `traits.barrier_severity`
    derives `competing_care`, the knowledge graph's Barrier node is keyed on that
    same string, and that shared identity is the whole join between a simulated
    barrier and a citable fact. A slug that helpfully rewrote it to
    `competing-care` would quietly cut it — so only characters that are not
    already id-safe collapse to `-`.

    Long free text (a goal, a constraint) truncates at a word boundary rather
    than mid-word. Collisions after truncation are resolved by `_unique`.
    """
    cleaned = re.sub(r"[^a-z0-9_]+", "-", str(value).casefold()).strip("-")
    if len(cleaned) > limit:
        head = cleaned[:limit]
        cleaned = head.rsplit("-", 1)[0] if "-" in head else head
    return cleaned.strip("-") or "unknown"


def _unique(taken: set[str], candidate: str) -> str:
    """Deterministic disambiguation for repeated keys (two follow-ups).

    Suffixes by order of appearance, which is stable because the lists it walks
    are themselves derived deterministically.
    """
    if candidate not in taken:
        taken.add(candidate)
        return candidate
    index = 2
    while f"{candidate}-{index}" in taken:
        index += 1
    resolved = f"{candidate}-{index}"
    taken.add(resolved)
    return resolved


def _profile_facts(dna: PatientDNA) -> list[StateFact]:
    """Walk `PROFILE_FIELDS` in declared order."""
    facts: list[StateFact] = []
    taken: set[str] = set()

    def add(suffix: str, text: str, origin: str, detail: str = "") -> None:
        facts.append(StateFact(
            id=_unique(taken, f"P-{suffix}"), text=text,
            namespace="P", origin=origin, detail=detail,
        ))

    add("age", f"You are {dna.age} years old.", "age")

    if dna.sex in {"female", "male"}:
        add("sex", f"You are {dna.sex}.", "sex")
    else:
        add("sex", f"Your sex is recorded as {dna.sex}.", "sex")

    add("condition", f"You have {dna.condition}.", "condition")

    if dna.stage:
        add("stage", f"Your {dna.condition} is described as {dna.stage}.", "stage")

    for comorbidity in dna.comorbidities:
        add(f"comorbidities.{_slug(comorbidity)}",
            f"You also live with {comorbidity}.",
            f"comorbidities[{comorbidity}]")

    for medication in dna.medications:
        dose = f" ({medication.dose})" if medication.dose else ""
        text = f"You take {medication.name}{dose}."
        if medication.adherence < 1.0:
            text += f" You manage that about {medication.adherence:.0%} of the time."
        add(f"medications.{_slug(medication.name)}", text,
            f"medications[{medication.name}]")

    add("adherence_baseline",
        "You take your medication as prescribed about "
        f"{dna.adherence_baseline:.0%} of the time.",
        "adherence_baseline")

    add("health_literacy",
        _LITERACY_PHRASING.get(
            dna.health_literacy,
            f"Your health literacy is {dna.health_literacy}.",
        ),
        "health_literacy")

    for key, value in dna.social_determinants.items():
        add(f"social_determinants.{_slug(key)}",
            f"{key.replace('_', ' ').capitalize()} situation: {value}.",
            f"social_determinants[{key}]")

    for goal in dna.goals:
        add(f"goals.{_slug(goal)}", f"Something you want: {goal}", f"goals[{goal}]")

    for constraint in dna.constraints:
        add(f"constraints.{_slug(constraint)}",
            f"Something you cannot change: {constraint}",
            f"constraints[{constraint}]")

    return facts


def _severity_band(severity: float) -> str:
    """Words, not a percentage — the model reads this text and may echo it.

    A persona saying "transport is a 62% problem for me" is the register failure
    the whole narration layer exists to avoid.
    """
    if severity >= 0.66:
        return "a major problem"
    if severity >= 0.33:
        return "a real problem"
    return "a minor problem"


def _barrier_facts(dna: PatientDNA) -> list[StateFact]:
    """One id per derived barrier, worst first.

    A barrier and the profile field it came from are an ALTERNATION, not a
    conjunction: citing `B-transport` or its origin `P-social_determinants.
    transport` both ground the same claim. That is why `origin` travels with the
    fact rather than being reconstructed by whoever reads the citation.
    """
    facts: list[StateFact] = []
    taken: set[str] = set()
    for barrier in sorted(dna.barriers, key=lambda b: (-b.severity, b.name)):
        text = (
            f"{barrier.name.replace('_', ' ').capitalize()} gets in your way — "
            f"{_severity_band(barrier.severity)} for you."
        )
        facts.append(StateFact(
            id=_unique(taken, f"B-{_slug(barrier.name)}"),
            text=text,
            namespace="B",
            origin=barrier.origin,
            detail=barrier.note,
        ))
    return facts


def _journey_facts(dna: PatientDNA) -> list[StateFact]:
    """One id per milestone, in journey order. Repeats get a stable suffix."""
    facts: list[StateFact] = []
    taken: set[str] = set()
    for milestone in dna.journey:
        opening = _MILESTONE_PHRASING.get(
            milestone.stage, milestone.stage.replace("_", " ").capitalize()
        )
        when = f" on {milestone.when.isoformat()}" if milestone.when else ""
        text = f"{opening}{when}."
        if milestone.note:
            text += f" {milestone.note}"
        facts.append(StateFact(
            id=_unique(taken, f"J-{_slug(milestone.stage)}"),
            text=text,
            namespace="J",
            origin=f"journey[{milestone.stage}]",
            detail=milestone.note,
        ))
    return facts


def derive_state_facts(dna: PatientDNA) -> StateCitations:
    """Pure function: a persona in, its citable state out. No I/O, no clock, no RNG.

    Takes no `PersonaState` on purpose — event-log state is the `E-` namespace,
    which is reserved and unpopulated. See the module docstring.
    """
    facts = _profile_facts(dna) + _barrier_facts(dna) + _journey_facts(dna)
    return StateCitations(persona_id=dna.patient_id, facts=tuple(facts))


class StateDetail(BaseModel):
    """One state id expanded for citation click-through.

    The counterpart to `knowledge.FactDetail`, and deliberately a different
    model: that one walks a graph and carries neighbours, this one names a field
    of one specific persona. `kind` distinguishes them for a caller that receives
    either from the same endpoint — which is only unambiguous because the
    namespaces were split four ways rather than three.
    """

    id: str
    text: str
    kind: str = "persona_state"
    namespace: str
    namespace_meaning: str
    origin: str
    note: str = ""
    persona_id: str
    simulation_link: dict | None = None


def state_detail(dna: PatientDNA, state_id: str) -> StateDetail | None:
    """Expand one state id for citation click-through.

    For a `B-` id this closes the loop the room's badge work opened: cited id ->
    the persona's derived barrier -> the profile field the simulation derived it
    from. It never fabricates a link the persona does not have.
    """
    citations = derive_state_facts(dna)
    fact = citations.by_id(state_id)
    if fact is None:
        return None

    link = None
    if fact.namespace == "B":
        name = fact.id.partition("-")[2]
        barrier = next((b for b in dna.barriers if _slug(b.name) == name), None)
        if barrier is not None:
            link = {
                "kind": "derived_barrier",
                "barrier": barrier.name,
                "severity": barrier.severity,
                "origin": barrier.origin,
                "explanation": (
                    f"{barrier.name!r} is derived, not declared: the simulation "
                    f"computed it from {barrier.origin}. Citing this id or citing "
                    "that profile field ground the same claim — they are an "
                    "alternation, not two separate requirements."
                ),
            }

    return StateDetail(
        id=fact.id,
        text=fact.text,
        namespace=fact.namespace,
        namespace_meaning=NAMESPACE_MEANING[fact.namespace],
        origin=fact.origin,
        note=fact.detail,
        persona_id=dna.patient_id,
        simulation_link=link,
    )
