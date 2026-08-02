"""Scenario Lab server side: lenient parsing, cohort residency, fast preview.

The SPA is thin by design, so these are the tests that matter — every number the
Lab shows is computed here.
"""
import json
import time
from datetime import date
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from spp.api.main import app
from spp.cohort.residency import CohortResidency
from spp.protocol.lenient import parse_lenient

client = TestClient(app)
AS_OF = date(2026, 8, 1)
FIXTURES = Path(__file__).parent / "fixtures"


class TestLenientParsing:
    def test_a_half_typed_rule_is_editor_state_not_failure(self):
        parse = parse_lenient(["age >= 50", "biomarkers.HbA1c_pct >"])
        assert not parse.ok
        assert parse.valid_inclusion == ["age >= 50"]
        assert parse.has_usable_subset

    def test_errors_carry_a_location_for_the_squiggle(self):
        parse = parse_lenient(["bmi_at_screening > 30"])
        error = parse.errors[0]
        assert error.column is not None
        assert 0 <= error.column < len(error.text)
        assert "unknown field" in error.message

    def test_blank_lines_are_not_errors(self):
        parse = parse_lenient(["age >= 50", "", "   "])
        assert parse.ok
        assert parse.valid_inclusion == ["age >= 50"]

    def test_inclusion_and_exclusion_are_kept_apart(self):
        parse = parse_lenient(["age >= 50"], ["CKD", "nonsense_field > 1"])
        assert parse.valid_inclusion == ["age >= 50"]
        assert parse.valid_exclusion == ["CKD"]
        assert parse.errors[0].kind == "exclusion"

    def test_the_stale_message_reads_like_a_person_wrote_it(self):
        one = parse_lenient(["age >= 50", "bad_field > 1"]).stale_reason()
        assert one.startswith("1 rule has errors")

        two = parse_lenient(["bad_one > 1", "bad_two > 2"]).stale_reason()
        assert two.startswith("2 rules have errors")

    def test_everything_valid_means_no_stale_marker(self):
        assert parse_lenient(["age >= 50"], ["CKD"]).stale_reason() == ""

    def test_strictness_is_unchanged_where_it_matters(self):
        """screen() must still refuse anything it cannot parse."""
        from spp.cohort import generate_cohort
        from spp.protocol import CriterionError, screen

        cohort = generate_cohort("COPD", 5, seed=42, as_of=AS_OF)
        with pytest.raises(CriterionError):
            screen(cohort, ["bmi_at_screening > 30"])


class TestCohortResidency:
    def test_the_key_is_the_identity_not_merely_a_lookup(self):
        """Determinism means a rebuild is provably identical, so eviction is safe."""
        residency = CohortResidency(capacity=2)
        first, key, cached = residency.get("COPD", 42, 20, AS_OF)
        assert cached is False

        residency.clear()
        rebuilt, rebuilt_key, _ = residency.get("COPD", 42, 20, AS_OF)
        assert rebuilt_key == key
        assert [p.model_dump() for p in rebuilt] == [p.model_dump() for p in first]

    def test_a_hit_avoids_regeneration(self):
        residency = CohortResidency()
        residency.get("COPD", 42, 20, AS_OF)
        _, _, cached = residency.get("COPD", 42, 20, AS_OF)
        assert cached is True
        assert residency.hits == 1

    def test_different_seeds_sizes_and_conditions_are_different_cohorts(self):
        residency = CohortResidency()
        base = residency.key_for("COPD", 42, 20, AS_OF)
        assert residency.key_for("COPD", 43, 20, AS_OF) != base
        assert residency.key_for("COPD", 42, 21, AS_OF) != base
        assert residency.key_for("type 2 diabetes", 42, 20, AS_OF) != base

    def test_the_pack_version_is_part_of_the_identity(self):
        """Without it, an edited pack would keep serving the old population."""
        residency = CohortResidency()
        key = residency.key_for("COPD", 42, 20, AS_OF)
        assert key.pack_version >= 1
        assert "@v" in key.describe()

    def test_eviction_is_bounded_and_lru(self):
        residency = CohortResidency(capacity=2)
        for seed in (1, 2, 3):
            residency.get("COPD", seed, 10, AS_OF)
        assert residency.stats()["resident"] == 2


