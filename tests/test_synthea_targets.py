"""The Synthea target list is a commitment, and the enum is not a scale.

Two things this pins, both of which bake into the pack format and are expensive
to change later.

**Quotability keys on KIND, not on confidence.** `Confidence` is an ordered scale
and stays one for the assumption ledger. Provenance kind is a different axis: an
expert guess and a Synthea-derived value can both be wrong, and they are wrong
differently — unknown provenance against *known synthetic* provenance. Ranking
Synthea above guess on an ordered scale would eventually read as "quotable once
high enough", which is the inflation path. Only `CUSTOMER_DATA_FITTED` crosses
the line.

**The target list was committed before the loader existed.** A list discovered
during implementation is a list shaped by what turned out to be easy — and the
fields Synthea is weakest on (transport, caregiver support, literacy, adherence)
are exactly the ones this product leans on hardest.
"""
import json
from pathlib import Path

import pytest

from spp.cohort.packs import (
    QUOTABLE_KINDS,
    REQUIRED_FIELDS,
    Provenance,
    ProvenanceKind,
    load_all_packs,
)

TARGETS = json.loads(
    (Path(__file__).resolve().parents[1] / "tests" / "eval" / "synthea_targets.json")
    .read_text(encoding="utf-8")
)
CAN = set(TARGETS["synthea_can_calibrate"])
CANNOT = set(TARGETS["synthea_cannot_calibrate"])


class TestTheTargetListIsComplete:
    def test_every_required_field_is_classified(self):
        """A field in neither list is a decision nobody made."""
        assert (CAN | CANNOT) >= set(REQUIRED_FIELDS)

    def test_no_field_is_in_both(self):
        assert not (CAN & CANNOT)

    @pytest.mark.parametrize(
        "field", sorted({"social_determinants", "health_literacy", "base_adherence"})
    )
    def test_the_barrier_generating_fields_are_off_limits(self, field):
        """Named individually because these are the ones a future contributor
        will be most tempted to calibrate: they matter most to the product, and
        Synthea's coverage of them is thin and US-centric."""
        assert field in CANNOT


class TestQuotabilityKeysOnKind:
    def test_only_customer_data_is_quotable(self):
        assert QUOTABLE_KINDS == {ProvenanceKind.CUSTOMER_DATA_FITTED}

    def test_synthea_calibrated_is_not_quotable(self):
        """The whole point. Better-documented assumption, still an assumption."""
        p = Provenance(source="s", kind=ProvenanceKind.SYNTHEA_CALIBRATED,
                       synthea_version="3.3.0", synthea_seed=1)

        assert not p.quotable
        assert "not real-world epidemiology" in p.caveat

    def test_raising_confidence_alone_cannot_make_an_entry_quotable(self):
        """The inflation path, closed. Confidence is a different axis and moving
        it must not open the gate."""
        from spp.foundation.ledger import Confidence

        p = Provenance(source="s", confidence=Confidence.MEASURED)

        assert p.kind is ProvenanceKind.EXPERT_GUESS
        assert not p.quotable


class TestASyntheaEntryMustNameItsRun:
    def test_unversioned_calibration_is_refused(self):
        """Synthea is deterministic given (version, seed). A target that cannot
        name the run that produced it is the digest-pinning lesson forgotten."""
        with pytest.raises(ValueError, match="Synthea version"):
            Provenance(source="s", kind=ProvenanceKind.SYNTHEA_CALIBRATED)


class TestTodaysPacksAreHonest:
    def test_every_shipped_entry_is_still_an_expert_guess(self):
        """Baseline for the demo sentence: 'all expert guesses today; watch this
        one move'. When the loader lands, this test changes deliberately and the
        diff shows exactly which entries moved."""
        for pack in load_all_packs().values():
            for marginal in pack.marginals:
                assert marginal.provenance.kind is ProvenanceKind.EXPERT_GUESS
                assert not marginal.provenance.quotable
