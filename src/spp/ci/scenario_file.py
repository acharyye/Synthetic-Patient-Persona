"""A scenario as a file on disk, with a content hash.

This is the unit Protocol CI gates on: a protocol design, committed to a repo,
diffed like code. Nothing here adds simulation capability — it reuses the same
Pydantic models the API already validates, plus a loader and a hash.

**The loader is STRICT, and that is the whole point of this module.**

`protocol/lenient.py` exists because a half-typed rule in the Scenario Lab editor
is a person mid-keystroke, not a broken protocol: it scores the valid subset and
marks the result stale. Here the opposite is required. A rule that does not parse
in a committed scenario file is a broken protocol, and scoring "the subset that
parses" would silently gate on a design nobody wrote — the loudest possible
version of the bug the lenient path was careful to avoid on the other side.

So: any unparseable rule is a hard error at load, before a single persona is
generated.

The hash is over a canonical serialisation, so two files that *mean* the same
scenario hash the same regardless of key order or whitespace inside DSL text. It
travels in every verdict; a verdict that cannot name the scenario it judged is
not evidence.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, model_validator

from ..protocol import CriterionError, ProtocolBurden, parse_criteria

SCENARIO_SCHEMA_VERSION = 1

# Bumped when a change would alter simulation OUTPUT for an unchanged scenario
# file. Stamped into baselines and verdicts so a stale baseline is detectable
# rather than merely wrong.
ENGINE_VERSION = 1


class ScenarioError(ValueError):
    """A scenario file is unloadable. Always fatal — never degraded."""


class VisitSpec(BaseModel):
    """One scheduled demand. `visit_id` is stable identity, not position."""

    model_config = {"frozen": True}

    visit_id: str
    day: int = Field(ge=0)
    label: str = ""
    remote: bool = False

    @model_validator(mode="after")
    def _default_label(self) -> VisitSpec:
        if not self.label:
            object.__setattr__(self, "label", self.visit_id)
        return self


class ScenarioFile(BaseModel):
    """The committed description of a protocol design."""

    schema_version: int = SCENARIO_SCHEMA_VERSION
    name: str
    description: str = ""

    # Population
    condition: str
    pack: str = Field("", description="informational; the pack is resolved by condition")
    cohort_size: int = Field(200, ge=1, le=5000)
    seed: int = 42

    # Design
    inclusion: list[str] = Field(default_factory=list)
    exclusion: list[str] = Field(default_factory=list)
    burden: ProtocolBurden = Field(default_factory=ProtocolBurden)
    duration_days: int = Field(365, gt=0, le=3650)

    # Optional explicit timeline. When absent the schedule is derived from
    # `burden`, which is what most scenarios want.
    visits: list[VisitSpec] = Field(default_factory=list)

    @model_validator(mode="after")
    def _validate(self) -> ScenarioFile:
        if self.schema_version != SCENARIO_SCHEMA_VERSION:
            raise ValueError(
                f"scenario {self.name!r} is schema v{self.schema_version}; this "
                f"build reads v{SCENARIO_SCHEMA_VERSION}"
            )

        ids = [visit.visit_id for visit in self.visits]
        if len(ids) != len(set(ids)):
            raise ValueError(f"scenario {self.name!r} has duplicate visit_ids")

        # STRICT. Unlike the editor's lenient path, an unparseable rule here is
        # a broken protocol, not a keystroke in progress.
        for kind, rules in (("inclusion", self.inclusion), ("exclusion", self.exclusion)):
            try:
                parse_criteria([r for r in rules if r.strip()])
            except CriterionError as exc:
                raise ValueError(
                    f"scenario {self.name!r} has an unparseable {kind} rule: {exc}"
                ) from None
        return self

    # -- canonical form and hash -------------------------------------------

    def canonical(self) -> dict[str, Any]:
        """Serialisation the hash is taken over.

        Sorted keys and whitespace-normalised DSL text, so `age >= 50` and
        `age  >=  50` are the same scenario. Cosmetic fields that cannot change
        a simulation result (`name`, `description`, `pack`, visit `label`) are
        excluded — otherwise renaming a scenario would invalidate its baseline.
        """
        def normalise(rule: str) -> str:
            return re.sub(r"\s+", " ", rule.strip())

        return {
            "schema_version": self.schema_version,
            "condition": self.condition.strip().casefold(),
            "cohort_size": self.cohort_size,
            "seed": self.seed,
            "duration_days": self.duration_days,
            "inclusion": sorted(normalise(r) for r in self.inclusion if r.strip()),
            "exclusion": sorted(normalise(r) for r in self.exclusion if r.strip()),
            "burden": self.burden.model_dump(mode="json"),
            "visits": sorted(
                (
                    {"visit_id": v.visit_id, "day": v.day, "remote": v.remote}
                    for v in self.visits
                ),
                key=lambda v: (v["day"], v["visit_id"]),
            ),
        }

    def scenario_hash(self) -> str:
        payload = json.dumps(self.canonical(), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()

    @property
    def short_hash(self) -> str:
        return self.scenario_hash()[:12]


def load_scenario(path: str | Path) -> ScenarioFile:
    """Read and strictly validate a scenario file. Any problem is fatal."""
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ScenarioError(f"could not read scenario {path}: {exc}") from None

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        payload = _load_yaml(text, path, exc)

    if not isinstance(payload, dict):
        raise ScenarioError(f"scenario {path.name} must be a mapping")

    try:
        return ScenarioFile.model_validate(payload)
    except ScenarioError:
        raise
    except Exception as exc:
        raise ScenarioError(f"scenario {path.name} is invalid: {exc}") from None


def _load_yaml(text: str, path: Path, json_error: Exception) -> Any:
    """YAML is accepted when PyYAML is available; JSON always works.

    Not a hard dependency: the format is JSON-first so CI never fails on a
    missing parser, but hand-edited scenarios read better as YAML.
    """
    try:
        import yaml  # type: ignore[import-untyped]
    except ImportError:
        raise ScenarioError(
            f"scenario {path.name} is not valid JSON ({json_error}); install "
            "PyYAML to use YAML scenario files"
        ) from None
    try:
        return yaml.safe_load(text)
    except Exception as exc:
        raise ScenarioError(f"scenario {path.name} is not valid YAML: {exc}") from None


def dump_scenario(scenario: ScenarioFile, path: str | Path) -> Path:
    """Write a scenario back out. Round-trips through `load_scenario`."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(scenario.model_dump(mode="json"), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return path


def discover_scenarios(root: str | Path, pattern: str = "*.json") -> list[Path]:
    """Every scenario file under `root`, sorted. Used by the CI path filter.

    Baselines live beside their scenario as `<name>.baseline.json` and are
    excluded here, the same way `cli.changed_scenarios` excludes them: a
    baseline is an expectation about a scenario, not a scenario, and listing it
    as one made `spp ci list` report a committed baseline as INVALID.
    """
    root = Path(root)
    if not root.exists():
        return []
    found = sorted(root.rglob(pattern))
    if pattern == "*.json":
        found += sorted(root.rglob("*.yaml")) + sorted(root.rglob("*.yml"))
    return sorted(p for p in set(found) if not p.name.endswith(".baseline.json"))
