"""Protocol CI: scenario files, baselines, verdicts, gates.

The feature is packaging, not new simulation. So these tests concentrate on the
things packaging can get wrong: a hash that moves when it shouldn't, a baseline
that compares against the wrong population, and — the one that actually bit — a
gate that can never fail.
"""
import json
from pathlib import Path

import pytest

from spp.ci import (
    Gates,
    IncompatibleBaseline,
    ScenarioError,
    ScenarioFile,
    build_baseline,
    discover_scenarios,
    evaluate,
    load_scenario,
    read_baseline,
    render_markdown,
    write_baseline,
)
from spp.ci.cli import changed_scenarios, main
from spp.ci.scenario_file import ENGINE_VERSION
from spp.ci.verdict import SignStability, _gate

DOGFOOD = Path("protocols/t2d_standard_of_care.json")


def scenario_payload(**overrides) -> dict:
    payload = {
        "schema_version": 1, "name": "t", "condition": "COPD",
        "cohort_size": 60, "seed": 42, "duration_days": 365,
        "inclusion": ["age >= 50"], "exclusion": [],
        "burden": {"visits_per_year": 6},
    }
    payload.update(overrides)
    return payload


@pytest.fixture(scope="module")
def dogfood():
    return load_scenario(DOGFOOD)


class TestScenarioFileIsStrict:
    def test_an_unparseable_rule_is_fatal(self):
        """The editor scores the valid subset; a COMMITTED file must not. Gating
        on 'the rules that happened to parse' would gate on a design nobody
        wrote."""
        with pytest.raises(ValueError, match="unparseable inclusion rule"):
            ScenarioFile.model_validate(
                scenario_payload(inclusion=["age >= 50", "bmi_at_screening > 30"]))

    def test_exclusion_rules_are_strict_too(self):
        with pytest.raises(ValueError, match="unparseable exclusion rule"):
            ScenarioFile.model_validate(scenario_payload(exclusion=["nope_field > 1"]))

    def test_duplicate_visit_ids_are_rejected(self):
        with pytest.raises(ValueError, match="duplicate visit_ids"):
            ScenarioFile.model_validate(scenario_payload(visits=[
                {"visit_id": "v1", "day": 10}, {"visit_id": "v1", "day": 20}]))

    def test_future_schema_versions_are_rejected(self):
        with pytest.raises(ValueError, match="schema v9"):
            ScenarioFile.model_validate(scenario_payload(schema_version=9))

    def test_a_missing_file_is_a_scenario_error(self, tmp_path):
        with pytest.raises(ScenarioError, match="could not read"):
            load_scenario(tmp_path / "nope.json")

    def test_malformed_json_is_a_scenario_error(self, tmp_path):
        path = tmp_path / "bad.json"
        path.write_text("{not json")
        with pytest.raises(ScenarioError):
            load_scenario(path)


class TestScenarioHash:
    def test_key_order_does_not_change_the_hash(self):
        payload = scenario_payload()
        reordered = {k: payload[k] for k in reversed(list(payload))}
        assert (ScenarioFile.model_validate(payload).scenario_hash()
                == ScenarioFile.model_validate(reordered).scenario_hash())

    def test_whitespace_inside_dsl_text_does_not_change_the_hash(self):
        a = ScenarioFile.model_validate(scenario_payload(inclusion=["age >= 50"]))
        b = ScenarioFile.model_validate(scenario_payload(inclusion=["age   >=  50 "]))
        assert a.scenario_hash() == b.scenario_hash()

    def test_rule_order_does_not_change_the_hash(self):
        a = ScenarioFile.model_validate(
            scenario_payload(inclusion=["age >= 50", "n_medications >= 1"]))
        b = ScenarioFile.model_validate(
            scenario_payload(inclusion=["n_medications >= 1", "age >= 50"]))
        assert a.scenario_hash() == b.scenario_hash()

    def test_cosmetic_fields_do_not_change_the_hash(self):
        """Renaming a scenario must not invalidate its baseline."""
        a = ScenarioFile.model_validate(scenario_payload(name="one", description="x"))
        b = ScenarioFile.model_validate(scenario_payload(name="two", description="y"))
        assert a.scenario_hash() == b.scenario_hash()

    def test_a_real_design_change_does_change_the_hash(self):
        a = ScenarioFile.model_validate(scenario_payload())
        b = ScenarioFile.model_validate(
            scenario_payload(burden={"visits_per_year": 24}))
        assert a.scenario_hash() != b.scenario_hash()

    def test_round_trip(self, tmp_path, dogfood):
        from spp.ci import dump_scenario

        path = dump_scenario(dogfood, tmp_path / "s.json")
        assert load_scenario(path).scenario_hash() == dogfood.scenario_hash()


