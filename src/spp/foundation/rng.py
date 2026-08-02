"""Seeded RNG hierarchy: master -> cohort -> persona -> event.

The reproducibility promise ("same seed → same cohort → same simulation result")
only holds if every random draw can name where it came from. A single shared
Generator can't do that: add one draw anywhere and every downstream value shifts.

So seeds are *derived by name*, not consumed in sequence:

    master = SeedScope.root(42)
    cohort = master.child("cohort:type 2 diabetes")
    person = cohort.child("persona:0007")
    visits = person.child("event:visit-3")

Two properties fall out, and both matter:

  * **Isolation.** `person.generator()` is unaffected by how many draws any
    sibling made, so a single persona can be re-simulated on its own and produce
    identical results. That is what makes counterfactual forking honest.
  * **Stability.** Derivation is BLAKE2b over "<parent>:<name>", so it does not
    depend on PYTHONHASHSEED, dict ordering, or call order — the same names give
    the same seeds across processes and Python versions.

Log `scope.path` and `scope.seed` in any output artifact; they are enough to
reproduce that exact draw.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field

import numpy as np

# numpy seeds must fit in 64 unsigned bits.
_SEED_BITS = 64
_SEED_MASK = (1 << _SEED_BITS) - 1


def derive_seed(parent_seed: int, name: str) -> int:
    """Stable child seed from a parent seed and a name.

    BLAKE2b rather than hash() because the latter is randomised per process for
    str, which would silently break reproducibility across runs.
    """
    digest = hashlib.blake2b(
        f"{parent_seed}:{name}".encode(), digest_size=8, person=b"spp-seed"
    ).digest()
    return int.from_bytes(digest, "big") & _SEED_MASK


@dataclass(frozen=True)
class SeedScope:
    """A named point in the seed tree. Immutable; `child` returns a new scope."""

    name: str
    seed: int
    parents: tuple[str, ...] = field(default=())

    @classmethod
    def root(cls, master_seed: int, name: str = "master") -> SeedScope:
        return cls(name=name, seed=int(master_seed) & _SEED_MASK)

    @property
    def path(self) -> str:
        """Dotted path, e.g. 'master/cohort:COPD/persona:0007'."""
        return "/".join((*self.parents, self.name))

    def child(self, name: str) -> SeedScope:
        return SeedScope(
            name=name,
            seed=derive_seed(self.seed, name),
            parents=(*self.parents, self.name),
        )

    def generator(self) -> np.random.Generator:
        """A fresh Generator for this scope. Calling twice gives two Generators
        at the same starting state — deliberate, so a scope can be replayed.
        """
        return np.random.default_rng(self.seed)

    def describe(self) -> dict:
        """What to stamp into an output artifact so the draw can be reproduced."""
        return {"path": self.path, "seed": self.seed}


def cohort_scope(master_seed: int, condition: str) -> SeedScope:
    """Conventional scope for a cohort. Keep naming centralised: an ad-hoc name
    elsewhere would silently produce a different, unreproducible cohort.
    """
    return SeedScope.root(master_seed).child(f"cohort:{condition}")


def persona_scope(cohort: SeedScope, index: int) -> SeedScope:
    return cohort.child(f"persona:{index:06d}")


def event_scope(persona: SeedScope, event_name: str) -> SeedScope:
    return persona.child(f"event:{event_name}")
