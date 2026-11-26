"""The Synthea-vs-prior table: thresholds read, never restated; no row upgrades itself.

Records are built by hand here so the sample size and the values are chosen by
the test rather than by whatever an export happens to contain.
"""
import hashlib
import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

from spp.cohort.packs import PACK_DIR, pack_for
from spp.ingest.synthea_derive import TARGETS_PATH, derive
from spp.ingest.synthea_loader import LoadReport, SyntheaLoad, SyntheaPatient, load_synthea

ROOT = Path(__file__).resolve().parents[1]
REAL = ROOT / "data" / "synthea" / "structural_seed11"
CALIBRATION = {"purpose": "calibration run", "jar_sha256": "abc", "seed": 1,
               "population_flag": "-p 1000"}
STRUCTURAL = {"purpose": "structural-validation run ONLY — feeds NO calibration target"}


def cohort(n, *, age=62, female_share=0.48, hypertension_share=0.7, manifest=CALIBRATION):
    people = [
        SyntheaPatient(
            source_id=f"s-{i:04d}", condition="type 2 diabetes", age=age,
            sex="female" if i < round(n * female_share) else "male",
            diagnosed=date(2020, 1, 1),
            comorbidities=("hypertension",) if i < round(n * hypertension_share) else (),
            medications=("metformin",),
        )
        for i in range(n)
    ]
    report = LoadReport(csv_dir="synthetic", as_of=date(2026, 1, 1), manifest=manifest,
                        patients_total=n, living=n, records=n)
    return SyntheaLoad(patients=people, report=report)


def row(table, entry):
    return next(r for r in table.rows if r.entry == entry)


@pytest.fixture(scope="module")
def pack():
    return pack_for("type 2 diabetes")


class TestVerdictsAtAdequateN:
    def test_a_value_inside_the_entrys_own_tolerance_agrees(self, pack):
        table = derive(cohort(60), pack)

        assert table.feeds_targets
        assert row(table, "age (mean)").verdict == "within_tolerance"
        assert row(table, "comorbidity: hypertension").verdict == "within_tolerance"

    def test_a_value_outside_it_disagrees(self, pack):
        """The age tolerance in the pack is 4.0 years; 70 against 62 is outside."""
        table = derive(cohort(60, age=70, hypertension_share=0.2), pack)

        assert row(table, "age (mean)").verdict == "disagrees"
        assert row(table, "comorbidity: hypertension").verdict == "disagrees"

    def test_the_threshold_is_the_packs_number_not_this_modules(self, pack):
        """Widen the pack entry's tolerance and the same data stops disagreeing.
        Nothing in the derivation holds a tolerance of its own."""
        widened = pack.model_copy(deep=True)
        next(m for m in widened.marginals if m.field == "age").tolerance = 20.0

        assert row(derive(cohort(60, age=70), pack), "age (mean)").verdict == "disagrees"
        assert row(derive(cohort(60, age=70), widened), "age (mean)").verdict == "within_tolerance"


class TestNoRowUpgradesItself:
    def test_below_the_floor_every_comparison_is_n_too_small(self, pack):
        table = derive(cohort(49), pack)

        compared = [r for r in table.rows if r.prior is not None and r.synthea is not None]
        assert compared
        assert {r.verdict for r in compared} == {"n_too_small"}

    def test_the_floor_is_read_from_the_registration(self, pack, tmp_path):
        """49 records fail a floor of 50 and pass a floor of 10 — with the floor
        changed only in the targets file."""
        targets = json.loads(TARGETS_PATH.read_text(encoding="utf-8"))
        assert targets["sample_size_discipline"]["n_threshold"]["value"] == 50
        targets["sample_size_discipline"]["n_threshold"]["value"] = 10
        lowered = tmp_path / "targets.json"
        lowered.write_text(json.dumps(targets))

        assert row(derive(cohort(49), pack), "age (mean)").verdict == "n_too_small"
        assert row(derive(cohort(49), pack, targets_path=lowered),
                   "age (mean)").verdict == "within_tolerance"

    def test_a_structural_run_cannot_produce_an_adoptable_verdict(self, pack):
        """Even at n=60. The two-run rule exists so nobody sizes a decision on the
        structural export; here it cannot happen by accident."""
        table = derive(cohort(60, age=70, manifest=STRUCTURAL), pack)

        assert not table.feeds_targets
        assert not {r.verdict for r in table.rows} & {"within_tolerance", "disagrees"}
        assert row(table, "age (mean)").verdict == "illustrative"

    def test_an_export_with_no_manifest_feeds_no_target(self, pack):
        table = derive(cohort(60, manifest={}), pack)

        assert not table.feeds_targets
        assert "MANIFEST" in table.why_not

    def test_medication_rows_carry_a_rate_and_no_verdict(self, pack):
        table = derive(cohort(60), pack)
        metformin = row(table, "on metformin")

        assert metformin.verdict == "no_prior"
        assert metformin.synthea == 1.0 and metformin.prior is None

    def test_stage_and_the_unsourceable_fields_say_so(self, pack):
        table = derive(cohort(60), pack)

        assert row(table, "stage").verdict == "not_sourced"
        assert row(table, "health_literacy").verdict == "not_sourced"
        assert row(table, "comorbidity: depression").verdict == "not_sourced"


class TestItWritesNothing:
    def test_the_prior_packs_are_byte_identical_afterwards(self, pack):
        def digest():
            return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()
                    for p in sorted(PACK_DIR.glob("*.json"))}

        before = digest()
        derive(cohort(60, age=70), pack)

        assert digest() == before


@pytest.mark.skipif(not (REAL / "patients.csv").exists(),
                    reason="no real Synthea export committed")
class TestOnTheStructuralExport:
    def test_the_committed_export_feeds_no_target(self, pack):
        table = derive(load_synthea(REAL), pack)

        assert table.n == 6
        assert not table.feeds_targets
        assert not {r.verdict for r in table.rows} & {"within_tolerance", "disagrees"}

    def test_the_script_exits_nonzero_on_it(self):
        result = subprocess.run(
            [sys.executable, "-B", str(ROOT / "scripts" / "derive_synthea_marginals.py"),
             "--export", str(REAL), "--condition", "type 2 diabetes"],
            capture_output=True, text=True, env={"PYTHONPATH": "src", "PATH": "/usr/bin:/bin"},
        )

        assert result.returncode == 3
        assert "FEEDS NO TARGET" in result.stdout
