"""Evidence bundle: the first live run, archived the way any artifact is stamped.

The first compliance numbers are themselves evidence someone will want to audit
later — including whoever bumps the model or the prompt and needs the baseline
that justified the previous version. So the run is archived as a versioned
directory rather than printed and lost:

    evidence/<release>/<timestamp>/
      manifest.json      what was run, against which model digest and prompt
      canary.json        degraded-configuration scores and the sensitivity verdict
      compliance.json    aggregates and the pre-registered pass-bar verdicts
      takes/             the five seed-chosen raw takes, in full
      quarantine.json    every rejected response with its reason

`takes/` and `quarantine.json` are the reading protocol made durable: the
protocol says read five sampled takes and every quarantine entry before acting
on aggregates, and a bundle that omitted them would let a later reader skip
straight to the numbers — which is the failure the protocol exists to prevent.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from ..foundation.ledger import LEDGER_SCHEMA_VERSION

BUNDLE_VERSION = 1
EVIDENCE_DIR = Path(__file__).resolve().parents[3] / "evidence"


class BundleManifest(BaseModel):
    bundle_version: int = BUNDLE_VERSION
    release: str
    recorded_at: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="seconds")
    )
    backend: str
    model: str
    model_digest: str = ""
    prompt_version: int
    # Assumption names are the ledger's keys AND appear in every stamped report.
    # Domain namespacing in Phase 5 renames them, which would orphan this
    # bundle's references — so the version it was written against travels with
    # it, and an alias table can be scoped to a release rather than guessed at.
    ledger_schema_version: int = LEDGER_SCHEMA_VERSION
    sampling: dict[str, Any] = Field(default_factory=dict)
    battery_cases: int = 0
    accepted_takes: int = 0
    quarantined_takes: int = 0
    compliance_rate: float | None = None
    canary_sensitive: bool | None = None
    bars_passed: bool | None = None
    # Stated in the manifest so a later reader cannot mistake the bundle for a
    # validation of the model against real data.
    caveat: str = (
        "Compliance measured against a fixed battery under a pre-registered set "
        "of pass bars. This is evidence about one (prompt, model, sampling) "
        "configuration, not a validation of the model in general."
    )


def write_bundle(
    release: str,
    manifest: BundleManifest,
    canary: dict | None = None,
    compliance: dict | None = None,
    sampled_takes: list[dict] | None = None,
    quarantine: list[dict] | None = None,
    root: Path = EVIDENCE_DIR,
) -> Path:
    """Archive one run. Returns the bundle directory."""
    stamp = manifest.recorded_at.replace(":", "").replace("-", "")
    directory = root / release / stamp
    (directory / "takes").mkdir(parents=True, exist_ok=True)

    def dump(name: str, payload: Any) -> None:
        (directory / name).write_text(
            json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n",
            encoding="utf-8",
        )

    dump("manifest.json", manifest.model_dump())
    if canary is not None:
        dump("canary.json", canary)
    if compliance is not None:
        dump("compliance.json", compliance)
    if quarantine is not None:
        dump("quarantine.json", {"count": len(quarantine), "rejected": quarantine})

    for index, take in enumerate(sampled_takes or []):
        (directory / "takes" / f"{index:02d}_{take.get('case_id', 'take')}.json").write_text(
            json.dumps(take, indent=2, sort_keys=True, default=str) + "\n",
            encoding="utf-8",
        )

    _write_readme(directory, manifest, len(sampled_takes or []))
    return directory


def _write_readme(directory: Path, manifest: BundleManifest, take_count: int) -> None:
    """A human entry point, so the bundle explains itself in six months."""
    identity = (
        f"{manifest.model}@{manifest.model_digest[:19]}"
        if manifest.model_digest else manifest.model
    )
    (directory / "README.md").write_text(
        f"""# Narration evidence bundle — {manifest.release}

Recorded {manifest.recorded_at} against **{identity}**, prompt v{manifest.prompt_version}.

| | |
|---|---|
| battery cases | {manifest.battery_cases} |
| accepted takes | {manifest.accepted_takes} |
| quarantined | {manifest.quarantined_takes} |
| compliance rate | {manifest.compliance_rate} |
| canary sensitive | {manifest.canary_sensitive} |
| pass bars met | {manifest.bars_passed} |
| ledger schema | v{manifest.ledger_schema_version} |

## Read in this order

1. `canary.json` — **first**. If the instrument could not detect a degraded
   configuration, nothing else here is evidence.
2. `takes/` — {take_count} raw takes, chosen by seed rather than picked. No
   aggregate catches degeneracy; only reading does.
3. `quarantine.json` — every rejected response, with its reason.
4. `compliance.json` — aggregates and the pre-registered pass-bar verdicts.

## Caveat

{manifest.caveat}
""",
        encoding="utf-8",
    )


def latest_bundle(release: str, root: Path = EVIDENCE_DIR) -> Path | None:
    directory = root / release
    if not directory.exists():
        return None
    bundles = sorted(p for p in directory.iterdir() if p.is_dir())
    return bundles[-1] if bundles else None
