# Synthea CSV fixtures

Written **from the published Synthea CSV data dictionary**, not exported from a
Synthea run. That distinction is the whole reason `test_synthea_structure.py`
exists: these files encode what the interface is *believed* to be, and the
structural diff against one real ~100-patient run is what converts *"the loader
works on my fixtures"* into *"the fixtures match reality."*

**If the real run contradicts a fixture, the fixture was the bug.** Same verdict
this project gave the eval authored from retrieval output.

## The rows are chosen to break joins, not to look plausible

Synthea joins on `PATIENT` UUIDs across files. Join-by-a-key-that-is-not-unique
has appeared four times in this repository, so the fixtures make the wrong join
fail *here* rather than in the real run:

| case | patient | why |
|---|---|---|
| zero conditions | `p-0004` | a patient the condition join must not drop or duplicate |
| multiple concurrent conditions | `p-0001` | the comorbidity join's real case |
| medication with no matching condition | `p-0002` | REASONCODE empty — must not fabricate a link |
| condition with no medications | `p-0003` | the outer-join case |
| legitimately distinct duplicate-looking rows | `p-0001` | two encounters, same code, different dates |
| **two patients sharing a display name** | `p-0005`, `p-0006` | **a name-based join must break here** |

The last row is the load-bearing one. `Jordan Vance` appears twice with different
UUIDs and different conditions, so any join that keys on a name rather than an id
produces a patient with both conditions and no error.


## What the first structural diff caught — 2026-08-27

The fixtures were authored from the published data dictionary. A real export
(113 patients, seed 11, jar `018ad7f0…`) arrived and the diff fired **twice**:

| | fixture said | reality says |
|---|---|---|
| `patients.csv` | no `MIDDLE` column | `MIDDLE` sits between `FIRST` and `LAST` |
| `conditions.SYSTEM` | `http://snomed.info/sct` | `SNOMED-CT` |

Both fixtures were wrong and both are corrected. The `SYSTEM` one is the more
instructive: it *parsed*, it looked like a plausible SNOMED identifier, and it
would have had the loader tested against a vocabulary that does not exist. A
column that goes missing announces itself; an invented enum value does not.

Three columns the manifest flagged as likely misses — `SYSTEM`, `FIPS`, `INCOME` —
were already present and correct. So the dictionary this was written from was
current in structure and wrong in two details, which is roughly the failure rate
a documentation page earns and exactly why the diff is the deliverable rather
than the fixtures.