class TestPreviewEndpoint:
    def test_sequence_is_echoed_so_stale_responses_can_be_discarded(self):
        """Type-ahead means concurrent requests; a late response overwriting a
        fresh one shows wrong attrition next to the rule on screen."""
        body = {"condition": "COPD", "n": 50, "seed": 42,
                "inclusion": ["age >= 50"], "sequence": 7}
        assert client.post("/scenario/preview", json=body).json()["sequence"] == 7

    def test_invalid_rules_do_not_blank_the_preview(self):
        body = {"condition": "type 2 diabetes", "n": 100, "seed": 42,
                "inclusion": ["age >= 50", "bmi_at_screening > 30"], "sequence": 1}
        payload = client.post("/scenario/preview", json=body).json()

        assert payload["stale"] is True
        assert payload["stale_reason"]
        assert payload["eligible"] > 0, "must keep showing last-valid results"
        assert any(not d["ok"] for d in payload["diagnostics"])

    def test_a_clean_ruleset_is_not_marked_stale(self):
        body = {"condition": "COPD", "n": 100, "seed": 42,
                "inclusion": ["age >= 50"], "sequence": 1}
        payload = client.post("/scenario/preview", json=body).json()
        assert payload["stale"] is False
        assert payload["stale_reason"] == ""

    def test_the_warm_path_is_fast_enough_for_keystrokes(self):
        body = {"condition": "type 2 diabetes", "n": 400, "seed": 99,
                "inclusion": ["age >= 50"], "sequence": 1}
        client.post("/scenario/preview", json=body)  # warm the residency

        start = time.perf_counter()
        payload = client.post("/scenario/preview", json={**body, "sequence": 2}).json()
        elapsed = time.perf_counter() - start

        assert payload["cohort"]["cached"] is True
        assert elapsed < 0.5, f"warm preview took {elapsed * 1000:.0f}ms"

    def test_preview_carries_exact_shapley_attribution(self):
        body = {"condition": "type 2 diabetes", "n": 200, "seed": 42,
                "inclusion": ["age >= 50"], "exclusion": ["CKD"], "sequence": 1}
        payload = client.post("/scenario/preview", json=body).json()

        shares = [rule["shapley_share"] for rule in payload["attribution"]]
        assert sum(shares) == pytest.approx(1.0, abs=1e-3)

    def test_residency_endpoint_reports_identities(self):
        client.post("/scenario/preview", json={
            "condition": "COPD", "n": 30, "seed": 5, "sequence": 1})
        stats = client.get("/scenario/residency").json()
        assert stats["resident"] >= 1
        assert any("@v" in key for key in stats["keys"])


class TestSharedFixtures:
    """Committed artifacts both renderers read. Regenerate with
    `PYTHONPATH=src python scripts/export_schema.py`."""

    @pytest.mark.parametrize("name", [
        "counterfactual_run", "scenario_preview",
        "scenario_preview_with_errors", "panel", "interview",
    ])
    def test_fixture_exists_and_parses(self, name):
        path = FIXTURES / f"{name}.json"
        assert path.exists(), f"missing fixture {name}; run scripts/export_schema.py"
        assert isinstance(json.loads(path.read_text()), dict)

    def test_the_counterfactual_fixture_still_matches_the_api(self):
        """Drift guard: if the artifact shape changes, the fixture the SPA tests
        assert against must be regenerated, or the two renderers diverge."""
        fixture = json.loads((FIXTURES / "counterfactual_run.json").read_text())
        live = client.post("/counterfactual/run", json={
            "condition": "type 2 diabetes", "n": 120, "seed": 42,
            "inclusion": ["age >= 50"], "burden": {"visits_per_year": 12},
            "remote_visits": ["v001", "v003", "v005"],
        }).json()

        assert set(fixture) == set(live), "artifact keys drifted from the fixture"
        assert fixture["net_flips"] == live["net_flips"]
        assert fixture["recovered"] == live["recovered"]

    def test_the_error_fixture_actually_contains_errors(self):
        payload = json.loads((FIXTURES / "scenario_preview_with_errors.json").read_text())
        assert payload["stale"] is True
        assert payload["eligible"] > 0


class TestGeneratedTypes:
    def test_schema_and_types_are_committed(self):
        root = Path(__file__).parent.parent
        assert (root / "ui/src/types/artifacts.schema.json").exists()
        types = root / "ui/src/types/artifacts.ts"
        assert types.exists(), "run scripts/export_schema.py"
        assert "do not edit by hand" in types.read_text().lower()

    def test_schema_has_no_dangling_refs(self):
        """A dangling $ref breaks codegen — and nested models are easy to miss."""
        root = Path(__file__).parent.parent
        schema = json.loads((root / "ui/src/types/artifacts.schema.json").read_text())
        definitions = set(schema["definitions"])

        blob = json.dumps(schema)
        import re
        for ref in set(re.findall(r'"#/definitions/([A-Za-z0-9_]+)"', blob)):
            assert ref in definitions, f"dangling $ref to {ref}"
