"""The Synthea loader joins by identity, excludes visibly, and invents nothing.

Fixtures first (`tests/fixtures/synthea/`, authored to break wrong joins), then
the committed real export. The rules under test were registered in
`tests/eval/synthea_targets.json` before the loader existed.
"""
import csv
import json
import random
import shutil
from datetime import date
from pathlib import Path

import pytest

from spp.ingest.synthea_loader import (
    CODE_MAP_PATH,
    FIELDS_NOT_SOURCED,
    SyntheaError,
    load_from_synthea,
    load_synthea,
)
from spp.schemas import PatientDNA

ROOT = Path(__file__).resolve().parents[1]
FIXTURES = ROOT / "tests" / "fixtures" / "synthea"
REAL = ROOT / "data" / "synthea" / "structural_seed11"


def by_id(load):
    return {(p.source_id, p.condition): p for p in load.patients}


def edited(tmp_path, table, mutate):
    """A copy of the fixtures with one table rewritten by `mutate(rows)`."""
    target = tmp_path / "export"
    shutil.copytree(FIXTURES, target)
    path = target / f"{table}.csv"
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fields, rows = reader.fieldnames, list(reader)
    rows = mutate(rows) or rows
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)
    return target


class TestJoinsByIdentity:
    def test_two_patients_sharing_a_name_stay_two_patients(self):
        """`Jordan Vance` twice: one diabetic, one with rheumatoid arthritis. A
        name join merges them into a patient with both and raises nothing."""
        records = by_id(load_synthea(FIXTURES))

        assert ("p-0005", "type 2 diabetes") in records
        assert ("p-0006", "rheumatoid arthritis") in records
        assert ("p-0005", "rheumatoid arthritis") not in records
        assert ("p-0006", "type 2 diabetes") not in records
        assert records[("p-0006", "rheumatoid arthritis")].comorbidities == ()

    def test_row_order_changes_nothing(self, tmp_path):
        """A positional join survives sorted fixtures and dies on shuffled ones."""
        def shuffle(rows):
            random.Random(7).shuffle(rows)
            return rows

        shuffled = edited(tmp_path, "conditions", shuffle)

        assert load_synthea(shuffled).patients == load_synthea(FIXTURES).patients

    def test_an_orphan_reference_is_an_error_not_a_dropped_row(self, tmp_path):
        def orphan(rows):
            rows[0]["PATIENT"] = "p-9999"

        with pytest.raises(SyntheaError, match="absent from patients.csv"):
            load_synthea(edited(tmp_path, "conditions", orphan))

    def test_a_duplicate_patient_id_is_refused(self, tmp_path):
        def duplicate(rows):
            rows[1]["Id"] = rows[0]["Id"]

        with pytest.raises(SyntheaError, match="not unique"):
            load_synthea(edited(tmp_path, "patients", duplicate))