class TestBaseline:
    def test_it_is_deterministic(self, dogfood):
        a, b = build_baseline(dogfood), build_baseline(dogfood)
        assert a.outcomes == b.outcomes
        assert a.retention_rate == b.retention_rate
        assert a.scenario_hash == b.scenario_hash

    def test_it_stores_the_scenario_it_came_from(self, dogfood):
        """Without this the sign-stability control has nothing to compare
        against — see TestGateCanActuallyFail."""
        baseline = build_baseline(dogfood)
        assert baseline.scenario
        assert ScenarioFile.model_validate(baseline.scenario).scenario_hash() \
            == dogfood.scenario_hash()

    def test_outcomes_are_keyed_by_globally_unique_id(self, dogfood):
        baseline = build_baseline(dogfood)
        assert all("-s42-" in pid for pid in baseline.outcomes)

    @pytest.mark.parametrize("field,value", [
        ("cohort_size", 999), ("master_seed", 7), ("pack_version", 99),
        ("condition", "COPD"), ("duration_days", 180), ("engine_version", 99),
    ])
    def test_incompatible_config_is_refused(self, dogfood, field, value):
        """A baseline from a different population is not a baseline."""
        baseline = build_baseline(dogfood)
        candidate = baseline.config.model_copy(update={field: value})
        with pytest.raises(IncompatibleBaseline, match="same population"):
            baseline.require_compatible(candidate)

    def test_a_matching_config_passes(self, dogfood):
        baseline = build_baseline(dogfood)
        assert baseline.require_compatible(baseline.config) is baseline

    def test_a_stale_schema_version_is_refused(self, tmp_path, dogfood):
        path = tmp_path / "b.json"
        write_baseline(build_baseline(dogfood), path)
        payload = json.loads(path.read_text())
        payload["baseline_schema_version"] = 99
        path.write_text(json.dumps(payload))
        with pytest.raises(IncompatibleBaseline, match="schema v99"):
            read_baseline(path)


class TestGateCanActuallyFail:
    """The bug this class exists for: a fallback that compared the candidate
    against itself yielded zero flips at every seed, reported 'not sign-stable',
    and downgraded EVERY fail to warn. A gate that cannot fail is worse than no
    gate, because it looks like protection."""

    def test_a_real_regression_fails(self, dogfood):
        baseline = build_baseline(dogfood)
        harsher = dogfood.model_copy(update={
            "burden": dogfood.burden.model_copy(
                update={"visits_per_year": 24, "daily_diary": True})})

        verdict = evaluate(baseline, harsher, dogfood)
        assert verdict.outcome == "FAIL"
        assert verdict.exit_code == 1
        assert verdict.retention_delta_pp < -1.0
        assert verdict.lost and not verdict.recovered
        assert verdict.sign_stability.stable

    def test_the_sign_stability_control_is_the_baseline_not_the_candidate(self, dogfood):
        """Comparing a candidate against itself is always zero flips. If the
        control were the candidate, this would be [0, 0] and downgrade."""
        baseline = build_baseline(dogfood)
        harsher = dogfood.model_copy(update={
            "burden": dogfood.burden.model_copy(update={"visits_per_year": 24})})
        verdict = evaluate(baseline, harsher, dogfood)
        assert verdict.sign_stability.net_flips != [0, 0]

    def test_a_baseline_without_a_stored_scenario_errors(self, tmp_path, dogfood):
        from spp.ci.cli import _baseline_scenario

        baseline = build_baseline(dogfood)
        baseline.scenario = {}
        with pytest.raises(IncompatibleBaseline, match="downgrade to WARN"):
            _baseline_scenario(dogfood, baseline)


