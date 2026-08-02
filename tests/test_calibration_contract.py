"""Calibration contracts: the PSD gate, and retention bands rather than points.

Two invariants that are easy to lose in a refactor and expensive to lose quietly.

**PSD gate.** A hand-specified 21-pair correlation matrix goes non-positive-
definite easily — one more strong entry can do it. The gate must fail loudly, and
must NOT silently project: projection moves entries, which would break the
invariant that the ledger number is the latent correlation actually sampled.

**Retention bands.** The hazard is calibrated to plausibility targets, not fitted
to data, so pinning point values would assert precision the model does not have
and would break on every legitimate recalibration. What must survive is the
ordering across intensities and the rough spread — which is exactly what the
"read differences, not absolutes" framing claims the tool provides.
"""
from datetime import date

import numpy as np
import pytest

from spp.assumptions import CORRELATION_PSD_GATE, DROPOUT_HAZARD, TRAIT_CORRELATIONS
from spp.cohort import generate_cohort
from spp.cohort.correlation import (
    TRAIT_AXES,
    NotPositiveDefinite,
    assemble_matrix,
    build_correlation_matrix,
    is_positive_definite,
)
from spp.protocol import ProtocolBurden
from spp.simulation import retention_summary, schedule_from_protocol, simulate_cohort

AS_OF = date(2026, 8, 1)


@pytest.fixture(scope="module")
def cohort():
    return generate_cohort("type 2 diabetes", 400, seed=42, as_of=AS_OF)


def retention(cohort, protocol: ProtocolBurden) -> float:
    logs = simulate_cohort(
        cohort, schedule_from_protocol(protocol, 365), seed=42,
        washout=protocol.washout_required,
    )
    return retention_summary(logs)["retention_rate"]


class TestPSDGate:
    def test_the_shipped_matrix_is_comfortably_positive_definite(self):
        """Headroom matters: this is what tells you the next edit is safe."""
        pairs = {tuple(k.split("|")): v for k, v in TRAIT_CORRELATIONS.params.items()}
        matrix, corrections = build_correlation_matrix(pairs)

        assert corrections == [], "shipped matrix must need no projection"
        assert is_positive_definite(matrix)
        smallest = float(np.linalg.eigvalsh(matrix)[0])
        assert smallest > CORRELATION_PSD_GATE.params["min_eigenvalue"]
        assert smallest > 0.01, (
            f"min eigenvalue {smallest:.4f} leaves little headroom; the next "
            "correlation edit may push the matrix non-PSD"
        )

    def test_an_inconsistent_specification_fails_loudly(self):
        """a~b strongly, b~c strongly, a~c strongly negative is not a matrix."""
        pairs = {
            ("age", "mobility"): 0.95,
            ("mobility", "financial_security"): 0.95,
            ("age", "financial_security"): -0.95,
        }
        with pytest.raises(NotPositiveDefinite) as raised:
            build_correlation_matrix(pairs)

        assert "not positive definite" in str(raised.value)
        assert raised.value.min_eigenvalue < 0
        assert raised.value.culprits, "error must name the axes to revisit"

    def test_projection_is_off_by_default(self):
        assert CORRELATION_PSD_GATE.params["allow_projection"] is False

    def test_projection_when_enabled_reports_exactly_what_moved(self):
        pairs = {
            ("age", "mobility"): 0.95,
            ("mobility", "financial_security"): 0.95,
            ("age", "financial_security"): -0.95,
        }
        matrix, corrections = build_correlation_matrix(pairs, allow_projection=True)

        assert is_positive_definite(matrix)
        assert corrections, "a projection that moved nothing is a contradiction"
        for correction in corrections:
            assert correction.delta != 0.0
            assert correction.axis_a in TRAIT_AXES
            assert "->" in correction.describe()

    def test_projection_actually_changes_the_specification(self):
        """The reason it is off by default, stated as a test."""
        pairs = {
            ("age", "mobility"): 0.95,
            ("mobility", "financial_security"): 0.95,
            ("age", "financial_security"): -0.95,
        }
        raw = assemble_matrix(pairs)
        projected, corrections = build_correlation_matrix(pairs, allow_projection=True)
        moved = {(c.axis_a, c.axis_b) for c in corrections}

        assert moved, "projection must be reported"
        index = {name: i for i, name in enumerate(TRAIT_AXES)}
        for left, right in moved:
            i, j = index[left], index[right]
            assert raw[i, j] != pytest.approx(projected[i, j]), (
                "a moved pair must actually differ — otherwise the report lies"
            )

    def test_out_of_range_and_unknown_axes_are_rejected(self):
        with pytest.raises(ValueError, match="out of range"):
            build_correlation_matrix({("age", "mobility"): 1.4})
        with pytest.raises(KeyError, match="unknown trait axis"):
            build_correlation_matrix({("age", "astrological_sign"): 0.3})