class TestTheCardinalityCases:
    def test_concurrent_conditions_become_comorbidities(self):
        record = by_id(load_synthea(FIXTURES))[("p-0001", "type 2 diabetes")]

        assert record.comorbidities == ("CKD", "hypertension")

    def test_a_patient_with_no_condition_yields_no_record_and_is_counted(self):
        load = load_synthea(FIXTURES)

        assert not [p for p in load.patients if p.source_id == "p-0004"]
        assert load.report.living_without_pack_condition == 2

    def test_a_resolved_condition_is_not_a_candidate(self):
        """p-0003's breast cancer has a STOP date. Active means unstopped — the
        same definition the keep-modules commit to."""
        load = load_synthea(FIXTURES)

        assert not [p for p in load.patients if p.source_id == "p-0003"]
        assert load.report.resolved_pack_conditions == 1

    def test_two_dispenses_of_one_drug_are_one_membership(self):
        load = load_synthea(FIXTURES)
        record = by_id(load)[("p-0001", "type 2 diabetes")]

        assert record.medications == ("metformin",)
        assert load.report.medication_rows_mapped == 3

    def test_a_dispense_with_no_reason_is_not_linked_to_the_condition(self, tmp_path):
        """A mapped drug, an empty REASONCODE, a patient with COPD. Linking them
        would fabricate a treatment relationship the export never stated."""
        def add_unreasoned_metformin(rows):
            row = dict(next(r for r in rows if r["CODE"] == "860975"))
            row.update(PATIENT="p-0002", ENCOUNTER="e-0011", REASONCODE="",
                       REASONDESCRIPTION="")
            return rows + [row]

        load = load_synthea(edited(tmp_path, "medications", add_unreasoned_metformin))

        assert by_id(load)[("p-0002", "COPD")].medications == ()
        assert load.report.medication_rows_mapped_without_reason == 1

    def test_a_medication_for_another_condition_is_not_borrowed(self, tmp_path):
        """A patient with diabetes AND emphysema, an inhaler dispensed for the
        emphysema. Each record carries only the drug whose reason names it.

        The first version of this test asserted a drug absent from the fixtures
        was absent from the record, and passed against a loader that attributed
        every drug a patient takes to every condition they have.
        """
        target = edited(tmp_path, "conditions", lambda rows: rows + [{
            **rows[0], "PATIENT": "p-0005", "ENCOUNTER": "e-0031", "START": "2019-05-04",
            "CODE": "87433001", "DESCRIPTION": "Pulmonary emphysema (disorder)",
        }])
        path = target / "medications.csv"
        path.write_text(path.read_text() + (
            "2019-05-04,,p-0005,pay-3,e-0031,896209,"
            "60 ACTUAT Fluticasone propionate 0.25 MG/ACTUAT / salmeterol 0.05 MG/ACTUAT "
            "Dry Powder Inhaler,30.0,20.0,12,360.0,87433001,Pulmonary emphysema (disorder)\n"
        ))

        load = load_synthea(target)
        records = by_id(load)

        assert records[("p-0005", "type 2 diabetes")].medications == ("metformin",)
        assert records[("p-0005", "COPD")].medications == ("fluticasone/salmeterol",)
        assert records[("p-0005", "type 2 diabetes")].comorbidities == ("COPD",)
        assert load.report.living_with_several_pack_conditions == 1


class TestExclusionsAreVisible:
    def test_deceased_patients_are_excluded_and_counted(self, tmp_path):
        def kill(rows):
            next(r for r in rows if r["Id"] == "p-0001")["DEATHDATE"] = "2024-01-01"

        load = load_synthea(edited(tmp_path, "patients", kill))

        assert not [p for p in load.patients if p.source_id == "p-0001"]
        assert load.report.deceased_excluded == 1
        assert load.report.living == 5

    def test_a_missing_column_names_itself(self, tmp_path):
        target = tmp_path / "export"
        shutil.copytree(FIXTURES, target)
        path = target / "medications.csv"
        text = path.read_text().replace("REASONCODE", "REASON_CODE", 1)
        path.write_text(text)

        with pytest.raises(SyntheaError, match="REASONCODE"):
            load_synthea(target)

    def test_every_unsourced_field_is_named(self):
        """The fields Synthea was registered as unable to calibrate must all be
        declared not-sourced, so a schema default cannot pass for a measurement."""
        targets = json.loads((ROOT / "tests/eval/synthea_targets.json").read_text())
        registered = {"adherence_baseline" if f == "base_adherence" else f
                      for f in targets["synthea_cannot_calibrate"]} - {"dx_delay_months"}

        assert registered <= set(FIELDS_NOT_SOURCED)
        assert load_synthea(FIXTURES).report.fields_not_sourced == FIELDS_NOT_SOURCED


