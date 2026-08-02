"""Persist event logs to Parquet, and load them back in another process.

This is the precondition for the analytics being genuinely *pure reads*. If a
survival curve computed from logs loaded in a fresh process differs from the one
computed in-run, then something in the analytics depends on live simulation
state — and Phase 2's fork-and-diff would be measuring that hidden state instead
of the design change.

Parquet + DuckDB is also the roadmap's analytics substrate (§3.6), so this is the
on-ramp to funnels and survival curves being SQL rather than Python.
"""
from __future__ import annotations

from pathlib import Path

from .events import EventLog

# Column order is fixed so the written file is stable across runs.
COLUMNS = ["persona_id", "schema_version", "seq", "type", "t", "payload", "seed_path"]


class EventStoreSchemaError(ValueError):
    """A Parquet file's column types are not the ones we write."""


def arrow_schema():
    """The pinned physical schema for an event-log file.

    Pinned rather than inferred because inference is where silent coercion
    happens: a column of all-None strings infers as null or double, and a NaN
    then rides back in where a string was expected. Writing against an explicit
    schema makes that a write-time failure instead of a replay-time mystery.
    """
    import pyarrow as pa

    return pa.schema([
        pa.field("persona_id", pa.string(), nullable=False),
        pa.field("schema_version", pa.int32(), nullable=False),
        pa.field("seq", pa.int32(), nullable=False),
        pa.field("type", pa.string(), nullable=False),
        pa.field("t", pa.int32(), nullable=False),
        pa.field("payload", pa.string(), nullable=False),
        pa.field("seed_path", pa.string(), nullable=True),
    ])


def write_logs(logs: dict[str, EventLog], path: str | Path) -> Path:
    """Write every log to a single Parquet file against the pinned schema."""
    import pyarrow as pa
    import pyarrow.parquet as pq

    path = Path(path)
    rows = [row for log in logs.values() for row in log.to_rows()]
    # Sort so file contents do not depend on dict iteration order.
    rows.sort(key=lambda row: (row["persona_id"], row["seq"]))

    table = pa.Table.from_pylist(
        [{column: row[column] for column in COLUMNS} for row in rows],
        schema=arrow_schema(),
    )
    pq.write_table(table, path)
    return path


def read_logs(path: str | Path) -> dict[str, EventLog]:
    """Load logs back, validating the physical schema then each log's version."""
    import pyarrow.parquet as pq

    table = pq.read_table(Path(path))
    expected = arrow_schema()

    if table.schema.names != expected.names:
        raise EventStoreSchemaError(
            f"columns {table.schema.names} != expected {expected.names}"
        )
    for field in expected:
        actual = table.schema.field(field.name)
        if actual.type != field.type:
            raise EventStoreSchemaError(
                f"column {field.name!r} has type {actual.type}, expected {field.type}"
            )

    logs: dict[str, EventLog] = {}
    for row in table.to_pylist():
        logs.setdefault(str(row["persona_id"]), []).append(row)  # type: ignore[arg-type]
    return {
        persona_id: EventLog.from_rows(rows)
        for persona_id, rows in sorted(logs.items())
    }
