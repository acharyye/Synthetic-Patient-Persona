"""Panel mode: the LLM speaks, code decides who speaks.

The moderator is a deterministic state machine. Turn order, speaker selection,
when to probe, and when to stop are all decided in Python from the transcript so
far; the model only fills in each turn's content, under the same citation
discipline as a single interview. A panel where an LLM also chose the running
order would be unreproducible for no benefit.

Theme extraction then needs no clustering to be trustworthy. Every statement
already carries persona ids and cited fact ids, so themes group by **cited-fact
overlap** — mechanically. "3 of 6 personas flagged travel burden" becomes a count
over citations rather than a judgement call, which is exactly what makes a
transcript survive a design review. An LLM may write a summary sentence on top of
a mechanically attributed group; it may not decide the grouping.
"""
from __future__ import annotations

from pydantic import BaseModel, Field

from ..assumptions import PANEL_SPEAKING_ORDER
from ..foundation.events import EventLog
from ..knowledge.graph import KnowledgeGraph, load_graph
from ..schemas import PatientDNA
from .interview import InterviewTurn, interview


class PanelStatement(BaseModel):
    """One persona's turn in the transcript."""

    order: int
    patient_id: str
    prompt: str
    text: str
    cited_fact_ids: list[str] = Field(default_factory=list)
    grounded: bool = True
    is_probe: bool = False


class Theme(BaseModel):
    """A group of statements sharing cited facts. Attribution is mechanical."""

    id: str
    label: str
    fact_ids: list[str] = Field(default_factory=list)
    patient_ids: list[str] = Field(default_factory=list)
    statement_orders: list[int] = Field(default_factory=list)

    @property
    def support(self) -> int:
        return len(self.patient_ids)

    def headline(self, panel_size: int) -> str:
        return f"{self.support} of {panel_size} personas raised {self.label}"


class PanelTranscript(BaseModel):
    topic: str
    panel_size: int
    statements: list[PanelStatement] = Field(default_factory=list)
    themes: list[Theme] = Field(default_factory=list)
    probes: list[str] = Field(default_factory=list)

    def ungrounded(self) -> list[PanelStatement]:
        return [s for s in self.statements if not s.grounded]

    def render(self) -> str:
        lines = [f"PANEL: {self.topic}", ""]
        for statement in self.statements:
            marker = "  [probe] " if statement.is_probe else "  "
            lines.append(f"{marker}{statement.patient_id}: {statement.text}")
        if self.themes:
            lines.append("")
            lines.append("THEMES (grouped by shared citations, not by judgement):")
            for theme in self.themes:
                lines.append(f"  - {theme.headline(self.panel_size)} "
                             f"[{', '.join(theme.fact_ids[:3])}]")
        return "\n".join(lines)


# -- the deterministic moderator -------------------------------------------

def speaking_order(panel: list[PatientDNA]) -> list[PatientDNA]:
    """Deterministic order: highest barrier load first.

    Not arbitrary — the personas with most in their way have the most to say
    about a design, and putting them first means a truncated session still
    contains the signal.
    """
    return sorted(panel, key=lambda dna: (-dna.barrier_load, dna.patient_id))


def should_probe(statements: list[PanelStatement], min_overlap: int = 2) -> str | None:
    """Decide whether the moderator interjects, and about what.

    Trigger: two or more personas have cited the same fact. That is a shared
    concern worth pushing on, and it is detectable without reading the prose.
    Returns the fact id to probe, or None.
    """
    seen: dict[str, set[str]] = {}
    for statement in statements:
        for fact_id in statement.cited_fact_ids:
            seen.setdefault(fact_id, set()).add(statement.patient_id)

    contested = [
        fact_id for fact_id, people in sorted(seen.items())
        if len(people) >= min_overlap
    ]
    return contested[0] if contested else None


def probe_question(graph: KnowledgeGraph, fact_id: str, topic: str) -> str:
    """The moderator's follow-up, built from the fact everyone converged on."""
    try:
        text = graph.render(graph.fact(fact_id))
    except KeyError:
        text = "that point"
    return (
        f"Several of you have raised the same thing — {text}. "
        f"For {topic}, what would actually have to change there?"
    )


def extract_themes(statements: list[PanelStatement], graph: KnowledgeGraph) -> list[Theme]:
    """Group statements by shared cited facts. No clustering, no judgement.

    Grouping key is the fact itself, so a theme's membership is a fact of the
    transcript rather than an interpretation of it. The label comes from the
    graph, not from a model.
    """
    by_fact: dict[str, tuple[set[str], set[int]]] = {}
    for statement in statements:
        for fact_id in statement.cited_fact_ids:
            people, orders = by_fact.setdefault(fact_id, (set(), set()))
            people.add(statement.patient_id)
            orders.add(statement.order)

    themes: list[Theme] = []
    for index, (fact_id, (people, orders)) in enumerate(
        sorted(by_fact.items(), key=lambda kv: (-len(kv[1][0]), kv[0]))
    ):
        if len(people) < 2:
            continue  # a theme needs more than one voice
        try:
            fact = graph.fact(fact_id)
            label = graph.render(fact)
            # Prefer naming the barrier or resource — the actionable end.
            for endpoint in (fact.object, fact.subject):
                if endpoint.startswith(("barrier:", "res:")):
                    label = graph.node(endpoint).name
                    break
        except KeyError:
            label = fact_id

        themes.append(Theme(
            id=f"T{index + 1}",
            label=label,
            fact_ids=[fact_id],
            patient_ids=sorted(people),
            statement_orders=sorted(orders),
        ))
    return themes


def run_panel(
    panel: list[PatientDNA],
    topic: str,
    graph: KnowledgeGraph | None = None,
    logs: dict[str, EventLog] | None = None,
    generate=None,
    probe_after: int | None = None,
    max_probes: int | None = None,
) -> PanelTranscript:
    """Run a focus group. Every scheduling decision here is deterministic."""
    graph = graph if graph is not None else load_graph()
    settings = PANEL_SPEAKING_ORDER.params
    probe_after = settings["probe_after"] if probe_after is None else probe_after
    max_probes = settings["max_probes"] if max_probes is None else max_probes
    statements: list[PanelStatement] = []
    probes: list[str] = []
    order = 0

    def speak(dna: PatientDNA, question: str, is_probe: bool) -> None:
        nonlocal order
        turn: InterviewTurn = interview(
            dna, question, graph=graph,
            log=(logs or {}).get(dna.patient_id),
            generate=generate,
        )
        statements.append(PanelStatement(
            order=order, patient_id=dna.patient_id, prompt=question,
            text=turn.answer, cited_fact_ids=turn.cited_fact_ids,
            grounded=turn.grounded, is_probe=is_probe,
        ))
        order += 1

    ordered = speaking_order(panel)
    for index, dna in enumerate(ordered):
        speak(dna, topic, is_probe=False)

        # Moderator interjects once a shared concern has surfaced, and only a
        # bounded number of times — a state machine, not a conversation.
        if (index + 1) % probe_after == 0 and len(probes) < max_probes:
            fact_id = should_probe(statements)
            if fact_id:
                question = probe_question(graph, fact_id, topic)
                probes.append(question)
                for responder in ordered[: min(2, len(ordered))]:
                    speak(responder, question, is_probe=True)

    return PanelTranscript(
        topic=topic,
        panel_size=len(panel),
        statements=statements,
        themes=extract_themes(statements, graph),
        probes=probes,
    )
