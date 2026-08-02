"""Foundation layer: the four guarantees everything else is built on."""
import pytest

from spp.foundation import (
    Assumption,
    AssumptionLedger,
    BurdenVector,
    Confidence,
    EventLog,
    EventType,
    JourneyStage,
    MigrationError,
    SeedScope,
    cohort_scope,
    derive_seed,
    fold,
    generate,
    generate_structured,
    get_backend,
    persona_scope,
)
from spp.foundation.llm import NullBackend
from spp.foundation.versioning import migrate, migration, register_schema


class TestSeedHierarchy:
    def test_derivation_is_deterministic(self):
        assert derive_seed(42, "cohort:COPD") == derive_seed(42, "cohort:COPD")

    def test_different_names_and_parents_diverge(self):
        assert derive_seed(42, "a") != derive_seed(42, "b")
        assert derive_seed(42, "a") != derive_seed(43, "a")

    def test_derivation_is_stable_across_processes(self):
        """Regression guard: hash() is randomised per process for str, which
        would silently break reproducibility between runs. BLAKE2b is not."""
        import subprocess
        import sys

        code = (
            "import sys; sys.path.insert(0, 'src'); "
            "from spp.foundation.rng import derive_seed; print(derive_seed(42, 'x'))"
        )
        runs = {
            subprocess.run(
                [sys.executable, "-c", code],
                capture_output=True, text=True, env={"PYTHONHASHSEED": seed},
            ).stdout.strip()
            for seed in ("0", "1", "random")
        }
        assert len(runs) == 1, f"seed derivation varied across processes: {runs}"
        assert runs.pop() == str(derive_seed(42, "x"))

    def test_seeds_fit_in_64_unsigned_bits(self):
        for name in ("a", "persona:000001", "event:visit-3" * 20):
            assert 0 <= derive_seed(2**63, name) < 2**64

    def test_child_scopes_are_isolated_from_sibling_draws(self):
        """The property that makes counterfactual forking honest: re-simulating
        one persona alone must give the same numbers as in a full run."""
        cohort = cohort_scope(42, "COPD")

        in_context = []
        for i in range(5):
            gen = persona_scope(cohort, i).generator()
            gen.random()  # sibling work that would shift a shared generator
            in_context.append(gen.random())

        isolated = []
        for i in range(5):
            gen = persona_scope(cohort, i).generator()
            gen.random()
            isolated.append(gen.random())

        assert in_context == isolated

    def test_generator_replays_from_the_same_state(self):
        scope = SeedScope.root(7).child("x")
        assert scope.generator().random() == scope.generator().random()

    def test_path_records_the_lineage(self):
        scope = SeedScope.root(42).child("cohort:COPD").child("persona:000003")
        assert scope.path == "master/cohort:COPD/persona:000003"
        assert scope.describe() == {"path": scope.path, "seed": scope.seed}

    def test_scopes_are_immutable(self):
        scope = SeedScope.root(1)
        with pytest.raises(Exception):
            scope.seed = 2


