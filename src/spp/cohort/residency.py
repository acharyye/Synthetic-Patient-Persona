"""Resident cohorts for the live preview.

The rule editor needs a cohort in memory to score criteria on every keystroke.
Normally that means a cache, and a cache means an invalidation problem.

**There isn't one here, and that is a consequence of Phase 0.** Generation is
deterministic, so `(pack_id, pack_version, cohort_seed, size, as_of)` is not a
cache *key* — it is the cohort's *identity*. Two cohorts with that tuple equal
are the same cohort, byte for byte. Which means:

  * eviction is always safe — a rebuild is provably identical, never merely
    probably;
  * staleness is impossible — if the pack version changes the key changes, so a
    cohort generated from an old pack can never be served for a new one;
  * there is nothing to invalidate, only something to recompute.

That property was designed in three phases ago; this module just spends it.
"""
from __future__ import annotations

from collections import OrderedDict
from datetime import date
from typing import NamedTuple

from ..schemas import PatientDNA
from .generator import generate_cohort
from .packs import pack_for

# Small: each entry is a few hundred personas, and a miss is cheap by design.
MAX_RESIDENT = 8


class CohortKey(NamedTuple):
    """The cohort's identity, not merely a lookup key.

    `pack_version` is in here because a pack edit changes the population. If it
    were omitted, an edited pack would keep serving personas from the old one —
    the exact silent-staleness bug this design avoids.
    """

    pack_id: str
    pack_version: int
    cohort_seed: int
    size: int
    as_of: str

    def describe(self) -> str:
        return (
            f"{self.pack_id}@v{self.pack_version} seed={self.cohort_seed} "
            f"n={self.size} as_of={self.as_of}"
        )


class CohortResidency:
    """LRU of generated cohorts. Bounded, and safe to evict at any moment."""

    def __init__(self, capacity: int = MAX_RESIDENT) -> None:
        self._entries: OrderedDict[CohortKey, list[PatientDNA]] = OrderedDict()
        self.capacity = capacity
        self.hits = 0
        self.misses = 0

    def key_for(
        self, condition: str, seed: int, size: int, as_of: date | None = None
    ) -> CohortKey:
        pack = pack_for(condition)
        as_of = as_of or date.today()
        return CohortKey(
            pack_id=pack.name if pack else f"generic:{condition}",
            pack_version=pack.schema_version if pack else 0,
            cohort_seed=seed,
            size=size,
            as_of=as_of.isoformat(),
        )

    def get(
        self, condition: str, seed: int, size: int, as_of: date | None = None
    ) -> tuple[list[PatientDNA], CohortKey, bool]:
        """Return (cohort, key, was_cached). Generating on a miss is not a fallback
        — it is the same operation the cache is a shortcut for.
        """
        key = self.key_for(condition, seed, size, as_of)
        if key in self._entries:
            self._entries.move_to_end(key)
            self.hits += 1
            return self._entries[key], key, True

        self.misses += 1
        cohort = generate_cohort(condition, size, seed=seed, as_of=as_of)
        self._entries[key] = cohort
        while len(self._entries) > self.capacity:
            self._entries.popitem(last=False)
        return cohort, key, False

    def clear(self) -> None:
        self._entries.clear()

    def stats(self) -> dict:
        total = self.hits + self.misses
        return {
            "resident": len(self._entries),
            "capacity": self.capacity,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": round(self.hits / total, 4) if total else None,
            "keys": [key.describe() for key in self._entries],
        }


RESIDENT = CohortResidency()
