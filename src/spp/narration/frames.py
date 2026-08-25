"""v2.2 — five assertion frames, derived from the rater's committed rules.

v2.1 had ONE frame, possession, and its two validated failure classes were both
circumstance asserted through a frame it did not have. Three independent
sightings of one gap: eight held-out misses, three in-sample, and the canary
fixture (*"I cannot always get myself to the clinic"* — an ability claim) which
v2.1 scored as containing no circumstantial segment at all.

The inventory is not read off those misses. R1-R5 and BA1-BA3 already name the
frames; the misses only established that the inventory was short.

| frame | rule | fixture |
|---|---|---|
| possession | R1 explicit branch, BA3 | *I take X* |
| experience | R3, BA2 indicative branch | *makes me feel Y* |
| ability | R5 (own capability asserted) | *I cannot get myself to Z* |
| situation | R5 allusion, first person NOT required | *the site is far from me* |
| negated resource | R4 (grounding circumstance asserted) | *I don't have a car* |

Two suppressions, both stated by the rules rather than discovered:

* **modal talk is knowledge, not experience** (BA2). *"can make me feel tired"*
  is a property of a drug; *"makes me feel tired"* is a fact about the speaker.
* **a bare temporal locator does not assert** (BA1). *"during my work hours"*
  presupposes employment and asserts nothing about it, while *"my work schedule
  makes it hard"* asserts the conflict. Implemented narrowly as a temporal
  preposition governing a possessive time phrase — the one form BA1 names.

**Not validated.** Both existing sheets are in-sample for this module by
construction. Adoption needs the v1-era sheet nobody has labelled.
"""
from __future__ import annotations

import re

from .circumstantial import _MIN_LENGTH, _STOPWORDS, tokens_of

_FIRST_PERSON = re.compile(r"\b(i|i'm|i've|i'd|my|mine|me|we|our|us)\b")

# A modal before the verb makes the clause about what a thing CAN do, not about
# what happened to the speaker. BA2's boundary, in one regex.
_MODAL = re.compile(r"\b(can|could|might|may|would|should)\b")

# BA1: "during my work hours" locates an event in time. It presupposes the
# employment; it does not assert it.
_TEMPORAL_LOCATOR = re.compile(
    r"\b(during|in|at|on)\s+(my|our|the)\s+(\w+\s+)?"
    r"(hour|hours|time|times|day|days|week|weeks|shift|shifts|morning|evening)\b"
)

# `(?!\s+to\b)` is the obligation exclusion: "I have to go in person" wears
# possession's verb and asserts a protocol requirement. Without it the frame
# swallows the protocol vocabulary, which is how v2.1 nearly collapsed into v1.
_POSSESSION = re.compile(
    r"\b(i\s+(take|took|use|used|keep|own|get|got)|"
    r"i\s+(have|had)(?!\s+to\b)|"
    r"i'm\s+(taking|using|on)|i\s+am\s+(taking|using|on)|"
    r"i've\s+(taken|used|got|had)|my|our|mine)\b"
)
_EXPERIENCE = re.compile(
    r"\b(makes?\s+me|gives?\s+me|leaves?\s+me|"
    r"i\s+(feel|felt|get|got|wake|notice|find)|i'm\s+(feeling|getting))\b"
)
_ABILITY = re.compile(
    r"\b(i\s+(can't|cannot|couldn't|struggle|manage|can)|"
    r"i'm\s+(able|unable)|hard\s+for\s+me|tough\s+for\s+me|"
    r"tiring\s+for\s+me|difficult\s+for\s+me|easy\s+for\s+me)\b"
)
_SITUATION = re.compile(
    r"\b(the\s+site|the\s+clinic|the\s+hospital|getting\s+there|"
    r"get\s+there|journey|each\s+way|live[sd]?\s+(far|rural)|"
    r"far\s+(away|from)|long\s+way)\b"
)
_NEGATED_RESOURCE = re.compile(
    r"\b(don't\s+have|do\s+not\s+have|haven't\s+got|no\s+one|nobody|"
    r"can't\s+afford|cannot\s+afford|there's\s+no|there\s+is\s+no|"
    r"without\s+(a|any|reliable))\b"
)

FRAMES: dict[str, re.Pattern[str]] = {
    "possession": _POSSESSION,
    "experience": _EXPERIENCE,
    "ability": _ABILITY,
    "situation": _SITUATION,
    "negated_resource": _NEGATED_RESOURCE,
}

# possession and experience frame a TERM, so what they frame must be state
# vocabulary. The other three assert a circumstance in themselves — an inability,
# a distance, an absent resource — and are speaker-relative by construction.
_TERM_FRAMES = ("possession", "experience")
_WINDOW = 8


def frames_firing(text: str) -> set[str]:
    """Which of the five frames this segment carries. Diagnostic and testable."""
    lowered = " ".join((text or "").casefold().split())
    firing = set()
    for name, pattern in FRAMES.items():
        if not pattern.search(lowered):
            continue
        if name == "experience" and _MODAL.search(lowered):
            continue                      # BA2: knowledge, not experience
        if name == "possession" and _is_only_a_locator(lowered):
            continue                      # BA1: presupposes, does not assert
        firing.add(name)
    return firing


def _is_only_a_locator(lowered: str) -> bool:
    """True when the sole possession marker is a temporal locator phrase."""
    if not _TEMPORAL_LOCATOR.search(lowered):
        return False
    stripped = _TEMPORAL_LOCATOR.sub(" ", lowered)
    return not _POSSESSION.search(stripped)


def framed_terms(text: str) -> set[str]:
    """Content terms sitting inside a possession or experience frame."""
    lowered = " ".join((text or "").casefold().split())
    words = re.findall(r"[a-z']+", lowered)
    found: set[str] = set()
    for name in _TERM_FRAMES:
        for match in FRAMES[name].finditer(lowered):
            after = lowered[match.end():]
            for word in re.findall(r"[a-z]+", after)[:_WINDOW]:
                if len(word) < _MIN_LENGTH or word in _STOPWORDS:
                    continue
                found.add(word[:-1] if word.endswith("s") and len(word) > _MIN_LENGTH
                          else word)
    return found or set(words) & set()


def is_circumstantial_v22(
    text: str, state_terms: frozenset[str], graph_terms: frozenset[str]
) -> bool:
    """Circumstantial iff a frame asserts something about the speaker.

    Three of the five frames are self-asserting: an inability, a distance, an
    absent resource is a circumstance whoever holds it. Possession and experience
    frame a TERM, so that term must belong to the persona's own state surface —
    otherwise *"I take the bus every morning"* and *"I take offence"* score alike.

    The v2 subtraction survives as a third path, for circumstance stated with no
    frame at all: a term this persona's state carries and no offered graph fact
    does is evidence on its own.
    """
    lowered = " ".join((text or "").casefold().split())
    firing = frames_firing(lowered)
    if not firing:
        return False

    if firing - set(_TERM_FRAMES):
        # ability / situation / negated_resource: speaker-relative in themselves.
        # Situation alone still wants a speaker in the sentence or a state term,
        # because "the clinic is open late" is not about anyone.
        if firing - set(_TERM_FRAMES) != {"situation"}:
            return True
        if _FIRST_PERSON.search(lowered) or (tokens_of(lowered) & state_terms):
            return True

    if tokens_of(lowered) & (state_terms - graph_terms):
        return True
    return bool(framed_terms(lowered) & state_terms)