class TestEventSourcing:
    def _log(self) -> EventLog:
        log = EventLog(persona_id="p1")
        log.append(EventType.SCREENED, t=0, payload={"eligible": True})
        log.append(EventType.ENROLLED, t=1)
        log.append(EventType.VISIT_COMPLETED, t=30)
        log.append(EventType.BURDEN_ACCRUED, t=30, payload={"burden": {"travel": 0.4}})
        log.append(EventType.VISIT_MISSED, t=60)
        return log

    def test_fold_is_deterministic(self):
        log = self._log()
        assert fold(log) == fold(log)

    def test_fold_derives_state(self):
        state = fold(self._log())
        assert state.stage == JourneyStage.ACTIVE
        assert state.visits_completed == 1
        assert state.visits_missed == 1
        assert state.burden.travel == 0.4
        assert state.attendance_rate == 0.5
        assert state.active is True

    def test_time_travel(self):
        log = self._log()
        assert fold(log, until=0).stage == JourneyStage.SCREENED
        assert fold(log, until=30).visits_missed == 0
        assert fold(log, until=30).visits_completed == 1

    def test_terminal_stages_absorb(self):
        """A dropped persona cannot go on completing visits."""
        log = self._log()
        log.append(EventType.DROPPED_OUT, t=70, payload={"reason": "travel burden"})
        log.append(EventType.VISIT_COMPLETED, t=90)

        state = fold(log)
        assert state.stage == JourneyStage.DROPPED
        assert state.exit_reason == "travel burden"
        assert state.visits_completed == 1  # not 2
        assert state.terminal is True

    def test_fork_branches_at_a_point_in_time(self):
        log = self._log()
        forked = log.fork_at(30)

        assert len(forked) == 4
        assert fold(forked).visits_missed == 0
        assert len(log) == 5, "forking must not mutate the original"

    def test_events_are_immutable(self):
        event = self._log().events[0]
        with pytest.raises(Exception):
            event.t = 99

    def test_log_rejects_time_going_backwards(self):
        log = self._log()
        with pytest.raises(ValueError, match="cannot append"):
            log.append(EventType.VISIT_COMPLETED, t=1)

    def test_log_rejects_a_foreign_event(self):
        from spp.foundation.events import PersonaEvent

        with pytest.raises(ValueError, match="belongs to"):
            EventLog(
                persona_id="p1",
                events=[PersonaEvent(seq=0, persona_id="p2", type=EventType.ENROLLED, t=0)],
            )

    def test_barriers_are_deduplicated(self):
        log = EventLog(persona_id="p1")
        for _ in range(3):
            log.append(EventType.BARRIER_TRIGGERED, t=1, payload={"barrier": "transport"})
        assert fold(log).barriers == ["transport"]

    def test_screen_failure_is_terminal(self):
        log = EventLog(persona_id="p1")
        log.append(EventType.SCREEN_FAILED, t=0, payload={"reason": "age < 50"})
        state = fold(log)
        assert state.stage == JourneyStage.DROPPED
        assert state.eligible is False


class TestBurdenVector:
    def test_total_sums_components(self):
        vector = BurdenVector(time=0.1, travel=0.2, cognitive=0.3)
        assert vector.total == pytest.approx(0.6)

    def test_addition_is_componentwise(self):
        combined = BurdenVector(travel=0.2).plus(BurdenVector(travel=0.1, time=0.5))
        assert combined.travel == pytest.approx(0.3)
        assert combined.time == pytest.approx(0.5)

    def test_dominant_names_the_headline_component(self):
        assert BurdenVector(travel=0.5, time=0.1).dominant() == "travel"
        assert BurdenVector().dominant() is None


class TestAssumptionLedger:
    def _assumption(self, **overrides) -> Assumption:
        return Assumption(**{"name": "test.thing", "params": {"a": 1.0}, **overrides})

    def test_registration_is_idempotent(self):
        ledger = AssumptionLedger()
        first = ledger.register(self._assumption())
        assert ledger.register(self._assumption()) is first
        assert len(ledger) == 1

    def test_conflicting_redefinition_is_rejected(self):
        """Two modules disagreeing about a coefficient is the bug this prevents."""
        ledger = AssumptionLedger()
        ledger.register(self._assumption())
        with pytest.raises(ValueError, match="already registered"):
            ledger.register(self._assumption(params={"a": 2.0}))

    def test_unknown_lookup_lists_what_exists(self):
        ledger = AssumptionLedger()
        ledger.register(self._assumption())
        with pytest.raises(KeyError, match="test.thing"):
            ledger.get("nope")

    def test_confidence_gates_quotability(self):
        guess = self._assumption(confidence=Confidence.EXPERT_GUESS)
        measured = self._assumption(name="m", confidence=Confidence.MEASURED)
        assert guess.quotable is False
        assert measured.quotable is True

    def test_unsupported_lists_the_non_quotable(self):
        ledger = AssumptionLedger()
        ledger.register(self._assumption(confidence=Confidence.EXPERT_GUESS))
        ledger.register(self._assumption(name="b", confidence=Confidence.MEASURED))
        assert [a.name for a in ledger.unsupported()] == ["test.thing"]

    def test_perturbation_scales_numbers_only(self):
        ledger = AssumptionLedger()
        ledger.register(self._assumption(params={"a": 2.0, "label": "x", "flag": True}))
        perturbed = ledger.perturbed("test.thing", 1.5)
        assert perturbed == {"a": 3.0, "label": "x", "flag": True}

    def test_snapshot_is_serialisable(self):
        import json

        ledger = AssumptionLedger()
        ledger.register(self._assumption())
        assert json.loads(json.dumps(ledger.snapshot()))["count"] == 1


