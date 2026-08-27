"""Prior packs: population priors as versioned data, not code.

A pack is the **single source of truth** for one population. Everything that
describes how a cohort should look lives in it — marginals, the latent
correlation matrix, derivation rules, and per-entry provenance — and the
statistical contract tests are *generated from it* rather than written beside it.
That is the load-bearing decision: a contract written by hand next to the data is
a second copy of the same numbers, and two copies drift. Generated contracts mean
adding a pack is adding data, and a pack cannot ship without coverage.

What is deliberately NOT in a pack:

  * **Hazard anchors.** Retention targets are properties of a scenario's
    intensity, not of a population. Mixing them would make packs unloadable
    across scenario types.
  * **Overlays / inheritance.** Flat single packs only. Base+delta composition is
    Phase 5 platform work and is easy to add once two real packs disagree;
    building it now would be speculation.

Validation happens at load, using machinery that already exists: field coverage
against the schema registry, support/parameter sanity, and the PSD gate on the
latent matrix. A bad community-supplied pack therefore fails with the
eigenvector-naming error from `correlation.py`, not somewhere downstream in
generation.
"""
from __future__ import annotations

import math

import json
from datetime import date
from enum import Enum
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from ..foundation.ledger import Confidence
from .correlation import TRAIT_AXES, build_correlation_matrix

PACK_SCHEMA_VERSION = 1
PACK_DIR = Path(__file__).resolve().parents[3] / "data" / "prior_packs"

MarginalFamily = Literal["normal", "categorical", "bernoulli_set", "ladder", "scalar"]


class ProvenanceKind(str, Enum):
    """WHAT KIND of claim a number is. Deliberately **not** an ordered scale.

    `Confidence` is ordered weakest-to-strongest and stays that way for the
    assumption ledger, where "how much weight can this bear" is the question. This
    is a different axis and needs its own field, because an expert guess and a
    Synthea-derived value can both be wrong and they are wrong *differently*:

    * `EXPERT_GUESS` — unknown provenance. Someone typed a plausible number.
    * `SYNTHEA_CALIBRATED` — **known synthetic** provenance. Traceable to Synthea's
      care maps and published statistics, which carry their own documented biases:
      US-centric, care-pathway-shaped, and thin on social determinants.
    * `CUSTOMER_DATA_FITTED` — fitted to a real population's aggregates.

    Ranking Synthea above guess on the *confidence* scale would eventually be read
    as "quotable once high enough", and that is the inflation path: synthetic
    calibration is a better-documented assumption, not a weaker one. So `quotable`
    keys on KIND, and **only the third kind ever crosses the line.**

    The demo sentence this protects: *"51 entries, all expert guesses today; watch
    this one move to Synthea-calibrated, per entry, with the version stamped."*
    Visible per-entry movement is the feature. A scale would blur it.
    """

    EXPERT_GUESS = "expert_guess"
    SYNTHEA_CALIBRATED = "synthea_calibrated"
    CUSTOMER_DATA_FITTED = "customer_data_fitted"


# The one kind whose outputs may be presented as findings.
QUOTABLE_KINDS: frozenset[ProvenanceKind] = frozenset({
    ProvenanceKind.CUSTOMER_DATA_FITTED
})


