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
