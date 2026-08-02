"""The HTML report: pure reads, and provenance rendered as first-class furniture."""
import re

from fastapi.testclient import TestClient

from spp.api.main import app
from spp.report import render_counterfactual

client = TestClient(app)

REQUEST = {
    "condition": "type 2 diabetes", "n": 120, "seed": 42,
    "inclusion": ["age >= 50"], "burden": {"visits_per_year": 12},
    "remote_visits": ["v001", "v003", "v005"],
}


def artifact() -> dict:
    return client.post("/counterfactual/run", json=REQUEST).json()


class TestReportIsAPureRead:
    def test_every_headline_number_matches_the_artifact(self):
        """Nothing may be recomputed for display — that is how a report starts
        disagreeing with the API it claims to render."""
        data = artifact()
        page = render_counterfactual(data)

        assert f"{data['net_flips']:+d} net personas" in page
        assert f"+{data['recovered']} recovered" in page
        assert str(data["provenance"]["master_seed"]) in page
        assert str(data["provenance"]["cohort_size"]) in page

    def test_rendering_is_deterministic(self):
        """Same artifact in, identical bytes out — the timestamp lives in the
        artifact, so rendering itself has no clock."""
        data = artifact()
        assert render_counterfactual(data) == render_counterfactual(data)

    def test_it_survives_an_artifact_with_no_flips(self):
        data = artifact()
        data.update(net_flips=0, recovered=0, lost=0,
                    example_recovered=[], example_lost=[])
        assert "no outcome changed" in render_counterfactual(data)

    def test_missing_optional_sections_do_not_break_it(self):
        data = artifact()
        data["sign_stability"] = None
        data["eligibility_attribution"] = None
        assert render_counterfactual(data).startswith("<!doctype html>")


class TestProvenanceIsTheAesthetic:
    def test_seeds_and_versions_are_rendered_not_buried(self):
        page = render_counterfactual(artifact())
        assert "seed" in page and "artifact" in page
        assert "generated" in page

    def test_the_ledger_is_rendered_in_full(self):
        from spp.foundation import LEDGER

        page = render_counterfactual(artifact())
        for assumption in LEDGER:
            assert assumption.name in page, assumption.name

    def test_unquotable_assumptions_are_visibly_marked(self):
        """A reader who never goes looking must still see how much is judgement."""
        page = render_counterfactual(artifact())
        assert "never quote" in page
        assert re.search(r"\d+ not quotable", page)

    def test_the_paired_design_is_explained_next_to_the_number(self):
        page = render_counterfactual(artifact())
        assert "exact flips" in page
        assert "common random numbers" in page

    def test_sign_stability_verdict_is_shown(self):
        page = render_counterfactual(artifact())
        assert "Sign stability" in page

    def test_the_disclaimer_travels_with_the_artifact(self):
        page = render_counterfactual(artifact())
        assert "not a forecast" in page.lower()


class TestSelfContained:
    def test_no_external_assets_or_scripts(self):
        """It must render from file:// in a meeting where the wifi has failed."""
        page = render_counterfactual(artifact())
        assert "<script" not in page.lower()
        assert "http://" not in page.replace("http://localhost", "")
        assert "cdn" not in page.lower()

    def test_persona_ids_render_unambiguously(self):
        """Globally unique ids mean a flip table names exactly one persona."""
        data = artifact()
        page = render_counterfactual(data)
        for flip in data.get("example_recovered", [])[:3]:
            assert flip["patient_id"] in page
            assert "-s42-" in flip["patient_id"]


class TestEndpoint:
    def test_report_endpoint_returns_html(self):
        response = client.post("/counterfactual/report", json=REQUEST)
        assert response.status_code == 200
        assert response.text.startswith("<!doctype html>")
        assert "text/html" in response.headers["content-type"]

    def test_endpoint_and_renderer_agree(self):
        """Compared with the wall-clock stamp normalised out: two independent
        runs are generated at different seconds, and that difference is correct."""
        stamp = re.compile(r"generated <b>[^<]*</b>")
        endpoint = stamp.sub("generated <b>X</b>",
                             client.post("/counterfactual/report", json=REQUEST).text)
        direct = stamp.sub("generated <b>X</b>", render_counterfactual(artifact()))
        assert endpoint == direct