class TestGateBoundaries:
    GATES = Gates()

    def _stable(self):
        return SignStability(seeds=[42, 1234], net_flips=[-5, -4], stable=True)

    def _unstable(self):
        return SignStability(seeds=[42, 1234], net_flips=[-5, 3], stable=False)

    def test_exactly_at_fail_threshold_fails(self):
        outcome, _ = _gate(-1.0, self._stable(), self.GATES)
        assert outcome == "FAIL"

    def test_just_under_fail_threshold_warns(self):
        outcome, _ = _gate(-0.99, self._stable(), self.GATES)
        assert outcome == "WARN"

    def test_exactly_at_warn_threshold_warns(self):
        outcome, _ = _gate(-0.25, self._stable(), self.GATES)
        assert outcome == "WARN"

    def test_just_under_warn_threshold_passes(self):
        outcome, _ = _gate(-0.24, self._stable(), self.GATES)
        assert outcome == "PASS"

    def test_sign_instability_downgrades_fail_to_warn(self):
        """Never fail on a delta the paired design cannot distinguish."""
        outcome, reason = _gate(-5.0, self._unstable(), self.GATES)
        assert outcome == "WARN"
        assert "cannot distinguish it from noise" in reason

    def test_sign_instability_can_be_disabled(self):
        gates = Gates(require_sign_stability_for_fail=False)
        outcome, _ = _gate(-5.0, self._unstable(), gates)
        assert outcome == "FAIL"

    def test_improvement_passes(self):
        outcome, reason = _gate(+3.0, self._stable(), self.GATES)
        assert outcome == "PASS"
        assert "improved" in reason

    def test_gates_load_from_the_committed_file(self):
        gates = Gates.load("ci/gates.json")
        assert gates.retention_drop_pp["fail"] == 1.0
        assert gates.require_sign_stability_for_fail is True


class TestNoOpIsPass:
    def test_an_unchanged_scenario_passes_with_zero_flips(self, dogfood):
        baseline = build_baseline(dogfood)
        verdict = evaluate(baseline, dogfood, dogfood)
        assert verdict.outcome == "PASS"
        assert verdict.net_flips == 0
        assert verdict.recovered == [] and verdict.lost == []
        assert verdict.retention_delta_pp == 0.0


class TestVerdictRendering:
    def test_the_comment_leads_with_people_not_percentages(self, dogfood):
        baseline = build_baseline(dogfood)
        harsher = dogfood.model_copy(update={
            "burden": dogfood.burden.model_copy(update={"visits_per_year": 24})})
        markdown = render_markdown(evaluate(baseline, harsher, dogfood))

        # Within the HEADLINE line specifically: paired runs make "15 personas
        # lost" exact, while a percentage invites reading as a difference of
        # aggregates. ("retention" also appears in the reason line above.)
        headline = next(l for l in markdown.splitlines() if "personas lost" in l)
        assert headline.index("personas lost") < headline.index("retention")
        assert "exact per-persona flips" in markdown
        assert "not a difference of two aggregates" in markdown

    def test_it_carries_every_stamp(self, dogfood):
        markdown = render_markdown(evaluate(build_baseline(dogfood), dogfood, dogfood))
        for stamp in ("scenario", "population", "ledger", "gates", "generated"):
            assert stamp in markdown
        assert f"engine=v{ENGINE_VERSION}" in markdown

    def test_it_carries_the_sticky_comment_marker(self, dogfood):
        from spp.ci import COMMENT_MARKER

        markdown = render_markdown(evaluate(build_baseline(dogfood), dogfood, dogfood))
        assert markdown.startswith(COMMENT_MARKER)

    def test_thresholds_are_named_as_pre_registered(self, dogfood):
        markdown = render_markdown(evaluate(build_baseline(dogfood), dogfood, dogfood))
        assert "pre-registered" in markdown