class Provenance(BaseModel):
    """Where a number came from, what kind of claim it is, and what it may bear."""

    source: str
    confidence: Confidence = Confidence.EXPERT_GUESS
    kind: ProvenanceKind = ProvenanceKind.EXPERT_GUESS
    as_of: date | None = None
    # Synthea is deterministic given (version, seed). A calibration target that
    # cannot name the run that produced it is the digest-pinning lesson forgotten:
    # a tag is a mutable pointer, and so is "generated from Synthea".
    synthea_version: str = ""
    synthea_seed: int | None = None

    @property
    def quotable(self) -> bool:
        return self.kind in QUOTABLE_KINDS

    @property
    def caveat(self) -> str:
        """The sentence this entry can be described with, without flinching."""
        if self.kind is ProvenanceKind.CUSTOMER_DATA_FITTED:
            return "fitted to real population aggregates"
        if self.kind is ProvenanceKind.SYNTHEA_CALIBRATED:
            stamp = f"{self.synthea_version or 'unversioned'}"
            if self.synthea_seed is not None:
                stamp += f", seed {self.synthea_seed}"
            return (f"calibrated against Synthea-generated populations ({stamp}); "
                    "not real-world epidemiology")
        return "expert guess; not fitted to any dataset"

    @model_validator(mode="after")
    def _synthea_entries_name_their_run(self) -> Provenance:
        if self.kind is ProvenanceKind.SYNTHEA_CALIBRATED and not self.synthea_version:
            raise ValueError(
                "a SYNTHEA_CALIBRATED entry must name the Synthea version that "
                "produced it — an unversioned calibration target cannot be "
                "reproduced or audited"
            )
        return self


class MarginalSpec(BaseModel):
    """One field's marginal distribution, with its own provenance and tolerance."""

    field: str
    family: MarginalFamily
    params: dict[str, Any] = Field(default_factory=dict)
    support: list[Any] | None = Field(
        default=None, description="allowed values (categorical) or [lo, hi] (normal)"
    )
    provenance: Provenance

    # Tolerance the generated contract test asserts against. Lives with the
    # number it constrains, so tightening a prior tightens its own test.
    tolerance: float = 0.06

    # Mechanisms OUTSIDE the copula that also touch this field. Without this,
    # the first person to measure a pack's realized correlations files a bug
    # against correct behaviour — see the age/comorbidity case, where age_factor
    # stacks a causal path on top of the latent correlation.
    structural_paths: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_family(self) -> MarginalSpec:
        if self.family == "normal":
            for key in ("mean", "sd"):
                if key not in self.params:
                    raise ValueError(f"{self.field}: normal marginal needs {key!r}")
            if self.params["sd"] <= 0:
                raise ValueError(f"{self.field}: sd must be positive")
            if self.support is not None:
                lo, hi = self.support
                if lo >= hi:
                    raise ValueError(f"{self.field}: support {self.support} is empty")
        elif self.family in {"categorical", "bernoulli_set"}:
            if not self.params:
                raise ValueError(f"{self.field}: {self.family} needs weights")
            for name, weight in self.params.items():
                if not 0.0 <= float(weight) <= 1.0:
                    raise ValueError(
                        f"{self.field}/{name}: {weight} is not a probability"
                    )
            if self.family == "categorical":
                total = math.fsum(float(w) for w in self.params.values())
                if abs(total - 1.0) > 1e-6:
                    raise ValueError(
                        f"{self.field}: categorical weights sum to {total}, not 1"
                    )
        return self


class LatentPair(BaseModel):
    """One entry of the latent Gaussian correlation matrix."""

    axis_a: str
    axis_b: str
    rho: float = Field(ge=-1.0, le=1.0)
    provenance: Provenance
    tolerance: float = 0.02
    structural_paths: list[str] = Field(default_factory=list)

    @property
    def key(self) -> str:
        return f"{self.axis_a}|{self.axis_b}"

    @model_validator(mode="after")
    def _check_axes(self) -> LatentPair:
        for axis in (self.axis_a, self.axis_b):
            if axis not in TRAIT_AXES:
                raise ValueError(f"unknown trait axis {axis!r}")
        if self.axis_a == self.axis_b:
            raise ValueError(f"self-correlation for {self.axis_a!r}")
        return self


class DerivationRules(BaseModel):
    """How goals and barriers are read off a finished profile."""

    barrier_severity: dict[str, float] = Field(default_factory=dict)
    goal_limit: int = 3
    provenance: Provenance


