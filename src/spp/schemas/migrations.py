"""Migrations for persisted persona payloads.

Imported for side effects: importing this module registers every migration with
`foundation.versioning`. `spp.schemas` does that at package import, so a caller
who can construct a PatientDNA can also load an old one.
"""
from __future__ import annotations

from ..foundation.versioning import migration, register_schema

PATIENT_DNA_VERSION = 2

register_schema("PatientDNA", PATIENT_DNA_VERSION)


@migration("PatientDNA", 1, 2)
def _v1_to_v2(payload: dict) -> dict:
    """v2 adds traits, goals, constraints and barriers.

    A v1 cohort predates the copula, so there are no latent trait quantiles to
    recover — they stay empty rather than being invented, and `traits == {}` is
    the honest marker that this persona was sampled independently.

    Goals and barriers are *derivable* from fields v1 already had, but deriving
    them here would bake in whatever heuristics happen to be current at load
    time and make an old cohort silently change as the code moves. Left empty;
    call `derive_persona_traits()` explicitly if you want them.
    """
    payload.setdefault("traits", {})
    payload.setdefault("goals", [])
    payload.setdefault("constraints", [])
    payload.setdefault("barriers", [])
    return payload
