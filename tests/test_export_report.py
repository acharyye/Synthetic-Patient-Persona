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


class TestTheBundlePageKeepsTheReadingOrder:
    """The order is the constraint, not the styling.

    A bundle's protocol is canary → takes → quarantine → aggregates →
    adjudication, and it exists because a reader who meets the verdict first reads
    everything above it looking for confirmation. A summary page that opened with
    the headline would be a nicer document and a worse artifact, so the order is
    asserted rather than trusted to whoever edits the template next.
    """

    def page(self):
        from spp.report import render_bundle

        return render_bundle({
            "manifest": {"release": "v0.5", "canary_sensitive": True,
                         "accepted_takes": 30, "battery_cases": 30,
                         "quarantined_takes": 0},
            "compliance": {"report": {}, "verdict": {"bars": []}},
            "adjudication": {"verdict": "THE LEVER ACTED AND THE FLOOR WAS MISSED",
                             "arms": [{"metric": "state_coverage", "bound": "floor 0.6",
                                       "observed": 0.556, "passed": False}]},
        })

    def test_sections_appear_in_the_protocol_order(self):
        page = self.page()
        positions = [page.find(marker) for marker in
                     ("1 · Canary", "2 · Raw takes", "3 · Quarantine",
                      "4 · Aggregates", "5 · Adjudication")]

        assert all(p >= 0 for p in positions), "a protocol section is missing"
        assert positions == sorted(positions)

    def test_the_verdict_does_not_appear_before_the_canary(self):
        page = self.page()
        head = page[:page.find("1 · Canary")]

        assert "FLOOR WAS MISSED" not in head

    def test_an_unadjudicated_bundle_says_so_rather_than_omitting(self):
        """Missing and absent are different, and a reader cannot tell them apart."""
        from spp.report import render_bundle

        page = render_bundle({"manifest": {"release": "v0.1"}})

        assert "not adjudicated" in page


class TestTheVerdictPageShowsTheDowngrade:
    def test_sign_stability_is_rendered_next_to_the_outcome(self):
        """A FAIL downgraded to WARN for want of sign stability is the gate
        refusing to assert what its method cannot distinguish. A page showing only
        the final word hides the most defensible thing about it."""
        from spp.report import render_verdict

        page = render_verdict({
            "outcome": "warn", "scenario_name": "s", "reason": "r",
            "sign_stability": {"seeds": [42, 7], "net_flips": [3, -1], "stable": False},
        })

        assert "not stable" in page
        assert "downgrades it to WARN" in page
        assert ">42<" in page and ">7<" in page
