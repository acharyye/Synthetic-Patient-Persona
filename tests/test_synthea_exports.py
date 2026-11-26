"""Every committed Synthea export, held to the fixtures and to its own MANIFEST.

Two jars have produced exports here. The first structural run used the jar pinned
in August; that jar's mutable tag was re-published, so the calibration run uses a
second jar, amended on the record — and the registration required the structural
check to be repeated against it first. These tests are that check, kept running.
"""
import csv
import hashlib
import json
from pathlib import Path

import pytest

from spp.cohort.packs import pack_for
from spp.ingest.synthea_derive import derive
from spp.ingest.synthea_loader import REQUIRED_COLUMNS, load_synthea

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "synthea"
EXPORTS = [d for d in sorted((ROOT / "data" / "synthea").iterdir())
           if (d / "patients.csv").exists()]
CALIBRATION = ROOT / "data" / "synthea" / "calibration_seed20260827"

pytestmark = pytest.mark.skipif(not EXPORTS, reason="no Synthea export committed")


def header(directory, table):
    with (directory / f"{table}.csv").open(encoding="utf-8") as handle:
        return next(csv.reader(handle))


@pytest.mark.parametrize("export", EXPORTS, ids=lambda d: d.name)
class TestEveryExport:
    @pytest.mark.parametrize("table", sorted(REQUIRED_COLUMNS))
    def test_the_tables_the_loader_reads_match_the_fixtures(self, export, table):
        assert header(export, table) == header(FIXTURES, table)

    def test_it_names_the_jar_that_made_it(self, export):
        manifest = json.loads((export / "MANIFEST.json").read_text())

        assert len(manifest["jar_sha256"]) == 64
        assert manifest["purpose"]

    def test_kept_files_match_the_hashes_its_manifest_recorded(self, export):
        """Exports written by scripts/run_synthea.py record a sha256 per table. A
        committed CSV that no longer matches was edited after the run."""
        tables = json.loads((export / "MANIFEST.json").read_text()).get("tables")
        if not tables:
            pytest.skip("written before per-table hashes were recorded")
        for name, meta in tables.items():
            if meta["kept"]:
                got = hashlib.sha256((export / f"{name}.csv").read_bytes()).hexdigest()
                assert got == meta["sha256"], name

    def test_it_loads_and_its_books_balance(self, export):
        report = load_synthea(export).report

        assert report.living + report.deceased_excluded == report.patients_total
        assert sum(report.records_by_condition.values()) == report.records


@pytest.mark.skipif(not (CALIBRATION / "patients.csv").exists(),
                    reason="the calibration export is not committed")
class TestTheCalibrationRun:
    @pytest.fixture(scope="module")
    def load(self):
        return load_synthea(CALIBRATION)

    def test_it_ran_under_the_registered_parameters(self, load):
        targets = json.loads((ROOT / "tests/eval/synthea_targets.json").read_text())
        registered = targets["calibration_run_parameters"]
        manifest = load.report.manifest

        assert manifest["jar_sha256"] == registered["jar_sha256"]
        assert manifest["seed"] == registered["seed"]
        assert manifest["population_flag"] == registered["population_flag"]
        assert "calibration" in manifest["purpose"]

    def test_only_type_2_diabetes_clears_the_floor(self, load):
        """The prevalence finding, measured rather than extrapolated."""
        assert load.report.records_by_condition == {
            "COPD": 17, "breast cancer": 9, "heart failure": 1,
            "rheumatoid arthritis": 3, "type 2 diabetes": 62,
        }

    def test_the_diabetes_table_as_it_was_read(self, load):
        """Pinned so the table the owner read cannot shift under a later edit to
        the loader, the code map or the pack without this test saying so."""
        table = derive(load, pack_for("type 2 diabetes"))
        verdicts = {r.entry: r.verdict for r in table.rows}

        assert table.feeds_targets and table.n == 62
        assert [e for e, v in verdicts.items() if v == "disagrees"] == [
            "comorbidity: dyslipidemia", "comorbidity: cardiovascular disease",
        ]
        assert sum(1 for v in verdicts.values() if v == "within_tolerance") == 8

    def test_the_other_four_conditions_are_all_n_too_small(self, load):
        for condition in ("COPD", "breast cancer", "heart failure", "rheumatoid arthritis"):
            table = derive(load, pack_for(condition))
            compared = [r for r in table.rows if r.prior is not None and r.synthea is not None]
            assert {r.verdict for r in compared} <= {"n_too_small"}, condition