class TestNoClock:
    def test_as_of_comes_from_the_export_not_from_today(self):
        load = load_synthea(FIXTURES)

        assert load.report.as_of == date(2020, 3, 17)
        assert by_id(load)[("p-0001", "type 2 diabetes")].age == 65

    def test_an_explicit_as_of_moves_ages_and_nothing_else(self):
        early = by_id(load_synthea(FIXTURES, as_of=date(2020, 3, 17)))
        late = by_id(load_synthea(FIXTURES, as_of=date(2030, 3, 17)))

        assert set(early) == set(late)
        assert all(late[k].age == early[k].age + 10 for k in early)


class TestPatientDNA:
    def test_the_build_order_entry_point_returns_patient_dna(self):
        people = load_from_synthea(FIXTURES)

        assert len(people) == 4
        assert all(isinstance(p, PatientDNA) for p in people)

    def test_ids_are_unique_and_url_safe(self):
        ids = [p.patient_id for p in load_from_synthea(FIXTURES)]

        assert len(ids) == len(set(ids))
        assert all(i.startswith("synthea-") and " " not in i for i in ids)

    def test_a_missing_directory_is_a_clear_error(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            load_from_synthea(tmp_path / "nope")


class TestTheCodeMap:
    def test_every_code_carries_a_description_some_committed_export_states(self):
        """The map was built from exports, so it is held to them. An entry whose
        description matches no committed export is a code somebody typed."""
        exports = [d for d in sorted((ROOT / "data" / "synthea").iterdir())
                   if (d / "conditions.csv").exists()]
        if not exports:
            pytest.skip("no real Synthea export committed")
        real: dict[str, set[str]] = {}
        for export in exports:
            with (export / "conditions.csv").open(encoding="utf-8") as handle:
                for r in csv.DictReader(handle):
                    real.setdefault(r["CODE"], set()).add(r["DESCRIPTION"])
        raw = json.loads(CODE_MAP_PATH.read_text(encoding="utf-8"))

        for group in ("conditions", "comorbidities"):
            for name, entries in raw[group].items():
                for entry in entries:
                    assert entry["description"] in real.get(entry["code"], set()), (name, entry)

    def test_no_entry_is_left_unverified(self):
        """Rheumatoid arthritis was the one declared-unverified code until the
        calibration export contained it. Nothing may be marked unverified now
        without a test changing to say so."""
        raw = json.loads(CODE_MAP_PATH.read_text(encoding="utf-8"))
        unverified = [e["code"] for entries in raw["conditions"].values()
                      for e in entries if e.get("verified") is False]

        assert unverified == []


@pytest.mark.skipif(not (REAL / "patients.csv").exists(),
                    reason="no real Synthea export committed")
class TestTheRealExport:
    @pytest.fixture()
    def load(self):
        return load_synthea(REAL)

    def test_the_counts_match_the_registered_prevalence_finding(self, load):
        """113 generated, 13 deceased, and the living counts the finding in
        synthea_targets.json reported before this loader existed."""
        assert load.report.patients_total == 113
        assert load.report.deceased_excluded == 13
        assert load.report.records_by_condition == {
            "COPD": 2, "breast cancer": 3, "type 2 diabetes": 6,
        }

    def test_the_books_balance(self, load):
        report = load.report

        assert report.living + report.deceased_excluded == report.patients_total
        assert report.records >= report.living - report.living_without_pack_condition
        assert sum(report.records_by_condition.values()) == report.records

    def test_the_unmapped_report_is_not_empty_and_not_hidden(self, load):
        """Most active condition rows are social findings and encounter noise.
        The report must say so rather than present a clean join."""
        report = load.report

        assert report.condition_rows_unmapped > report.condition_rows_mapped
        assert report.top_unmapped_conditions
        assert report.top_unmapped_conditions[0].rows >= report.top_unmapped_conditions[-1].rows
        assert 0 < report.record_condition_rows_mapped <= report.record_condition_rows

    def test_metformin_reaches_diabetes_through_its_reason_code(self, load):
        diabetics = [p for p in load.patients if p.condition == "type 2 diabetes"]

        assert any("metformin" in p.medications for p in diabetics)
        assert all("metformin" not in p.medications
                   for p in load.patients if p.condition != "type 2 diabetes")
