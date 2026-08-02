"""Assumption ledger: every heuristic in the system, registered and versioned.

This project is full of numbers that are judgement rather than measurement —
adherence coefficients, burden weights, epidemiological priors, dropout hazards.
Left in code they are a liability ("your heuristics are made up"). Registered
here, with a source and a confidence tag, they become an auditable feature: any
exported result can carry the exact assumption set that produced it, and
sensitivity analysis has something concrete to perturb.

The rule this enforces: **no magic number in simulation code.** If a coefficient
influences an outcome, it is registered here and read from here.

    ADHERENCE = ledger.register(Assumption(
        name="adherence.literacy_effect",
        params={"low": -0.14, "medium": 0.0, "high": 0.07},
        source="expert guess informed by adherence literature",
        confidence=Confidence.EXPERT_GUESS,
    ))
    ...
    delta = ADHERENCE.params[literacy]
"""
from __future__ import annotations

from enum import Enum
from typing import Any, Iterator

from pydantic import BaseModel, Field


# Bumped when assumption NAMES change meaning or shape — notably the Phase 5
# domain namespacing (`timeline.dropout_hazard` -> `clinical.timeline...`).
# Stamped into every evidence bundle so an older bundle's assumption references
# stay resolvable through an alias table rather than by courtesy.
LEDGER_SCHEMA_VERSION = 1


class Confidence(str, Enum):
    """How much weight an assumption can bear. Ordered weakest to strongest."""

    EXPERT_GUESS = "expert_guess"
    PUBLISHED_AGGREGATE = "published_aggregate"
    TUNED = "tuned"
    MEASURED = "measured"


# Anything at or below this level must never be presented as a finding.
UNSUPPORTED = frozenset({Confidence.EXPERT_GUESS})


class Assumption(BaseModel):
    """One registered heuristic."""

    name: str
    params: dict[str, Any] = Field(default_factory=dict)
    description: str = ""
    source: str = ""
    confidence: Confidence = Confidence.EXPERT_GUESS
    version: int = 1
    tags: list[str] = Field(default_factory=list)
    changelog: list[str] = Field(default_factory=list)

    @property
    def quotable(self) -> bool:
        """False if a number derived from this must carry a caveat."""
        return self.confidence not in UNSUPPORTED

    def get(self, key: str, default: Any = None) -> Any:
        return self.params.get(key, default)


class AssumptionLedger:
    """Registry of assumptions. Registration is idempotent per (name, version);
    re-registering the same name with different content is an error, because two
    modules disagreeing about a coefficient is exactly the bug this prevents.
    """

    def __init__(self) -> None:
        self._entries: dict[str, Assumption] = {}

    def register(self, assumption: Assumption) -> Assumption:
        existing = self._entries.get(assumption.name)
        if existing is not None:
            if existing.model_dump() != assumption.model_dump():
                raise ValueError(
                    f"assumption {assumption.name!r} is already registered with "
                    "different content; bump `version` and add a changelog entry "
                    "instead of redefining it"
                )
            return existing
        self._entries[assumption.name] = assumption
        return assumption

    def get(self, name: str) -> Assumption:
        try:
            return self._entries[name]
        except KeyError:
            raise KeyError(
                f"unknown assumption {name!r}. Registered: "
                f"{', '.join(sorted(self._entries)) or '(none)'}"
            ) from None

    def __contains__(self, name: str) -> bool:
        return name in self._entries

    def __iter__(self) -> Iterator[Assumption]:
        return iter(sorted(self._entries.values(), key=lambda a: a.name))

    def __len__(self) -> int:
        return len(self._entries)

    def snapshot(self) -> dict:
        """Serialisable image of every assumption, stamped into exported runs."""
        return {
            "ledger_schema_version": LEDGER_SCHEMA_VERSION,
            "count": len(self._entries),
            "assumptions": [a.model_dump(mode="json") for a in self],
        }

    def by_confidence(self, confidence: Confidence) -> list[Assumption]:
        return [a for a in self if a.confidence == confidence]

    def unsupported(self) -> list[Assumption]:
        """Assumptions whose outputs must never be quoted as findings."""
        return [a for a in self if not a.quotable]

    def perturbed(self, name: str, factor: float) -> dict[str, Any]:
        """Numeric params scaled by `factor` — the primitive under sensitivity
        analysis ("re-run with travel burden weight +20%").
        """
        assumption = self.get(name)
        return {
            key: (value * factor if isinstance(value, (int, float)) and
                  not isinstance(value, bool) else value)
            for key, value in assumption.params.items()
        }


# Process-wide ledger. Modules register at import time.
LEDGER = AssumptionLedger()


def register(assumption: Assumption) -> Assumption:
    """Convenience wrapper around the process-wide ledger."""
    return LEDGER.register(assumption)
