"""Synthea CSV export -> joined patient records -> PatientDNA.

Synthea (https://github.com/synthetichealth/synthea) generates synthetic patient
histories from published statistics and clinical care maps. Its role here is
fixed by `tests/eval/synthea_targets.json`, registered before this module
existed: it is a **calibration source for the prior packs** — known *synthetic*
provenance, never quotable — and it may inform age, sex, stage, comorbidities and
medication membership, nothing else.

Four rules shape the code, each registered before a number was computed:

* **Join on the `PATIENT` id and nothing else.** Never on a name, never on row
  position. *Join by a key that is not unique* has cost this repository three
  wrong results; the fixtures carry two patients sharing a display name so that
  a name join fails there instead of here.
* **Deceased patients are excluded and counted.** The packs describe a
  population being recruited into a trial.
* **Mapping is an explicit committed table, by code** (`data/synthea/
  code_map.json`), and every run reports what the table did not cover. A mapping
  that quietly drops most condition rows yields clean-looking marginals from a
  population fragment.
* **A medication is attributed to a condition only through its `REASONCODE`.** A
  dispense with no stated reason is not linked to whatever the patient has.

What Synthea cannot supply is *not sourced* and says so: `LoadReport.
fields_not_sourced` names every `PatientDNA` field left at its schema default.
Derivation must read `SyntheaPatient`, which carries only sourced fields — a
default such as `adherence_baseline = 0.8` in a `PatientDNA` built here is a
placeholder, not data.
"""
from __future__ import annotations

import csv
import json
from collections import Counter
from datetime import date
from pathlib import Path

from pydantic import BaseModel, Field

from ..schemas import PatientDNA
from ..schemas.patient_dna import JourneyMilestone, Medication

CODE_MAP_PATH = Path(__file__).resolve().parents[3] / "data" / "synthea" / "code_map.json"

REQUIRED_COLUMNS: dict[str, tuple[str, ...]] = {
    "patients": ("Id", "BIRTHDATE", "DEATHDATE", "GENDER"),
    "conditions": ("START", "STOP", "PATIENT", "CODE", "DESCRIPTION"),
    "medications": ("START", "STOP", "PATIENT", "CODE", "DESCRIPTION", "REASONCODE"),
}

FIELDS_NOT_SOURCED: dict[str, str] = {
    "stage": "the packs' early/moderate/advanced ladder has no Synthea counterpart; "
             "deriving it needs its own registered rule",
    "biomarkers": "outside the registered target list",
    "adherence_baseline": "Synthea does not simulate adherence behaviour",
    "health_literacy": "not modelled by Synthea",
    "social_determinants": "deferred — Synthea's SDOH findings are module outputs and "
                           "miss transport, caregiver support and literacy",
    "goals": "not a Synthea concept",
    "constraints": "not a Synthea concept",
    "barriers": "derived from fields that are not sourced",
    "traits": "copula quantiles exist only for generated personas",
}

_SEX = {"M": "male", "F": "female"}
TOP_UNMAPPED = 15


class SyntheaError(ValueError):
    """The export does not have the shape this loader was verified against."""


class SyntheaPatient(BaseModel):
    """One living patient with one active pack condition. Sourced fields only."""

    model_config = {"frozen": True}

    source_id: str
    condition: str
    age: int
    sex: str
    diagnosed: date
    comorbidities: tuple[str, ...] = ()
    # Pack drug names whose dispense names this condition as its reason.
    medications: tuple[str, ...] = ()

    def to_dna(self) -> PatientDNA:
        """A `PatientDNA` with every unsourced field at its schema default."""
        slug = self.condition.lower().replace(" ", "-")
        return PatientDNA(
            patient_id=f"synthea-{slug}-{self.source_id}",
            age=self.age, sex=self.sex, condition=self.condition,
            comorbidities=list(self.comorbidities),
            medications=[Medication(name=name) for name in self.medications],
            journey=[JourneyMilestone(stage="diagnosis", when=self.diagnosed,
                                      note="first active condition row in the Synthea export")],
        )


class UnmappedCode(BaseModel):
    code: str
    description: str
    rows: int


