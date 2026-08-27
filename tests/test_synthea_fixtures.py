"""The fixtures must break the wrong joins, here, before the real run.

The structural diff (`test_synthea_structure.py`, once a real run exists) catches
schema drift: columns, types, enum values. It cannot catch join-logic bugs, which
only appear under realistic cardinality — and *join by a key that is not unique*
has appeared four times in this repository, three of them after the fact.

So these fixtures are authored to make a positional or name-based join fail
loudly. The load-bearing case is two patients sharing a display name and nothing
else: `Jordan Vance` twice, different UUIDs, different conditions. A join keyed on
a name produces one patient with both diabetes and rheumatoid arthritis, and
raises nothing.
"""
import csv
from collections import Counter
from pathlib import Path

import pytest

FIXTURES = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "synthea"


def rows(name: str) -> list[dict]:
    with (FIXTURES / f"{name}.csv").open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


class TestTheJoinTraps:
    def test_two_patients_share_a_display_name(self):
        """The trap. Any join keyed on a name rather than the UUID silently
        merges these two, and the merged patient looks perfectly plausible."""
        names = Counter((p["FIRST"], p["LAST"]) for p in rows("patients"))
        shared = [name for name, n in names.items() if n > 1]

        assert shared, "the name-collision fixture is missing"
        ids = {p["Id"] for p in rows("patients")
               if (p["FIRST"], p["LAST"]) == shared[0]}
        assert len(ids) == 2

        conditions = {p: {c["CODE"] for c in rows("conditions") if c["PATIENT"] == p}
                      for p in ids}
        assert len(set(map(frozenset, conditions.values()))) == 2, (
            "the colliding patients must carry DIFFERENT conditions, or merging "
            "them would be undetectable"
        )

    def test_a_patient_has_zero_conditions(self):
        with_conditions = {c["PATIENT"] for c in rows("conditions")}
        empty = [p["Id"] for p in rows("patients") if p["Id"] not in with_conditions]

        assert empty, "no zero-condition patient — the drop/duplicate case is untested"

    def test_a_patient_has_multiple_concurrent_conditions(self):
        """The comorbidity join's real case: overlapping, unstopped conditions."""
        counts = Counter(c["PATIENT"] for c in rows("conditions") if not c["STOP"])

        assert max(counts.values()) >= 3

    def test_a_medication_has_no_matching_condition(self):
        """REASONCODE empty. A loader must not fabricate a link to whatever
        condition the patient happens to have."""
        assert any(not m["REASONCODE"] for m in rows("medications"))

    def test_a_condition_has_no_medications(self):
        treated = {m["REASONCODE"] for m in rows("medications") if m["REASONCODE"]}
        untreated = [c for c in rows("conditions") if c["CODE"] not in treated]

        assert untreated, "no untreated condition — the outer-join case is untested"

    def test_duplicate_looking_rows_are_legitimately_distinct(self):
        """Same patient, same medication code, different encounter and date. A
        naive de-duplication on (PATIENT, CODE) would drop a real dispense."""
        meds = rows("medications")
        keyed = Counter((m["PATIENT"], m["CODE"]) for m in meds)
        repeated = [k for k, n in keyed.items() if n > 1]

        assert repeated, "no duplicate-looking rows"
        pair = [m for m in meds if (m["PATIENT"], m["CODE"]) == repeated[0]]
        assert len({m["ENCOUNTER"] for m in pair}) == len(pair)
        assert len({m["START"] for m in pair}) == len(pair)


class TestReferentialIntegrity:
    @pytest.mark.parametrize("table", ["conditions", "medications", "observations",
                                       "encounters"])
    def test_every_patient_reference_resolves(self, table):
        known = {p["Id"] for p in rows("patients")}

        assert {r["PATIENT"] for r in rows(table)} <= known

    @pytest.mark.parametrize("table", ["conditions", "medications", "observations"])
    def test_every_encounter_reference_resolves(self, table):
        known = {e["Id"] for e in rows("encounters")}
        referenced = {r["ENCOUNTER"] for r in rows(table) if r["ENCOUNTER"]}

        assert referenced <= known

    def test_patient_ids_are_unique(self):
        ids = [p["Id"] for p in rows("patients")]

        assert len(ids) == len(set(ids))
