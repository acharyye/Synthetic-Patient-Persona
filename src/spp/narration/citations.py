"""Mechanical citation verification. No LLM judges an LLM here.

The obvious design — extract claims with a model, then verify them with a model —
puts a judge in the runtime path: slow, circular, and impossible to test offline.
Inverted here: generation is *constrained to cite inline*, so verification
becomes ordinary code.

Two deterministic checks:

  1. **Every cited id was offered.** A citation outside the retrieval result's
     allowlist is a hallucinated reference — the clearest possible signal.
  2. **Every factual sentence carries a citation.** Sentence-level, using a
     conservative heuristic for what counts as a factual assertion: first-person
     feeling and preference sentences are exempt, assertions about the condition,
     treatment or logistics are not.

Check 2's heuristic is the fuzzy part, and it is deliberately biased toward
*permitting* — a false accusation would trigger pointless regeneration, while a
missed uncited sentence still cannot contain a fabricated fact id. The fuzzy
claim-extraction pipeline still exists, but as an OFFLINE EVAL scoring cassettes,
never as a runtime gate.

Retry is capped at one. A retry loop that keeps going until something passes is
the narration-layer equivalent of a leaked perturbation: it hides a model that
will not ground, and turns a measurable compliance rate into an invisible one.
"""
from __future__ import annotations

import re

from pydantic import BaseModel, Field

from .state_facts import STATE_ID_PATTERN

# [F012], [F012, F031], [B-transport] — graph ids and state ids alike, since
# both are citation handles and both may show up in a text-path answer.
_ANY_ID = rf"(?:F\d+|{STATE_ID_PATTERN})"
CITATION_RE = re.compile(rf"\[({_ANY_ID}(?:\s*,\s*{_ANY_ID})*)\]")
_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")

# Sentences that are clearly about the speaker's inner life need no citation.
_EXEMPT_OPENERS = (
    "i feel", "i felt", "i worry", "i worried", "i'm worried", "i am worried",
    "i think", "i thought", "i hope", "i'd like", "i would like", "i want",
    "i don't know", "i do not know", "i'm not sure", "i am not sure",
    "honestly", "to be honest", "it's hard", "it is hard", "i suppose",
    "i just", "i can't", "i cannot", "i wish", "my worry", "that scares",
    "i'd need", "i would need", "i'm tired", "i am tired",
)

# Words that mark an assertion about the world rather than about a feeling.
# Public because the compliance eval reuses this vocabulary to decide which
# segments are CIRCUMSTANTIAL; two copies of it would drift.
FACTUAL_MARKERS = (
    "medication", "tablet", "drug", "dose", "treatment", "side effect",
    "symptom", "diagnos", "condition", "clinic", "appointment", "visit",
    "blood", "scan", "test", "study", "trial", "nurse", "doctor",
    "transport", "travel", "cost", "diary", "monitor", "fasting",
)


class CitationIssue(BaseModel):
    kind: str
    detail: str
    sentence: str = ""


class CitationCheck(BaseModel):
    """Result of verifying one generated answer."""

    ok: bool
    cited: list[str] = Field(default_factory=list)
    unknown_citations: list[str] = Field(default_factory=list)
    uncited_sentences: list[str] = Field(default_factory=list)
    issues: list[CitationIssue] = Field(default_factory=list)

    @property
    def summary(self) -> str:
        if self.ok:
            return f"grounded ({len(self.cited)} citations)"
        return "; ".join(issue.detail for issue in self.issues)


class GroundingFailure(RuntimeError):
    """Generation could not be grounded within the retry budget.

    Surfaced rather than swallowed: a persona whose answer cannot be verified is
    a result the caller must see, not one to paper over with a fallback.
    """

    def __init__(self, check: CitationCheck, attempts: int) -> None:
        super().__init__(
            f"answer failed citation checks after {attempts} attempt(s): {check.summary}"
        )
        self.check = check
        self.attempts = attempts


def extract_citations(text: str) -> list[str]:
    """All fact ids cited, in order of first appearance."""
    found: list[str] = []
    for match in CITATION_RE.finditer(text):
        for fact_id in match.group(1).split(","):
            fact_id = fact_id.strip()
            if fact_id not in found:
                found.append(fact_id)
    return found


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENTENCE_RE.split(text.strip()) if s.strip()]


def is_factual(sentence: str) -> bool:
    """Conservative: only sentences that look like assertions about the world.

    Biased toward permitting. A false positive causes a pointless regeneration; a
    false negative still cannot let a fabricated id through, because check 1
    catches those independently.
    """
    lowered = sentence.strip().lower().lstrip("-–— ")
    if any(lowered.startswith(opener) for opener in _EXEMPT_OPENERS):
        return False
    if lowered.endswith("?"):
        return False
    return any(marker in lowered for marker in FACTUAL_MARKERS)


def strip_citations(text: str) -> str:
    """The answer as a reader should see it, citations removed."""
    return re.sub(r"\s*" + CITATION_RE.pattern, "", text).strip()


def check_citations(text: str, allowed: frozenset[str]) -> CitationCheck:
    """Verify an answer against the exact fact ids it was offered."""
    cited = extract_citations(text)
    unknown = [fact_id for fact_id in cited if fact_id not in allowed]

    uncited: list[str] = []
    for sentence in split_sentences(text):
        if is_factual(sentence) and not CITATION_RE.search(sentence):
            uncited.append(sentence)

    issues: list[CitationIssue] = []
    if unknown:
        issues.append(CitationIssue(
            kind="unknown_citation",
            detail=f"cited fact ids that were never provided: {unknown}",
        ))
    for sentence in uncited:
        issues.append(CitationIssue(
            kind="uncited_claim",
            detail="factual sentence without a citation",
            sentence=sentence,
        ))

    return CitationCheck(
        ok=not issues,
        cited=cited,
        unknown_citations=unknown,
        uncited_sentences=uncited,
        issues=issues,
    )


def repair_instruction(check: CitationCheck) -> str:
    """The single corrective nudge used for the one permitted retry."""
    parts = ["Your previous answer broke the citation rules."]
    if check.unknown_citations:
        parts.append(
            f"These ids were in neither GROUNDED FACTS nor ABOUT YOU and must "
            f"not appear: {', '.join(check.unknown_citations)}."
        )
    if check.uncited_sentences:
        example = check.uncited_sentences[0]
        parts.append(
            "Every sentence stating a fact must end with a citation like [F012]. "
            f"This one did not: \"{example}\""
        )
    parts.append(
        "Rewrite the answer. Use only the listed ids. If a fact is not listed, "
        "say you do not know instead of stating it."
    )
    return " ".join(parts)