class TestRetentionBands:
    """Ordering and spread, never point values."""

    LIGHT = ProtocolBurden(visits_per_year=4, travel_required=False)
    TYPICAL = ProtocolBurden(visits_per_year=12)
    HEAVY = ProtocolBurden(
        visits_per_year=24, daily_diary=True, washout_required=True
    )

    def test_retention_is_ordered_by_intensity(self, cohort):
        light = retention(cohort, self.LIGHT)
        typical = retention(cohort, self.TYPICAL)
        heavy = retention(cohort, self.HEAVY)
        assert heavy < typical < light

    def test_anchor_bands_hold(self, cohort):
        """The two designs the hazard was fitted to."""
        assert 0.88 <= retention(cohort, self.LIGHT) <= 0.98
        assert 0.45 <= retention(cohort, self.HEAVY) <= 0.65

    def test_held_out_design_lands_in_a_plausible_band(self, cohort):
        """The mid-intensity protocol is NOT an anchor. It was never fitted, so
        landing in band is the evidence the two-parameter form generalises rather
        than interpolating between the anchors."""
        typical = retention(cohort, self.TYPICAL)
        assert 0.70 <= typical <= 0.90, (
            f"held-out 12-visit retention {typical:.1%} left the plausible band; "
            "re-run scripts/calibrate_hazard.py and check the anchors still hold"
        )

    def test_the_spread_between_designs_is_material(self, cohort):
        """The product claim is that design choices move retention visibly. If the
        spread collapses, the tool stops discriminating and says nothing useful."""
        spread = retention(cohort, self.LIGHT) - retention(cohort, self.HEAVY)
        assert spread > 0.25, f"design spread {spread:.1%} is too small to act on"

    def test_bands_survive_a_different_master_seed(self):
        """The fit was conditioned on one draw, and the objective is a step
        function in the seeds. If the bands only hold for seed 42, the intercept
        was calibrated to a quantization artifact rather than to the population.

        This re-runs the ANCHOR CHECK, never the fit.
        """
        other = generate_cohort("type 2 diabetes", 400, seed=1234, as_of=AS_OF)

        def retain(protocol: ProtocolBurden) -> float:
            logs = simulate_cohort(
                other, schedule_from_protocol(protocol, 365), seed=1234,
                washout=protocol.washout_required,
            )
            return retention_summary(logs)["retention_rate"]

        light, typical, heavy = retain(self.LIGHT), retain(self.TYPICAL), retain(self.HEAVY)
        assert heavy < typical < light
        assert 0.88 <= light <= 0.98, f"light {light:.1%} under a different seed"
        assert 0.45 <= heavy <= 0.65, f"heavy {heavy:.1%} under a different seed"
        assert 0.70 <= typical <= 0.90, f"typical {typical:.1%} under a different seed"

    def test_removing_travel_improves_retention_at_equal_visit_count(self, cohort):
        """Holding visit count fixed and varying per-visit burden — the comparison
        the current two anchors cannot separate (see the weak-identification note
        on timeline.dropout_hazard), and the one a user will actually run."""
        onsite = retention(cohort, ProtocolBurden(visits_per_year=12))
        remote = retention(
            cohort, ProtocolBurden(visits_per_year=12, travel_required=False)
        )
        assert remote > onsite


class TestCalibrationProvenance:
    def test_the_hazard_records_how_it_was_calibrated(self):
        source = DROPOUT_HAZARD.source
        assert "calibrate_hazard.py" in source
        assert "HELD OUT" in source
        assert "NOT a fit to any observed dataset" in source

    def test_the_unidentifiable_term_is_frozen_not_fitted(self):
        """A ledger number reads as calibrated regardless of its source note, so
        an unidentifiable parameter must sit at an obviously-chosen value."""
        assert DROPOUT_HAZARD.params["cumulative_burden_weight"] == 0.0
        assert "FROZEN AT ZERO" in DROPOUT_HAZARD.source
        assert "THIRD-ANCHOR PLAN" in DROPOUT_HAZARD.source

    def test_the_correlation_semantics_are_pinned(self):
        description = TRAIT_CORRELATIONS.description
        assert "LATENT GAUSSIAN" in description
        assert "asserted UNCORRELATED" in description