class LoadReport(BaseModel):
    """What was read, what was excluded, and what the mapping did not cover."""

    csv_dir: str
    as_of: date
    manifest: dict = Field(default_factory=dict)

    patients_total: int = 0
    deceased_excluded: int = 0
    living: int = 0
    living_without_pack_condition: int = 0
    living_with_several_pack_conditions: int = 0
    # A pack condition on record but STOPped — resolved, so not a candidate.
    resolved_pack_conditions: int = 0
    records: int = 0
    records_by_condition: dict[str, int] = Field(default_factory=dict)

    # Over ACTIVE condition rows of LIVING patients.
    condition_rows: int = 0
    condition_rows_mapped: int = 0
    top_unmapped_conditions: list[UnmappedCode] = Field(default_factory=list)
    # The same count restricted to patients who produced a record. The figure
    # above is dominated by people with no pack condition at all; THIS is the one
    # that says how much of a record's own history the comorbidity map discards.
    record_condition_rows: int = 0
    record_condition_rows_mapped: int = 0

    # Over ACTIVE medication rows of LIVING patients.
    medication_rows: int = 0
    medication_rows_mapped: int = 0
    medication_rows_mapped_without_reason: int = 0
    top_unmapped_medications: list[UnmappedCode] = Field(default_factory=list)

    fields_not_sourced: dict[str, str] = Field(default_factory=lambda: dict(FIELDS_NOT_SOURCED))

    @property
    def condition_rows_unmapped(self) -> int:
        return self.condition_rows - self.condition_rows_mapped

    def headline(self) -> str:
        return (
            f"{self.records} records from {self.living} living patients "
            f"({self.deceased_excluded} deceased excluded of {self.patients_total}); "
            f"{self.condition_rows_unmapped} of {self.condition_rows} active condition "
            f"rows unmapped"
        )


class SyntheaLoad(BaseModel):
    patients: list[SyntheaPatient]
    report: LoadReport

    def to_dna(self) -> list[PatientDNA]:
        return [patient.to_dna() for patient in self.patients]


class CodeMap(BaseModel):
    """`code_map.json`, inverted for lookup. Matching is by code only."""

    condition_of: dict[str, str]
    comorbidity_of: dict[str, str]
    drug_of: dict[str, str]
    condition_codes: dict[str, frozenset[str]]

    @classmethod
    def load(cls, path: Path = CODE_MAP_PATH) -> CodeMap:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        condition_of = {e["code"]: name for name, entries in raw["conditions"].items()
                        for e in entries}
        comorbidity_of = {e["code"]: name for name, entries in raw["comorbidities"].items()
                          for e in entries}
        # A pack condition is also a comorbidity of every OTHER pack condition.
        for code, name in condition_of.items():
            comorbidity_of.setdefault(code, name)
        return cls(
            condition_of=condition_of, comorbidity_of=comorbidity_of,
            drug_of={code: e["drug"] for code, e in raw["medications"].items()},
            condition_codes={name: frozenset(e["code"] for e in entries)
                             for name, entries in raw["conditions"].items()},
        )


def _read(csv_dir: Path, table: str) -> list[dict[str, str]]:
    path = csv_dir / f"{table}.csv"
    if not path.exists():
        raise FileNotFoundError(f"{path} not found — not a Synthea CSV export")
    with path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        missing = [c for c in REQUIRED_COLUMNS[table] if c not in (reader.fieldnames or [])]
        if missing:
            raise SyntheaError(f"{table}.csv is missing columns {missing}")
        return list(reader)


def _day(value: str) -> date:
    return date.fromisoformat(value[:10])


def _age(born: date, as_of: date) -> int:
    return as_of.year - born.year - ((as_of.month, as_of.day) < (born.month, born.day))


def _top(counter: Counter) -> list[UnmappedCode]:
    ranked = sorted(counter.items(), key=lambda item: (-item[1], item[0]))
    return [UnmappedCode(code=code, description=desc, rows=rows)
            for (code, desc), rows in ranked[:TOP_UNMAPPED]]


