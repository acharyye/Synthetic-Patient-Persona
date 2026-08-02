"""Schema registry with versioning.

A cohort saved a month ago must still load. Pydantic will happily parse an old
payload into a new model and silently give you defaults for fields that changed
meaning — which is worse than failing. So persisted payloads carry an explicit
`schema_version`, and moving between versions goes through a registered
migration function.

    @migration("PatientDNA", 1, 2)
    def _add_digital_literacy(payload: dict) -> dict:
        payload["digital_literacy"] = payload.pop("health_literacy", "medium")
        return payload

    data = migrate(raw, "PatientDNA", target=2)

Rules: migrations are pure dict->dict, form an unbroken chain, and never lose
information silently — if a field cannot be derived, raise rather than default.
"""
from __future__ import annotations

from typing import Callable

MigrationFn = Callable[[dict], dict]

# (model_name, from_version) -> (to_version, fn)
_MIGRATIONS: dict[tuple[str, int], tuple[int, MigrationFn]] = {}

# model_name -> current version
_CURRENT: dict[str, int] = {}


class MigrationError(RuntimeError):
    """No path from the payload's version to the target."""


def register_schema(model_name: str, version: int) -> None:
    """Declare the current version of a persisted model."""
    _CURRENT[model_name] = version


def current_version(model_name: str) -> int:
    return _CURRENT.get(model_name, 1)


def migration(model_name: str, from_version: int, to_version: int):
    """Decorator registering a migration step."""
    if to_version != from_version + 1:
        raise ValueError(
            f"migrations must be single steps; got {from_version} -> {to_version}"
        )

    def decorator(fn: MigrationFn) -> MigrationFn:
        key = (model_name, from_version)
        if key in _MIGRATIONS:
            raise ValueError(f"migration {model_name} v{from_version} already registered")
        _MIGRATIONS[key] = (to_version, fn)
        return fn

    return decorator


def migrate(payload: dict, model_name: str, target: int | None = None) -> dict:
    """Walk `payload` up to `target` (default: the model's current version)."""
    target = current_version(model_name) if target is None else target
    data = dict(payload)
    version = int(data.get("schema_version", 1))

    if version > target:
        raise MigrationError(
            f"{model_name} payload is v{version}, newer than the supported v{target}; "
            "downgrades are not supported"
        )

    while version < target:
        step = _MIGRATIONS.get((model_name, version))
        if step is None:
            raise MigrationError(
                f"no migration registered for {model_name} v{version} -> v{version + 1}"
            )
        next_version, fn = step
        data = fn(data)
        version = next_version
        data["schema_version"] = version

    return data


def registered_migrations() -> dict[str, list[str]]:
    """Introspection for tests and the ledger snapshot."""
    out: dict[str, list[str]] = {}
    for (model_name, from_version), (to_version, _) in sorted(_MIGRATIONS.items()):
        out.setdefault(model_name, []).append(f"v{from_version}->v{to_version}")
    return out
