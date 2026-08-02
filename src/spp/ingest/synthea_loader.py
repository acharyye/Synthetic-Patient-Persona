"""Map Synthea output -> PatientDNA.

Synthea (https://github.com/synthetichealth/synthea) generates realistic synthetic
patient histories (FHIR or CSV). Use it to seed statistically plausible Patient DNA
WITHOUT touching any protected data.

TODO(claude-code):
  1. Run Synthea to produce CSV (patients.csv, conditions.csv, medications.csv, ...).
  2. Point `csv_dir` at the output and implement the joins below.
"""
from __future__ import annotations

from pathlib import Path

from ..schemas import PatientDNA


def load_from_synthea(csv_dir: str | Path, limit: int | None = None) -> list[PatientDNA]:
    csv_dir = Path(csv_dir)
    if not csv_dir.exists():
        raise FileNotFoundError(
            f"{csv_dir} not found. Generate data with Synthea first "
            "(see README > Data). Returning early."
        )
    # TODO(claude-code): read patients/conditions/medications with pandas and join
    # on PATIENT id to build one PatientDNA per person.
    raise NotImplementedError("Implement Synthea CSV joins -> PatientDNA.")
