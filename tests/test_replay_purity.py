"""Replay purity: analytics must be pure reads over persisted event logs.

The companion to `TestNoLLMInTheCore`. That proves the simulation core never
calls the narration layer; this proves the other direction — that survival
curves, funnels and attribution depend on *nothing* but the logs.

The strong form of the check: serialise logs to Parquet, recompute the analytics
in a **fresh Python process** that never ran the simulation, and require exact
equality. An in-process round-trip would not catch analytics that quietly read
module state left behind by the run.

This is the precondition for Phase 2 fork-and-diff being small: if replaying a
log reproduces its readouts exactly, a diff between a run and its fork isolates
the design change. If it doesn't, the diff measures hidden state.
"""
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from spp.cohort import generate_cohort
from spp.foundation.events import SCHEMA_VERSION, EventLog, EventType, IncompatibleEventLog
from spp.foundation.store import read_logs, write_logs
from spp.protocol import ProtocolBurden
from spp.simulation import (
    attrition_funnel,
    burden_breakdown,
    retention_summary,
    schedule_from_protocol,
    simulate_cohort,
    survival_curve,
)

AS_OF = date(2026, 8, 1)
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# Recomputes every readout from a Parquet file alone. Deliberately imports only
# the analytics — never the generator or the simulator.
REPLAY_SCRIPT = """
import json, sys
sys.path.insert(0, {src!r})
from spp.foundation.store import read_logs
from spp.simulation import (attrition_funnel, burden_breakdown,
                            retention_summary, survival_curve)

logs = read_logs({path!r})
print(json.dumps({{
    "retention": retention_summary(logs),
    "survival": survival_curve(logs, 365),
    "funnel": attrition_funnel(logs),
    "burden": burden_breakdown(logs),
    "n_logs": len(logs),
}}, sort_keys=True))
"""


@pytest.fixture(scope="module")
def logs():
    cohort = generate_cohort("type 2 diabetes", 40, seed=42, as_of=AS_OF)
    schedule = schedule_from_protocol(ProtocolBurden(visits_per_year=12), 365)
    return simulate_cohort(cohort, schedule, seed=42)


class TestRoundTrip:
    def test_logs_survive_parquet_unchanged(self, logs, tmp_path):
        path = write_logs(logs, tmp_path / "logs.parquet")
        restored = read_logs(path)

        assert set(restored) == set(logs)
        for persona_id, original in logs.items():
            assert restored[persona_id].model_dump() == original.model_dump()

    def test_payloads_survive_round_trip(self, logs, tmp_path):
        """Burden vectors and dropout reasons are nested payloads — the part most
        likely to be flattened lossily."""
        restored = read_logs(write_logs(logs, tmp_path / "logs.parquet"))

        dropouts = [
            event
            for log in restored.values()
            for event in log.of_type(EventType.DROPPED_OUT)
        ]
        assert dropouts, "fixture should contain at least one dropout"
        assert all(event.payload.get("reason") for event in dropouts)

        accruals = [
            event
            for log in restored.values()
            for event in log.of_type(EventType.BURDEN_ACCRUED)
        ]
        assert accruals
        assert all(isinstance(event.payload["burden"], dict) for event in accruals)

    def test_seed_paths_survive(self, logs, tmp_path):
        """Seed provenance is what makes a replayed log reproducible."""
        restored = read_logs(write_logs(logs, tmp_path / "logs.parquet"))
        for persona_id, log in restored.items():
            assert [e.seed_path for e in log] == [
                e.seed_path for e in logs[persona_id]
            ]


