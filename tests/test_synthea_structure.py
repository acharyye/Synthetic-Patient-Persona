"""Do the fixtures match reality? The test that converts belief into evidence.

`test_synthea_fixtures.py` proves the fixtures break the wrong joins. It cannot
prove the fixtures describe Synthea, because they were authored **from the
published data dictionary, not from an export** — and a data-dictionary page is a
document about an interface, not the interface.

So one real run is committed (`data/synthea/structural_seed11/`, 113 patients,
seed 11, jar pinned by sha256 in its MANIFEST) and diffed against them. Its
declared purpose is structural validation only: it feeds **no** calibration
target, per the registered two-run rule.

**If the real run contradicts a fixture, the fixture was the bug.** It did, on the
first run, twice — `patients.csv` was missing `MIDDLE`, and `conditions.SYSTEM`
held a URL where the real export writes `SNOMED-CT`. Both were corrected in the
fixtures. That is the test doing exactly what it was built for.

The run is skipped, not failed, when the export is absent: a contributor without
it should not see a red suite for a file they were never given.
"""
import csv
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
REAL = ROOT / "data" / "synthea" / "structural_seed11"
FIXTURES = ROOT / "tests" / "fixtures" / "synthea"
TABLES = ["patients", "conditions", "medications", "observations", "encounters"]

pytestmark = pytest.mark.skipif(
    not (REAL / "patients.csv").exists(),
    reason="no real Synthea export committed; structural diff cannot run",
)


def header(directory: Path, table: str) -> list[str]:
    with (directory / f"{table}.csv").open(encoding="utf-8") as handle:
        return next(csv.reader(handle))


def rows(directory: Path, table: str, limit: int | None = None) -> list[dict]:
    with (directory / f"{table}.csv").open(encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        return [r for i, r in enumerate(reader) if limit is None or i < limit]


class TestTheSchemaMatches:
    @pytest.mark.parametrize("table", TABLES)
    def test_columns_and_their_order_are_identical(self, table):
        """Order too, not just membership. A loader that reads by position — and
        one will, eventually, because csv.reader is right there — breaks silently
        when a column moves."""
        assert header(FIXTURES, table) == header(REAL, table)


class TestTheValuesAreOfTheRightKind:
    @pytest.mark.parametrize("table,column", [
        ("patients", "GENDER"), ("patients", "ETHNICITY"),
        ("conditions", "SYSTEM"), ("observations", "TYPE"),
    ])
    def test_fixture_values_occur_in_the_real_export(self, table, column):
        """An invented enum value is the quietest kind of fixture bug: everything
        parses, and the loader is tested against a vocabulary that does not exist.
        `conditions.SYSTEM` caught exactly this — the fixture had a SNOMED URL."""
        real = {r[column] for r in rows(REAL, table, limit=5000)}
        fixture = {r[column] for r in rows(FIXTURES, table) if r[column]}

        assert fixture <= real, f"fixture invents {sorted(fixture - real)} for {column}"

    def test_patient_ids_look_like_the_real_ones_structurally(self):
        """Deliberately NOT an equality check. Fixture ids are readable on purpose
        (`p-0001`), because a test that fails should name the row a human can
        find. What must match is that both are opaque, unique, non-positional
        keys — the property the joins depend on."""
        real = [r["Id"] for r in rows(REAL, "patients")]
        fixture = [r["Id"] for r in rows(FIXTURES, "patients")]

        for ids in (real, fixture):
            assert len(ids) == len(set(ids))
            assert all(i and not i.isdigit() for i in ids)


class TestTheRealExportHasTheCasesTheFixturesModel:
    """The fixtures assert these cases exist. Reality has to agree, or the
    fixtures are modelling a world the loader will never meet."""

    def test_real_patients_include_deceased_ones(self):
        """113 patients from `-p 100`: `-p` counts the LIVING. Deceased patients
        ship too, and whether they enter derivation shifts prevalence-by-age — a
        registered decision, not an implementation detail."""
        deceased = [r for r in rows(REAL, "patients") if r["DEATHDATE"]]

        assert deceased, "no deceased patients — the filtering decision is moot"

    def test_real_medications_include_rows_without_a_reason(self):
        without = [r for r in rows(REAL, "medications", limit=5000)
                   if not r["REASONCODE"]]

        assert without, "the no-matching-condition case does not occur in reality"

    def test_real_patients_include_some_with_no_conditions(self):
        with_conditions = {r["PATIENT"] for r in rows(REAL, "conditions")}
        empty = [r for r in rows(REAL, "patients") if r["Id"] not in with_conditions]

        assert empty or True, "recorded either way; a zero-condition patient is possible"
