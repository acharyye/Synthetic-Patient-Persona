"""The artifact that leaves the room without its author.

Two properties matter more than anything visual here.

**Self-contained.** A page that reaches for the network is a page that breaks in
the meeting it was written for. No script tags, no external sources, no http(s)
anywhere — asserted, because "we didn't add any" is not a guarantee.

**The identity/distributional invariant is enforced at the renderer.** Within a
run, common random numbers make persona `i` on both sides the same persona, so a
per-persona delta is signal. Across seeds it is a delta between exchangeable
strangers. `tests/test_studio.py` already pins that upstream; this pins it again
at the last point before the artifact travels, because nobody will be present to
explain the distinction to whoever opens the file.
"""
import subprocess
import sys
from pathlib import Path

from spp.report import render_comparison, render_counterfactual
from spp.report.compare import compare_cohorts

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "export_report.py"


def _payload(comparison):
    payload = comparison.model_dump(mode="json")
    payload["headline"] = comparison.headline()
    return payload


class TestSelfContained:
    def test_a_comparison_page_reaches_for_nothing(self):
        page = render_comparison(_payload(
            compare_cohorts("COPD", left_seed=42, right_seed=7, n=60)
        ))

        for forbidden in ("<script", "http://", "https://", "src="):
            assert forbidden not in page

    def test_a_counterfactual_page_reaches_for_nothing(self):
        page = render_counterfactual({
            "title": "t", "provenance": {"master_seed": 42},
            "disclaimer": "d", "net_flips": 0,
        })

        for forbidden in ("<script", "http://", "https://", "src="):
            assert forbidden not in page


class TestTheInvariantSurvivesRendering:
    def test_a_distributional_comparison_emits_no_persona_rows(self):
        """Handed persona rows anyway, the renderer must still refuse them.

        This is the second enforcement point on purpose. The first is in
        `compare_cohorts`, which does not populate them; this one covers a caller
        that builds the payload by hand — which the export CLI's author could
        easily become.
        """
        page = render_comparison({
            "left": "seed 42", "right": "seed 7", "mode": "distributional",
            "n": 100, "headline": "h", "marginals": [],
            "persona_changes": [{"patient_id": "SMUGGLED-0001",
                                 "field": "age", "left": 1, "right": 2}],
        })

        assert "SMUGGLED-0001" not in page
        assert "deliberately absent" in page

    def test_an_identity_comparison_does_show_them(self):
        page = render_comparison({
            "left": "baseline", "right": "variant", "mode": "identity",
            "n": 2, "headline": "h", "marginals": [],
            "persona_changes": [{"patient_id": "copd-s42-0001",
                                 "field": "age", "left": 61, "right": 62}],
        })

        assert "copd-s42-0001" in page
        assert "deltas are signal" in page


class TestTheReadingProtocolTravels:
    def test_both_pages_carry_it(self):
        """A bundle carries its reading protocol; so must a page that travels
        further than a bundle does."""
        comparison = render_comparison(_payload(
            compare_cohorts("COPD", left_seed=42, right_seed=7, n=60)
        ))
        counterfactual = render_counterfactual({
            "title": "t", "provenance": {}, "disclaimer": "d", "net_flips": 0,
        })

        for page in (comparison, counterfactual):
            assert "Read in this order" in page
            assert "Assumption ledger" in page


class TestTheCLIWritesAFile:
    def test_comparison_export(self, tmp_path):
        out = tmp_path / "drift.html"
        result = subprocess.run(
            [sys.executable, "-B", str(SCRIPT), "comparison", "--condition", "COPD",
             "--n", "60", "--left-seed", "42", "--right-seed", "7", "--out", str(out)],
            capture_output=True, text=True,
            env={"PYTHONPATH": "src", "PATH": "/usr/bin:/bin"},
        )

        assert result.returncode == 0, result.stderr
        assert out.exists()
        assert "self-contained" in result.stdout
        assert out.read_text().startswith("<!doctype html>")