class TestFreshProcessReplay:
    def test_analytics_recompute_identically_in_a_new_process(self, logs, tmp_path):
        """The load-bearing test. Nothing but the Parquet file crosses over."""
        path = write_logs(logs, tmp_path / "logs.parquet")

        result = subprocess.run(
            [
                sys.executable,
                "-c",
                REPLAY_SCRIPT.format(src=str(PROJECT_ROOT / "src"), path=str(path)),
            ],
            capture_output=True,
            text=True,
            cwd=str(PROJECT_ROOT),
        )
        assert result.returncode == 0, result.stderr
        replayed = json.loads(result.stdout)

        expected = json.loads(json.dumps({
            "retention": retention_summary(logs),
            "survival": survival_curve(logs, 365),
            "funnel": attrition_funnel(logs),
            "burden": burden_breakdown(logs),
            "n_logs": len(logs),
        }, sort_keys=True))

        assert replayed["n_logs"] == len(logs)
        assert replayed["retention"] == expected["retention"]
        assert replayed["survival"] == expected["survival"]
        assert replayed["funnel"] == expected["funnel"]
        assert replayed["burden"] == expected["burden"]


class TestEventSchemaVersion:
    def test_every_log_is_stamped(self, logs):
        assert all(log.schema_version == SCHEMA_VERSION for log in logs.values())

    def test_rows_carry_the_version(self, logs):
        rows = next(iter(logs.values())).to_rows()
        assert all(row["schema_version"] == SCHEMA_VERSION for row in rows)

    def test_an_incompatible_log_is_rejected_not_misread(self):
        """A fork replayed against a foreign event schema must fail loudly."""
        log = EventLog(persona_id="p1", schema_version=SCHEMA_VERSION + 1)
        with pytest.raises(IncompatibleEventLog, match="event schema"):
            log.require_compatible()

    def test_loading_an_incompatible_log_from_rows_raises(self, logs, tmp_path):
        rows = next(iter(logs.values())).to_rows()
        for row in rows:
            row["schema_version"] = SCHEMA_VERSION + 99
        with pytest.raises(IncompatibleEventLog):
            EventLog.from_rows(rows)

    def test_a_compatible_log_passes_the_gate(self, logs):
        for log in logs.values():
            assert log.require_compatible() is log


class TestPinnedParquetSchema:
    def test_written_files_match_the_pinned_schema(self, logs, tmp_path):
        import pyarrow.parquet as pq

        from spp.foundation.store import arrow_schema

        path = write_logs(logs, tmp_path / "logs.parquet")
        written = pq.read_table(path).schema
        expected = arrow_schema()

        assert written.names == expected.names
        for field in expected:
            assert written.field(field.name).type == field.type, field.name

    def test_a_column_type_change_is_caught_at_load(self, logs, tmp_path):
        """The NaN-for-None bug was found at replay time. Pinning the schema
        turns the next coercion of its kind into a load-time error."""
        import pyarrow as pa
        import pyarrow.parquet as pq

        from spp.foundation.store import COLUMNS, EventStoreSchemaError

        rows = [
            {column: row[column] for column in COLUMNS}
            for log in logs.values()
            for row in log.to_rows()
        ]
        # seq written as float rather than int32 — exactly the kind of silent
        # widening a columnar round-trip can introduce.
        drifted = pa.schema([
            pa.field("persona_id", pa.string()),
            pa.field("schema_version", pa.int32()),
            pa.field("seq", pa.float64()),
            pa.field("type", pa.string()),
            pa.field("t", pa.int32()),
            pa.field("payload", pa.string()),
            pa.field("seed_path", pa.string()),
        ])
        path = tmp_path / "drifted.parquet"
        pq.write_table(pa.Table.from_pylist(rows, schema=drifted), path)

        with pytest.raises(EventStoreSchemaError, match="seq"):
            read_logs(path)

    def test_missing_columns_are_caught_at_load(self, logs, tmp_path):
        import pyarrow as pa
        import pyarrow.parquet as pq

        from spp.foundation.store import EventStoreSchemaError

        rows = [
            {"persona_id": row["persona_id"], "seq": row["seq"]}
            for log in logs.values()
            for row in log.to_rows()
        ]
        path = tmp_path / "narrow.parquet"
        pq.write_table(
            pa.Table.from_pylist(rows, schema=pa.schema([
                pa.field("persona_id", pa.string()), pa.field("seq", pa.int32()),
            ])),
            path,
        )
        with pytest.raises(EventStoreSchemaError, match="columns"):
            read_logs(path)