class PriorPack(BaseModel):
    """Everything needed to sample one population."""

    schema_version: int = PACK_SCHEMA_VERSION
    name: str
    condition: str
    aliases: list[str] = Field(default_factory=list)
    description: str = ""

    marginals: list[MarginalSpec]
    latent_correlations: list[LatentPair]
    derivations: DerivationRules | None = None

    @model_validator(mode="after")
    def _validate(self) -> PriorPack:
        if self.schema_version != PACK_SCHEMA_VERSION:
            raise ValueError(
                f"pack {self.name!r} is schema v{self.schema_version}, "
                f"this build reads v{PACK_SCHEMA_VERSION}"
            )

        fields = [m.field for m in self.marginals]
        if len(fields) != len(set(fields)):
            raise ValueError(f"pack {self.name!r} has duplicate marginals")

        missing = REQUIRED_FIELDS - set(fields)
        if missing:
            raise ValueError(
                f"pack {self.name!r} is missing required marginals: {sorted(missing)}"
            )

        keys = [pair.key for pair in self.latent_correlations]
        if len(keys) != len(set(keys)):
            raise ValueError(f"pack {self.name!r} has duplicate correlation pairs")

        # The PSD gate, run at pack load. A bad pack fails here with the
        # eigenvector diagnostic rather than deep inside generation.
        self.correlation_matrix()
        return self

    def marginal(self, field: str) -> MarginalSpec:
        for spec in self.marginals:
            if spec.field == field:
                return spec
        raise KeyError(f"pack {self.name!r} has no marginal for {field!r}")

    def correlation_matrix(self):
        """Latent matrix, PSD-gated. Raises NotPositiveDefinite on a bad pack."""
        pairs = {
            (pair.axis_a, pair.axis_b): pair.rho for pair in self.latent_correlations
        }
        matrix, corrections = build_correlation_matrix(pairs, allow_projection=False)
        assert not corrections
        return matrix

    def unquotable(self) -> list[str]:
        """Entries whose outputs must never be presented as findings."""
        names = [m.field for m in self.marginals if not m.provenance.quotable]
        names += [p.key for p in self.latent_correlations if not p.provenance.quotable]
        return sorted(names)


# Marginals every pack must define, checked against what the generator reads.
REQUIRED_FIELDS: frozenset[str] = frozenset({
    "age", "sex", "stage", "comorbidities", "health_literacy",
    "medication_ladder", "base_adherence", "dx_delay_months",
})


class PackError(ValueError):
    """A pack could not be loaded."""


_CACHE: dict[str, PriorPack] = {}


def load_pack(path: str | Path) -> PriorPack:
    """Read and validate one pack from disk."""
    path = Path(path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise PackError(f"could not read pack {path}: {exc}") from exc

    try:
        return PriorPack.model_validate(payload)
    except Exception as exc:
        raise PackError(f"pack {path.name} is invalid: {exc}") from exc


def available_packs(directory: Path = PACK_DIR) -> list[Path]:
    return sorted(directory.glob("*.json")) if directory.exists() else []


def load_all_packs(directory: Path = PACK_DIR, refresh: bool = False) -> dict[str, PriorPack]:
    """Load every pack, keyed by condition. Cached; `refresh` re-reads disk."""
    global _CACHE
    if _CACHE and not refresh:
        return _CACHE

    packs: dict[str, PriorPack] = {}
    for path in available_packs(directory):
        pack = load_pack(path)
        packs[pack.condition.casefold()] = pack
    _CACHE = packs
    return packs


def pack_for(condition: str, directory: Path = PACK_DIR) -> PriorPack | None:
    """Resolve a free-text condition to its pack, alias-aware."""
    packs = load_all_packs(directory)
    key = (condition or "").strip().casefold()
    if not key:
        return None
    if key in packs:
        return packs[key]
    for pack in packs.values():
        if key in {alias.casefold() for alias in pack.aliases}:
            return pack
    for pack in packs.values():
        names = [pack.condition.casefold(), *(a.casefold() for a in pack.aliases)]
        if any(name in key or key in name for name in names):
            return pack
    return None