class TestRealLedger:
    """The shipped assumptions, not a fixture."""

    def test_every_heuristic_is_registered(self):
        from spp.foundation import LEDGER

        import spp.assumptions  # noqa: F401 - registers on import

        names = {a.name for a in LEDGER}
        assert {
            "adherence.literacy_effect",
            "adherence.access_effect",
            "burden.factor_weights",
            "burden.trigger_thresholds",
            "cohort.condition_priors",
        } <= names

    def test_the_caveats_are_machine_readable(self):
        """The epidemiology priors must be flagged as non-quotable, so a report
        can't present them as findings without the caveat travelling with them."""
        from spp.foundation import LEDGER

        import spp.assumptions  # noqa: F401

        unsupported = {a.name for a in LEDGER.unsupported()}
        assert "cohort.condition_priors" in unsupported
        assert "burden.factor_weights" in unsupported

    def test_burden_code_reads_its_weights_from_the_ledger(self):
        """No magic numbers: changing the ledger must change the outcome."""
        from spp.assumptions import BURDEN_FACTORS
        from spp.protocol import burden_profile
        from spp.schemas import PatientDNA

        dna = PatientDNA(
            patient_id="x", age=70, sex="female", condition="COPD",
            adherence_baseline=0.2, health_literacy="low",
        )
        before = burden_profile(dna).score
        original = BURDEN_FACTORS.params["low_adherence"]
        try:
            BURDEN_FACTORS.params["low_adherence"] = original * 2
            assert burden_profile(dna).score > before
        finally:
            BURDEN_FACTORS.params["low_adherence"] = original


class TestSchemaVersioning:
    def test_migration_chain_runs_in_order(self):
        register_schema("Widget", 3)

        @migration("Widget", 1, 2)
        def _v1_to_v2(payload):
            payload["b"] = payload.pop("a")
            return payload

        @migration("Widget", 2, 3)
        def _v2_to_v3(payload):
            payload["c"] = payload["b"] * 2
            return payload

        out = migrate({"schema_version": 1, "a": 5}, "Widget")
        assert out == {"schema_version": 3, "b": 5, "c": 10}

    def test_missing_step_is_an_error_not_a_silent_default(self):
        register_schema("Gappy", 2)
        with pytest.raises(MigrationError, match="no migration registered"):
            migrate({"schema_version": 1}, "Gappy")

    def test_future_payloads_are_rejected(self):
        register_schema("Future", 1)
        with pytest.raises(MigrationError, match="newer than"):
            migrate({"schema_version": 9}, "Future")

    def test_current_version_payload_passes_through(self):
        register_schema("Stable", 1)
        assert migrate({"schema_version": 1, "x": 1}, "Stable") == {"schema_version": 1, "x": 1}


class TestLLMAdapter:
    def test_offline_forces_the_null_backend(self, monkeypatch):
        """The switch that makes 'offline-first' checkable rather than aspirational."""
        from spp.foundation import llm

        monkeypatch.setattr(llm.settings, "spp_live", False)
        monkeypatch.setattr(llm.settings, "llm_backend", "anthropic")
        assert isinstance(get_backend(), NullBackend)

    def test_null_backend_labels_its_output_as_synthetic(self):
        result = generate("system", "prompt")
        assert result.synthetic is True
        assert result.backend == "null"
        assert result.text

    def test_unknown_backend_is_rejected(self, monkeypatch):
        from spp.foundation import llm

        monkeypatch.setattr(llm.settings, "spp_live", True)
        with pytest.raises(ValueError, match="unknown LLM backend"):
            get_backend("telepathy")

    def test_cloud_backend_without_a_key_degrades_rather_than_erroring(self, monkeypatch):
        from spp.foundation import llm

        monkeypatch.setattr(llm.settings, "spp_live", True)
        monkeypatch.setattr(llm.settings, "anthropic_api_key", "")
        assert isinstance(get_backend("anthropic"), NullBackend)

    def test_structured_generation_returns_none_offline(self):
        assert generate_structured("sys", "prompt", {"type": "object"}) is None

    def test_default_backend_is_local(self):
        """Offline-first: the configured default must not be a cloud service."""
        from spp.config import Settings

        assert Settings().llm_backend in {"null", "ollama"}