class TestPathFilter:
    def test_it_selects_scenarios_and_ignores_baselines(self):
        assert changed_scenarios([
            "protocols/a.json", "protocols/a.baseline.json",
            "protocols/b.yaml", "src/spp/ci/cli.py", "README.md",
        ]) == ["protocols/a.json", "protocols/b.yaml"]

    def test_it_respects_the_root(self):
        assert changed_scenarios(["designs/a.json"], root="designs") == ["designs/a.json"]
        assert changed_scenarios(["designs/a.json"], root="protocols") == []

    def test_discovery_agrees_with_the_path_filter(self, tmp_path):
        """Both answer "is this a scenario?" and must not disagree.

        They did: `changed_scenarios` excluded baselines, `discover_scenarios`
        did not, so `spp ci list` reported a correctly committed baseline as
        INVALID — a listing that cries wolf about its own convention.
        """
        (tmp_path / "a.json").write_text("{}")
        (tmp_path / "a.baseline.json").write_text("{}")
        (tmp_path / "b.yaml").write_text("{}")

        discovered = [p.name for p in discover_scenarios(tmp_path)]

        assert discovered == ["a.json", "b.yaml"]
        assert discovered == [
            Path(p).name
            for p in changed_scenarios(
                [f"{tmp_path.name}/{n}" for n in ("a.json", "a.baseline.json", "b.yaml")],
                root=tmp_path.name,
            )
        ]


class TestCliExitCodes:
    def test_check_on_the_dogfood_pair_passes(self, tmp_path):
        assert main(["check", str(DOGFOOD), "--out", str(tmp_path)]) == 0
        assert json.loads((tmp_path / "verdict.json").read_text())["outcome"] == "PASS"

    def test_a_regression_exits_one(self, tmp_path, dogfood):
        payload = json.loads(DOGFOOD.read_text())
        payload["burden"]["visits_per_year"] = 24
        payload["burden"]["daily_diary"] = True
        candidate = tmp_path / "candidate.json"
        candidate.write_text(json.dumps(payload))

        write_baseline(build_baseline(dogfood), tmp_path / "candidate.baseline.json")
        assert main(["check", str(candidate), "--out", str(tmp_path / "out")]) == 1

    def test_an_invalid_scenario_exits_one_without_a_traceback(self, tmp_path, capsys):
        bad = tmp_path / "bad.json"
        bad.write_text(json.dumps(scenario_payload(inclusion=["nope_field > 1"])))
        assert main(["check", str(bad), "--out", str(tmp_path)]) == 1
        assert "::error" in capsys.readouterr().out

    def test_baseline_check_detects_staleness(self, tmp_path, dogfood):
        from spp.ci import dump_scenario

        path = dump_scenario(dogfood, tmp_path / "s.json")
        assert main(["baseline", str(path)]) == 0
        assert main(["baseline", str(path), "--check"]) == 0


class TestPureCore:
    def test_the_ci_path_never_calls_the_llm(self, dogfood, monkeypatch):
        """The TestNoLLMInTheCore pattern, applied to the CI path. Enforced by a
        test rather than asserted in a comment."""
        import spp.foundation.llm as llm

        def explode(*args, **kwargs):
            raise AssertionError("Protocol CI called the LLM adapter")

        monkeypatch.setattr(llm, "generate", explode)
        monkeypatch.setattr(llm, "get_backend", explode)
        monkeypatch.setattr(llm, "generate_structured", explode)

        baseline = build_baseline(dogfood)
        verdict = evaluate(baseline, dogfood, dogfood)
        assert verdict.outcome == "PASS"
        render_markdown(verdict)