def load_synthea(
    csv_dir: str | Path,
    as_of: date | None = None,
    limit: int | None = None,
    code_map: CodeMap | None = None,
) -> SyntheaLoad:
    """Join one export. Pure over its inputs: no clock, no RNG, no network.

    `as_of` defaults to the latest date in the export itself, never to today —
    ages computed against the wall clock would change the result of re-reading an
    unchanged export.
    """
    csv_dir = Path(csv_dir)
    code_map = code_map or CodeMap.load()
    patients = sorted(_read(csv_dir, "patients"), key=lambda row: row["Id"])
    conditions = _read(csv_dir, "conditions")
    medications = _read(csv_dir, "medications")

    ids = [row["Id"] for row in patients]
    if len(ids) != len(set(ids)):
        raise SyntheaError("patients.csv has duplicate Id values; the join key is not unique")
    known = set(ids)
    for table, rows in (("conditions", conditions), ("medications", medications)):
        orphans = {row["PATIENT"] for row in rows} - known
        if orphans:
            raise SyntheaError(
                f"{table}.csv references {len(orphans)} PATIENT id(s) absent from patients.csv"
            )

    if as_of is None:
        as_of = max(_day(row["START"]) for row in (*conditions, *medications))
    manifest_path = csv_dir / "MANIFEST.json"
    report = LoadReport(
        csv_dir=str(csv_dir), as_of=as_of,
        manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
        if manifest_path.exists() else {},
        patients_total=len(patients),
    )

    living = [row for row in patients if not row["DEATHDATE"]]
    report.deceased_excluded = len(patients) - len(living)
    if limit is not None:
        living = living[:limit]
    report.living = len(living)
    living_ids = {row["Id"] for row in living}

    active_conditions: dict[str, list[dict[str, str]]] = {}
    unmapped_conditions: Counter = Counter()
    resolved = 0
    for row in conditions:
        if row["PATIENT"] not in living_ids:
            continue
        if row["STOP"]:
            resolved += row["CODE"] in code_map.condition_of
            continue
        report.condition_rows += 1
        if row["CODE"] in code_map.comorbidity_of:
            report.condition_rows_mapped += 1
        else:
            unmapped_conditions[(row["CODE"], row["DESCRIPTION"])] += 1
        active_conditions.setdefault(row["PATIENT"], []).append(row)
    report.resolved_pack_conditions = resolved
    report.top_unmapped_conditions = _top(unmapped_conditions)

    # (patient, reason code) -> pack drug names. The reason code IS the link.
    drugs_for: dict[tuple[str, str], set[str]] = {}
    unmapped_medications: Counter = Counter()
    for row in medications:
        if row["PATIENT"] not in living_ids or row["STOP"]:
            continue
        report.medication_rows += 1
        drug = code_map.drug_of.get(row["CODE"])
        if drug is None:
            unmapped_medications[(row["CODE"], row["DESCRIPTION"])] += 1
            continue
        report.medication_rows_mapped += 1
        if not row["REASONCODE"]:
            report.medication_rows_mapped_without_reason += 1
            continue
        drugs_for.setdefault((row["PATIENT"], row["REASONCODE"]), set()).add(drug)
    report.top_unmapped_medications = _top(unmapped_medications)

    records: list[SyntheaPatient] = []
    for row in living:
        mine = active_conditions.get(row["Id"], [])
        pack_conditions = sorted({code_map.condition_of[c["CODE"]] for c in mine
                                  if c["CODE"] in code_map.condition_of})
        if not pack_conditions:
            report.living_without_pack_condition += 1
            continue
        report.living_with_several_pack_conditions += len(pack_conditions) > 1
        report.record_condition_rows += len(mine)
        report.record_condition_rows_mapped += sum(
            1 for c in mine if c["CODE"] in code_map.comorbidity_of
        )
        for condition in pack_conditions:
            codes = code_map.condition_codes[condition]
            comorbidities = sorted({
                code_map.comorbidity_of[c["CODE"]] for c in mine
                if c["CODE"] in code_map.comorbidity_of and c["CODE"] not in codes
            })
            drugs: set[str] = set()
            for code in codes:
                drugs |= drugs_for.get((row["Id"], code), set())
            records.append(SyntheaPatient(
                source_id=row["Id"], condition=condition,
                age=_age(_day(row["BIRTHDATE"]), as_of),
                sex=_SEX.get(row["GENDER"], "other"),
                diagnosed=min(_day(c["START"]) for c in mine if c["CODE"] in codes),
                comorbidities=tuple(comorbidities), medications=tuple(sorted(drugs)),
            ))

    report.records = len(records)
    report.records_by_condition = dict(sorted(Counter(r.condition for r in records).items()))
    return SyntheaLoad(patients=records, report=report)


def load_from_synthea(csv_dir: str | Path, limit: int | None = None) -> list[PatientDNA]:
    """Build-order item 1: real Synthea CSV joins -> PatientDNA.

    The thin form. Anything that derives a statistic should call `load_synthea`
    and read `SyntheaPatient`, which cannot carry a schema default as if it were
    a measurement, and should print the `LoadReport` beside whatever it derives.
    """
    csv_dir = Path(csv_dir)
    if not csv_dir.exists():
        raise FileNotFoundError(
            f"{csv_dir} not found. Generate data with Synthea first (see README > Data)."
        )
    return load_synthea(csv_dir, limit=limit).to_dna()
