"""Cohort Studio: bands from the pack itself, diff over the migration walker."""
import pytest
from fastapi.testclient import TestClient

from spp.api.main import app
from spp.cohort.packs import load_all_packs, pack_for
from spp.report import compare_cohorts, diff_artifacts, studio_view, walk_leaves

client = TestClient(app)
PACKS = sorted(load_all_packs())


class TestBandsComeFromThePack:
    @pytest.mark.parametrize("condition", PACKS)
    def test_every_tolerance_is_read_from_its_pack_entry(self, condition):
        """Not transcribed. A constant here would be a second copy that drifts,
        and the chart would show green while the contract test went red."""
        pack = pack_for(condition)
        view = studio_view(condition, n=200, seed=42)

        for band in view.bands:
            assert band.tolerance == pack.marginal(band.field).tolerance, band.field

    @pytest.mark.parametrize("condition", PACKS)
    def test_provenance_travels_with_every_band(self, condition):
        for band in studio_view(condition, n=200, seed=42).bands:
            assert band.source
            assert band.confidence

    def test_structurally_modulated_fields_carry_their_warning(self):
        """comorbidities is shifted by mechanisms outside the copula; the pack
        declares it, so the chart must too."""
        view = studio_view("type 2 diabetes", n=200, seed=42)
        comorbidity = next(b for b in view.bands if b.field == "comorbidities")
        assert comorbidity.structural_paths

    @pytest.mark.parametrize("condition", PACKS)
    def test_the_shipped_packs_are_in_band(self, condition):
        """The visual twin of the contract suite — it should agree with it."""
        view = studio_view(condition, n=400, seed=42)
        assert view.out_of_band == [], [b.field for b in view.out_of_band]

    def test_an_unmapped_condition_degrades_without_inventing_bands(self):
        view = studio_view("a condition nobody packed", n=50, seed=42)
        assert view.pack == "generic"
        assert view.bands == []


class TestDiffReusesTheWalker:
    def test_the_walker_finds_leaf_paths(self):
        paths = dict(walk_leaves({"a": {"b": 1}, "c": [2, 3]}))
        assert paths == {".a.b": 1, ".c[0]": 2, ".c[1]": 3}

    def test_identical_artifacts_report_no_change(self):
        payload = {"x": 1, "y": [1, 2]}
        diff = diff_artifacts(payload, dict(payload))
        assert diff.changed == 0
        assert diff.unchanged == 3

    def test_added_and_removed_leaves_are_distinguished(self):
        diff = diff_artifacts({"a": 1, "b": 2}, {"a": 1, "c": 3})
        kinds = {c.path: c.kind for c in diff.changes}
        assert kinds == {".b": "removed", ".c": "added"}

    def test_numeric_delta_is_available_for_charts(self):
        change = diff_artifacts({"n": 10}, {"n": 12}).changes[0]
        assert change.numeric_delta == 2.0

    def test_only_touches_answers_the_migration_question(self):
        """The check the persona-id migration needed: did ONLY the thing I meant
        to change actually change?"""
        diff = diff_artifacts(
            {"patient_id": "old", "age": 60}, {"patient_id": "new", "age": 60})
        assert diff.only_touches("patient_id")
        assert not diff.only_touches("age")


class TestComparisonMode:
    """Per-persona rows only under identity pairing — an invariant, not an option.

    Within a run, CRN makes a paired diff exact: same persona, one design change,
    the delta is signal. Across seeds, persona i on each side is an independent
    draw — exchangeable strangers. Rendering a per-pair delta between them in the
    flip table's visual language lends noise the authority that table earned.
    """

    def test_same_seed_pairs_by_identity(self):
        comparison = compare_cohorts("COPD", 42, 42, n=100)
        assert comparison.mode == "identity"
        assert comparison.persona_changes == []
        assert comparison.summary_diff.changed == 0

    def test_different_seeds_go_distributional(self):
        comparison = compare_cohorts("COPD", 42, 43, n=100)
        assert comparison.mode == "distributional"
        assert comparison.marginals, "must compare against pack targets instead"

    @pytest.mark.parametrize("mode_kwargs", [{}, {"allow_determinism_debug": True}])
    def test_no_per_persona_rows_outside_identity_pairing(self, mode_kwargs):
        """THE invariant. Whatever the mode, if it is not identity pairing there
        are no per-persona rows to misread."""
        comparison = compare_cohorts("COPD", 42, 43, n=100, **mode_kwargs)
        assert comparison.mode != "identity"
        assert comparison.persona_changes == []

    def test_determinism_debug_says_what_it_is_on_its_face(self):
        comparison = compare_cohorts(
            "COPD", 42, 43, n=50, allow_determinism_debug=True)
        assert comparison.mode == "determinism_debug"
        assert "DETERMINISM DEBUG ONLY" in comparison.note
        assert "sampling noise" in comparison.note

    def test_the_distributional_note_explains_the_refusal(self):
        note = compare_cohorts("COPD", 42, 43, n=50).note
        assert "independent draw" in note
        assert "sampling noise" in note

    def test_both_cohorts_are_scored_against_the_same_pack_target(self):
        comparison = compare_cohorts("type 2 diabetes", 42, 43, n=300)
        for marginal in comparison.marginals:
            assert marginal.tolerance > 0
            assert marginal.source, "provenance travels with the number"
            # Same target on both sides — the contract machinery, two cohorts.
            assert marginal.left_within == (
                abs(marginal.left - marginal.target) <= marginal.tolerance)

    def test_two_seeds_of_the_same_pack_mostly_agree(self):
        comparison = compare_cohorts("type 2 diabetes", 42, 43, n=400)
        assert len(comparison.out_of_band) <= len(comparison.marginals) // 3

    def test_the_headline_names_the_basis(self):
        assert "signal" in compare_cohorts("COPD", 42, 42, n=50).headline()
        assert "tolerance" in compare_cohorts("COPD", 42, 43, n=50).headline()


class TestStudioEndpoints:
    def test_marginals_endpoint_reports_bands_and_headline(self):
        payload = client.post("/studio/marginals", json={
            "condition": "type 2 diabetes", "n": 300, "seed": 42}).json()
        assert payload["bands"]
        assert "tolerance the pack declares" in payload["headline"]
        assert payload["out_of_band"] == []
        assert payload["pack_version"] >= 1

    def test_diff_endpoint_refuses_per_persona_rows_across_seeds(self):
        payload = client.post("/studio/diff", json={
            "condition": "COPD", "n": 100, "left_seed": 42, "right_seed": 43}).json()
        assert payload["mode"] == "distributional"
        assert payload["persona_changes"] == []
        assert payload["marginals"]
        assert "sampling noise" in payload["note"]

    def test_diff_endpoint_allows_identity_rows(self):
        payload = client.post("/studio/diff", json={
            "condition": "COPD", "n": 100, "left_seed": 42, "right_seed": 42}).json()
        assert payload["mode"] == "identity"
