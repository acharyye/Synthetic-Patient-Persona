"""Structured generation: citations are a decode constraint, not a prompt hope.

Asking a model for prose with inline `[F017]` and checking afterwards makes
citation compliance a behavioural property you have to measure and re-measure per
model. Inverting it removes most of the problem instead:

    the model emits   {"segments": [{"text": ..., "kind": ..., "fact_ids": [...]}]}
    prose rendering   is done in code, here

Two consequences worth being precise about:

  * **Malformed citations become impossible**, not merely detectable. Ollama (and
    the Anthropic API, differently) support JSON-schema-constrained decoding, and
    `fact_ids` is constrained to an **enum of exactly the retrieved ids**. A
    fabricated `F999` cannot be emitted, because it is not in the grammar.
  * **What is left is a relevance problem, not a format problem.** The model can
    still attach the wrong fact to a claim. That is what the gate and the
    compliance eval are for, and it is a much smaller and more interesting
    target than malformed output.

The cost is some naturalness at segment boundaries: prose assembled from typed
segments reads a little more clipped than free generation. For a tool whose
entire aesthetic is provenance, that is the right trade.

Defence in depth: the enum only binds if the backend honours the schema. The
structural gate below runs regardless, so a backend that ignores `format` fails
loudly rather than silently degrading to unchecked prose.
"""
from __future__ import annotations

import json
from typing import Any, Literal

from pydantic import BaseModel, Field

SegmentKind = Literal["factual", "feeling"]


class Segment(BaseModel):
    """One clause of an answer, typed by whether it asserts anything."""

    text: str
    kind: SegmentKind
    fact_ids: list[str] = Field(default_factory=list)

    @property
    def needs_citation(self) -> bool:
        return self.kind == "factual"


class StructuredAnswer(BaseModel):
    """The generation contract. Prose is derived from this, never the reverse."""

    segments: list[Segment] = Field(default_factory=list)

    @property
    def cited_fact_ids(self) -> list[str]:
        seen: list[str] = []
        for segment in self.segments:
            for fact_id in segment.fact_ids:
                if fact_id not in seen:
                    seen.append(fact_id)
        return seen

    def render(self, with_citations: bool = True) -> str:
        """Assemble prose. This is code, which is the whole point."""
        parts: list[str] = []
        for segment in self.segments:
            text = segment.text.strip()
            if not text:
                continue
            if with_citations and segment.fact_ids:
                text = f"{text} [{', '.join(segment.fact_ids)}]"
            parts.append(text)
        return " ".join(parts)


def answer_schema(allowed_fact_ids: frozenset[str]) -> dict[str, Any]:
    """JSON schema for constrained decoding.

    `fact_ids` is an enum over exactly the ids retrieval offered, so a
    hallucinated citation is ungrammatical rather than merely wrong. When nothing
    was retrieved the enum would be empty (invalid schema), so the field
    collapses to an empty-array constraint — the persona can only say it does not
    know, which is the correct behaviour for an unanchored question.
    """
    ids = sorted(allowed_fact_ids)
    fact_ids_schema: dict[str, Any] = (
        {"type": "array", "items": {"type": "string", "enum": ids}}
        if ids
        else {"type": "array", "items": {"type": "string"}, "maxItems": 0}
    )
    return {
        "type": "object",
        "properties": {
            "segments": {
                "type": "array",
                "minItems": 1,
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "kind": {"type": "string", "enum": ["factual", "feeling"]},
                        "fact_ids": fact_ids_schema,
                    },
                    "required": ["text", "kind", "fact_ids"],
                },
            }
        },
        "required": ["segments"],
    }


class StructuredCheck(BaseModel):
    """What survives once format failures are impossible by construction."""

    ok: bool
    cited: list[str] = Field(default_factory=list)
    unknown_citations: list[str] = Field(default_factory=list)
    uncited_factual: list[str] = Field(default_factory=list)
    empty: bool = False

    @property
    def summary(self) -> str:
        if self.ok:
            return f"grounded ({len(self.cited)} citations)"
        problems = []
        if self.empty:
            problems.append("no segments returned")
        if self.unknown_citations:
            problems.append(f"citations not in context: {self.unknown_citations}")
        if self.uncited_factual:
            problems.append(f"{len(self.uncited_factual)} factual segment(s) uncited")
        return "; ".join(problems)


def check_structured(
    answer: StructuredAnswer, allowed: frozenset[str]
) -> StructuredCheck:
    """The shrunken gate: existence and coverage. No sentence heuristics needed.

    Segment `kind` is declared by the model rather than inferred by regex, which
    removes the fuzziest part of the text-based checker. A model that mislabels a
    factual claim as a feeling to dodge citing it is a *relevance* failure the
    compliance eval measures — not something to guess at here.
    """
    if not answer.segments:
        return StructuredCheck(ok=False, empty=True)

    cited = answer.cited_fact_ids
    unknown = [fact_id for fact_id in cited if fact_id not in allowed]
    uncited = [
        segment.text
        for segment in answer.segments
        if segment.needs_citation and not segment.fact_ids
    ]
    return StructuredCheck(
        ok=not unknown and not uncited,
        cited=cited,
        unknown_citations=unknown,
        uncited_factual=uncited,
    )


def parse_structured(payload: str | dict) -> StructuredAnswer | None:
    """Parse a model response. Returns None rather than raising on garbage."""
    if isinstance(payload, dict):
        data = payload
    else:
        text = (payload or "").strip()
        if text.startswith("```"):
            parts = text.split("```")
            text = parts[1] if len(parts) > 1 else text
            if text.lower().startswith("json"):
                text = text[4:]
        try:
            data = json.loads(text.strip())
        except json.JSONDecodeError:
            return None
    if not isinstance(data, dict):
        return None
    try:
        return StructuredAnswer.model_validate(data)
    except Exception:
        return None


def structured_repair_instruction(check: StructuredCheck) -> str:
    """The one permitted corrective nudge."""
    parts = ["Your previous answer did not satisfy the grounding contract."]
    if check.empty:
        parts.append("You returned no segments. Return at least one.")
    if check.unknown_citations:
        parts.append(
            f"These fact ids were not in the provided context and must not be "
            f"used: {', '.join(check.unknown_citations)}."
        )
    if check.uncited_factual:
        parts.append(
            "Every segment with kind='factual' must list at least one fact id "
            f"from the context. This one had none: \"{check.uncited_factual[0]}\". "
            "Either cite a fact for it, or mark it kind='feeling' if it is about "
            "how you feel rather than a claim about the world."
        )
    parts.append("Return the corrected JSON object only.")
    return " ".join(parts)
