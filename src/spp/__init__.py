"""Synthetic Patient Persona: a GraphRAG-grounded conversational patient digital twin."""
from __future__ import annotations

import tomllib
from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version as _installed_version
from pathlib import Path

_DISTRIBUTION = "synthetic-patient-persona"


@lru_cache(maxsize=1)
def _resolve_version() -> str:
    """One source of truth, resolved rather than restated.

    This was hardcoded here AND in `api/main.py`, so pyproject said 0.3.0 while
    `GET /openapi.json` reported 0.1.0 — a stamp that lies, in a project whose
    whole argument is that artifacts carry honest stamps. Same drift shape as
    the uv.lock version bump: a value copied is a value that diverges.

    Installed metadata first, because that is authoritative for a wheel. Then
    pyproject, because the documented way to run this is `PYTHONPATH=src` from
    a source checkout with nothing installed. Then "unknown", which is honest
    about knowing less rather than asserting a stale number.
    """
    try:
        return _installed_version(_DISTRIBUTION)
    except PackageNotFoundError:
        pass

    for parent in Path(__file__).resolve().parents:
        pyproject = parent / "pyproject.toml"
        if pyproject.is_file():
            try:
                return tomllib.loads(pyproject.read_text())["project"]["version"]
            except (tomllib.TOMLDecodeError, KeyError):  # pragma: no cover
                break
    return "unknown"


__version__ = _resolve_version()
