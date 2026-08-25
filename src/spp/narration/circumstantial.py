"""`is_circumstantial` v2 — the denominator of `state_coverage`, defined from the
namespace semantics instead of from grammar.

v1 asks: *is this first person, and does it mention concrete-world vocabulary?*
That is deliberately over-inclusive — its docstring says so, and erring toward a
larger denominator makes the bar harder, which is the right direction to be wrong
in. Reading the v0.4 miss showed what it costs: of the 18 circumstantial segments
carrying no state id, roughly nine were first-person **clinical** claims —

    "For the metformin, I need to do fasting blood tests"   cites F067, F001

— which assert a property of a *drug*, cite the graph fact that supports it, and
have no state fact that could. Counting them against `state_coverage` charges the
model for not citing an id that would not have been correct. That is about half
the v0.4 miss, and it is an instrument fault, not a model one.

**The v2 definition, from principle:** a segment is circumstantial iff it asserts
something *only this persona's own state could support*. Operationally, it must
be first person AND carry at least one content term that appears in this
persona's `P-`/`B-`/`J-` fact texts and in **none** of the graph facts this case
was offered. A term the graph can support is not evidence of state-groundability;
first-person grammar alone is not either.

That rule is derivable from what the namespaces already mean — `state_coverage`
asks whether a claim *needing* a state id got one, and a claim whose every content
term is also in the offered graph surface does not need one. It was written from
`state_facts.PROFILE_FIELDS` and the offered-fact contract, not from the segment
texts it will be scored on.

**NOT YET VALIDATED.** This module deliberately does not replace v1. A classifier
tuned until it agrees with a reading of the run it will score is fitted, not
defined, and the whole point of the v3 pre-registration was to make that
impossible to do accidentally. Validation is blind labels authored against the
state dumps, scored against the classifier — never the reverse. Until those exist,
any number produced here is an *instrument correction under review* and must be
reported beside v1's, never instead of it.
"""
from __future__ import annotations

import re

from ..knowledge.graph import KnowledgeGraph
from .state_facts import StateCitations

_FIRST_PERSON = re.compile(r"\b(i|i'm|i've|i'd|my|mine|me|we|our|us)\b")
_WORD = re.compile(r"[a-z]+")

# Function words and narration scaffolding. Not a tuned list: these carry no
# claim, so a segment sharing only these with the state surface asserts nothing
# about the persona. Kept explicit rather than pulled from a dependency, both to
# avoid a new one and so the contents are reviewable in the diff.
_STOPWORDS: frozenset[str] = frozenset("""
about also always another anything are away back been before being both
but came can cannot come could does doing done down each else even ever
every from gets going gone good great had has have here how into its
just keep know like little long make many might more most much must need
needs never next not now off often once one only other out over own
part particular really right said same see seem should since some something
sometimes still such sure take takes tell than that the their them then there
these they thing things think this those though through time too under
until upon used using very want was way well were what when where which
while who why will with within without would you your yours
""".split())

_MIN_LENGTH = 4


def _tokens(text: str) -> set[str]:
    """Content terms, crudely singularised.

    Singularisation is a trailing `s` strip, not a stemmer. A stemmer is a
    dependency and a source of surprises; the failure mode here is a missed match
    ("appointments" vs "appointment" is handled, "families" vs "family" is not),
    which shrinks the denominator rather than inflating it — the same direction of
    error v1 chose, and the safe one.
    """
    found = set()
    for word in _WORD.findall((text or "").casefold()):
        if len(word) < _MIN_LENGTH or word in _STOPWORDS:
            continue
        found.add(word[:-1] if word.endswith("s") and len(word) > _MIN_LENGTH else word)
    return found


def state_only_vocabulary(
    state: StateCitations,
    graph: KnowledgeGraph,
    offered_fact_ids: list[str] | tuple[str, ...],
) -> frozenset[str]:
    """Terms this persona's state can support that the offered graph facts cannot.

    The subtraction is the whole definition. `transport` appearing in both a
    persona's `B-transport_fragile` and a retrieved mitigation fact is ambiguous
    evidence, so it is not evidence: it leaves the vocabulary and a segment
    mentioning only it is not counted circumstantial. That errs toward a SMALLER
    denominator, which is the opposite of v1's bias — stated here rather than
    discovered later, because it means v2 cannot be compared to v1 as though the
    two were measuring the same population.
    """
    state_terms: set[str] = set()
    for fact in state.facts:
        state_terms |= _tokens(fact.text)
        state_terms |= _tokens(fact.detail)
        state_terms |= _tokens(fact.origin)

    graph_terms: set[str] = set()
    for fact_id in offered_fact_ids:
        if graph.has_fact(fact_id):
            graph_terms |= _tokens(graph.render(graph.fact(fact_id)))

    return frozenset(state_terms - graph_terms)


def is_circumstantial_v2(text: str, distinctive: frozenset[str]) -> bool:
    """First person, and asserting something only the state surface supports."""
    lowered = (text or "").casefold()
    if not _FIRST_PERSON.search(lowered):
        return False
    return bool(_tokens(lowered) & distinctive)


def coverage_split(
    circumstantial: list[tuple[bool, bool]],
) -> tuple[float, float]:
    """`(state_coverage, schema_gap_rate)` over `(cited_state, coverable)` pairs.

    Two numbers, never one — pre-registered in `tests/eval/instrument_v2_gate.json`
    before any label existed, and derived from principle rather than from the
    segments that raised it: **a coverage metric computed over segments nothing in
    the schema can express measures the schema, not the model.** Blended, the
    figure falls when the model gets worse and equally when the declared surface
    gets narrower, and afterwards cannot say which happened.

    The known uncoverable class is **symptoms**. `PROFILE_FIELDS` does not carry
    them and biomarkers are deliberately outside it, so *"I feel breathless most
    days"* asserts a circumstance with no id available to cite. Charging that to
    the model would be the mirror of the clinical-claim false positive this
    instrument was written to remove.

    `coverable` is adjudicated by the blind labels, not by this module: the rater
    labels the concept, the classifier approximates it. Passing every segment as
    coverable reproduces the single-number metric exactly, which is what makes the
    split safe to introduce before the labels arrive.
    """
    if not circumstantial:
        return 0.0, 0.0

    coverable = [cited for cited, is_coverable in circumstantial if is_coverable]
    gap = len(circumstantial) - len(coverable)

    state_coverage = (
        round(sum(1 for cited in coverable if cited) / len(coverable), 4)
        if coverable else 0.0
    )
    return state_coverage, round(gap / len(circumstantial), 4)
