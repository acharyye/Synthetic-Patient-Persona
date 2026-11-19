"""A cohort sampled from invented priors must say so, as a field.

**Why this file exists.** `pack_for()` returns `None` for a condition with no
prior pack, `epidemiology.for_condition()` silently substitutes `GENERIC_EPI`,
and the endpoint returned **200** with a plausible number. `{"condition":
"glaucoma"}` measured 20/20 eligible via the API and 79/100 through the UI, with
the only trace being the substring `generic:glaucoma@v0` inside an identity
string a human has to notice in a monospace column. For a tool whose thesis is
that every number traces to a seed, a pack and a ledger entry, inventing a
population on a typo and not saying so is worse than a missing label: it
produces a **confident wrong provenance**.

**What it pins.**
1. `resolve_priors` is the single resolver — no consumer re-implements the match.
2. Every stakeholder-facing response carries `population.generic`, as a field.
3. `quotable` is DERIVED from the pack's own provenance, so it cannot go stale
   the way `narration.model` did. This is the same rule as
   `test_ledger_agrees_with_evidence.py`, applied to the code written here.
4. The canary: a generic condition is distinguishable from a packed one by the
   field alone, not by parsing an identity string.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from spp.api.main import app, population_provenance
from spp.cohort import for_condition, resolve_priors
from spp.cohort.packs import PACK_DIR, load_all_packs

client = TestClient(app)

# A condition no pack covers. Chosen because it is a real indication, so the
# fallback looks plausible rather than obviously bogus — which is the hazard.
UNPACKED = "glaucoma"


@pytest.fixture(scope="module")
def packs():
    return load_all_packs()


@pytest.fixture(autouse=True)
def _clean_pack_cache():
    """This module writes packs into temp directories. Without isolation a test
    here would leave the cache pointing at a deleted tmp_path and every later
    suite in the session would resolve conditions against nothing."""
    from spp.cohort import clear_pack_cache

    clear_pack_cache()
    yield
    clear_pack_cache()


class TestTheResolverIsSingular:
    def test_resolve_priors_reports_the_pack(self, packs):
        epi, pack = resolve_priors("type 2 diabetes")
        assert pack is not None
        # load_all_packs is keyed by CONDITION, not pack name — asserting that
        # here rather than assuming it is the kind of detail that makes a test
        # pass for the wrong reason.
        assert pack.condition in packs
        assert pack.name == "type_2_diabetes"
        assert epi.label == pack.condition

    def test_an_unpacked_condition_returns_none_not_a_guess(self):
        _epi, pack = resolve_priors(UNPACKED)
        assert pack is None

    def test_for_condition_still_agrees_with_the_resolver(self):
        """Two public entry points, one behaviour. If `for_condition` ever stops
        delegating, the sampling path and the reporting path disagree — which is
        the source/consumer split this whole change closes."""
        for condition in (UNPACKED, "type 2 diabetes", "COPD", ""):
            direct = for_condition(condition)
            via_resolver, _pack = resolve_priors(condition)
            assert direct.label == via_resolver.label
            assert direct.age_mean == via_resolver.age_mean
            assert direct.stage_weights == via_resolver.stage_weights

    def test_the_match_is_forgiving_in_both_directions(self):
        """Case, alias and substring matching live in `pack_for`, so the
        reporter must see the same answers the sampler does. A consumer that
        re-implemented this would disagree here first."""
        for spelling in ("type 2 diabetes", "TYPE 2 DIABETES", "Type 2 Diabetes", "T2D"):
            _epi, pack = resolve_priors(spelling)
            assert pack is not None, f"{spelling!r} stopped matching in one path"

    def test_generic_epis_own_text_admits_what_it_is(self):
        _epi, pack = resolve_priors(UNPACKED)
        assert pack is None
        epi, _ = resolve_priors("")
        assert "no prior pack" in epi.source_note or "Fallback" in epi.source_note


class TestTheFieldExists:
    def test_preview_carries_it(self):
        body = client.post("/scenario/preview", json={
            "condition": "type 2 diabetes", "n": 50, "seed": 42,
            "inclusion": ["age >= 50"],
        }).json()
        assert "population" in body
        assert body["population"]["generic"] is False
        assert body["population"]["prior_pack"] == "type_2_diabetes"

    def test_a_generic_condition_is_flagged_not_styled_away(self):
        """The canary against a field that always says False."""
        body = client.post("/scenario/preview", json={
            "condition": UNPACKED, "n": 50, "seed": 42, "inclusion": [],
        }).json()

        assert body["population"]["generic"] is True
        assert body["population"]["prior_pack"] is None
        assert body["population"]["pack_version"] == 0
        # The number still comes back, because the fallback is a legitimate
        # design choice — it is the SILENCE that was the defect.
        assert body["eligible"] >= 0
        assert "generic" in body["population"]["why_not_quotable"].lower()

    def test_the_identity_string_is_no_longer_the_only_tell(self):
        """A reader who never looks at the identity column still gets the fact."""
        packed = client.post("/scenario/preview", json={
            "condition": "COPD", "n": 20, "seed": 1, "inclusion": [],
        }).json()
        generic = client.post("/scenario/preview", json={
            "condition": UNPACKED, "n": 20, "seed": 1, "inclusion": [],
        }).json()

        assert "generic" in generic["cohort"]["identity"]
        assert "generic" not in packed["cohort"]["identity"]
        # And independently of it:
        assert generic["population"]["generic"] is True
        assert packed["population"]["generic"] is False

    @pytest.mark.parametrize("route,body", [
        ("/simulation/run", {"condition": "type 2 diabetes", "n": 40, "seed": 42}),
        ("/cohort/generate", {"condition": "type 2 diabetes", "n": 10, "seed": 42}),
        ("/protocol/stress-test", {"condition": "type 2 diabetes", "n": 20, "seed": 42}),
        ("/panel/run", {"condition": "type 2 diabetes", "n": 4,
                        "topic": "Could you attend twice a month?"}),
        ("/persona/narrate", {"condition": "type 2 diabetes", "n": 2,
                              "question": "What side effects should I expect?"}),
        ("/room/session", {"condition": "type 2 diabetes", "n": 4, "seed": 42}),
        ("/studio/marginals", {"condition": "type 2 diabetes", "n": 100, "seed": 42}),
    ])
    def test_every_stakeholder_endpoint_reports_it(self, route, body):
        """Nine call sites resolve a condition. Checking one and leaving the rest
        is how a flag becomes a lie of omission on the endpoints nobody tested."""
        response = client.post(route, json=body)
        assert response.status_code == 200, (route, response.text[:300])
        payload = response.json()
        assert "population" in payload, f"{route} omits population"
        assert payload["population"]["generic"] is False

    def test_counterfactual_reports_it_without_changing_the_artifact_model(self):
        """The population banner is attached at the route, not added to
        DiffReport, so `artifacts.ts` does not churn for it. Asserted, because
        'additive' is a claim until someone checks the model still matches."""
        body = client.post("/counterfactual/run", json={
            "condition": "type 2 diabetes", "n": 60, "seed": 42,
            "inclusion": ["age >= 50"], "burden": {"visits_per_year": 12},
            "remote_visits": ["v001"],
        }).json()
        assert "detail" not in body, body
        assert body["population"]["generic"] is False
        from spp.simulation.report import DiffReport

        assert "population" not in DiffReport.model_fields


class TestQuotabilityIsDerived:
    """The specific trap this change would otherwise have walked into."""

    def test_no_shipped_pack_is_quotable(self, packs):
        assert packs, "no packs found — this class would pass vacuously"
        for name, pack in packs.items():
            provenance = population_provenance(pack.condition)
            assert provenance["quotable"] is False, (
                f"{name} reports quotable; every shipped marginal is "
                f"EXPERT_GUESS, so the derivation is broken"
            )
            assert provenance["unquotable_fields"], (
                f"{name} lists no unquotable marginals while quotable is False — "
                f"the two fields disagree"
            )
    def test_it_would_flip_if_a_pack_became_fitted(self, tmp_path):
        """The canary. A pack whose every marginal and correlation is
        CUSTOMER_DATA_FITTED must read quotable. Without this, `quotable: False`
        would be a literal wearing a derivation's clothes, and it would go stale
        exactly the way `narration.model` did — which is the bug this file exists
        to close."""
        from spp.cohort.packs import PriorPack

        source = next(iter(Path(PACK_DIR).glob("*.json")))
        payload = json.loads(source.read_text())

        def _fit(entry: dict) -> None:
            entry.setdefault("provenance", {})["kind"] = "customer_data_fitted"
            entry["provenance"].setdefault("source", "synthetic fixture for the guard")
            entry["provenance"].setdefault("confidence", "measured")

        # Exactly the two collections `PriorPack.unquotable()` reads. Derivations
        # carry their own Provenance and are deliberately left unfit — that is not
        # an oversight of this test, it is the gap the next test records.
        for marginal in payload["marginals"]:
            _fit(marginal)
        for pair in payload.get("latent_correlations", []):
            _fit(pair)

        path = tmp_path / "fitted.json"
        path.write_text(json.dumps(payload))
        fitted = PriorPack.model_validate_json(path.read_text())

        assert fitted.unquotable() == [], (
            "the fixture pack still has unquotable entries, so the assertion "
            "below would prove nothing"
        )
        # Read from tmp_path. Against the shipped PACK_DIR this same call returns
        # the EXPERT_GUESS pack, and the canary would assert the wrong thing
        # about its own fixture while still going green.
        provenance = population_provenance(fitted.condition, pack_dir=tmp_path)
        assert provenance["quotable"] is True
        assert provenance["unquotable_fields"] == []
        assert provenance["prior_pack"] == fitted.name
        assert provenance["generic"] is False

    def test_derivations_are_not_covered_by_the_quotability_gate(self, tmp_path):
        """A HOLE, recorded rather than papered over.

        `PriorPack.unquotable()` reads marginals and latent correlations. It does
        NOT read `derivations.provenance`, which carries its own Provenance and is
        `EXPERT_GUESS` in every shipped pack — the barrier-severity magnitudes that
        drive burden. So a pack with every marginal fitted reports `quotable`,
        while the numbers turning barriers into a burden score remain judgement.

        This test pins the current behaviour so the gap is visible at the gate
        rather than discovered in a customer's report. Closing it means either
        extending `unquotable()` to derivations or giving derivations their own
        quotability, and that is a decision about what a finding is — not a fix to
        slip into Phase B's stride.
        """
        from spp.cohort.packs import PriorPack

        source = next(iter(Path(PACK_DIR).glob("*.json")))
        payload = json.loads(source.read_text())
        for marginal in payload["marginals"]:
            marginal.setdefault("provenance", {})["kind"] = "customer_data_fitted"
            marginal["provenance"].setdefault("source", "guard fixture")
            marginal["provenance"].setdefault("confidence", "measured")
        for pair in payload.get("latent_correlations", []):
            pair.setdefault("provenance", {})["kind"] = "customer_data_fitted"
            pair["provenance"].setdefault("source", "guard fixture")
            pair["provenance"].setdefault("confidence", "measured")
        # derivations deliberately left EXPERT_GUESS.
        path = tmp_path / "half_fitted.json"
        path.write_text(json.dumps(payload))
        pack = PriorPack.model_validate_json(path.read_text())

        assert pack.derivations.provenance.quotable is False, (
            "the derivation provenance stopped being judgement; this test's "
            "premise no longer holds and the gate above needs revisiting"
        )
        assert pack.unquotable() == [], (
            "unquotable() now covers derivations — the hole closed, so update "
            "population_provenance's derivation and this test"
        )
        # And therefore, today:
        assert population_provenance(pack.condition, pack_dir=tmp_path)["quotable"] is True

    def test_the_unquotable_list_comes_from_the_pack_not_a_string(self, packs):
        """Field-level, not pack-level: a partially fitted pack reports the
        fields that are still judgement."""
        for name, pack in packs.items():
            provenance = population_provenance(pack.condition)
            assert provenance["unquotable_fields"] == pack.unquotable(), (
                f"{name}: the response re-derived the list instead of reading it"
            )

    def test_the_health_endpoint_agrees_with_the_field(self, packs):
        """Two surfaces, one fact. /health says how many marginals are quotable;
        population_provenance says it per condition. They must not disagree."""
        health = client.get("/health").json()
        total_quotable = health["priors"]["quotable_marginals"]
        per_condition = sum(
            len(population_provenance(pack.condition)["unquotable_fields"])
            for pack in packs.values()
        )
        if total_quotable == 0:
            assert per_condition > 0, (
                "/health says nothing is quotable while every pack reports an "
                "empty unquotable list — one of the two is stale"
            )
        assert health["priors"]["any_number_quotable"] is (total_quotable > 0)


class TestThePackCacheIsPerDirectory:
    """The bug this change exists to close, held shut.

    `load_all_packs(directory)` used to return the DEFAULT directory's packs for
    any argument once anything had loaded once, because the cache was a single
    global. The parameter was honoured cold and ignored warm, which is worse than
    not having it: the caller wrote code that looks right. Discovered only because
    a quotability canary needed a fitted pack in a temp directory and got the
    shipped `EXPERT_GUESS` one instead — returning `quotable: False` for a pack
    that was, in fact, fitted, and going green. A canary that reads the wrong
    artifact is not a canary.
    """

    def test_a_second_directory_is_not_served_the_first_ones_packs(self, tmp_path):
        from spp.cohort import clear_pack_cache, load_all_packs, pack_for

        clear_pack_cache()
        try:
            # Warm the cache on the production directory first — that is the
            # ordering that used to break.
            assert load_all_packs(), "no shipped packs found"

            source = next(iter(Path(PACK_DIR).glob("*.json")))
            payload = json.loads(source.read_text())
            payload["name"] = "synthetic_fitted"
            payload["condition"] = "synthetic fitted condition"
            payload["aliases"] = ["sfc"]
            for entry in [*payload["marginals"], *payload.get("latent_correlations", [])]:
                entry.setdefault("provenance", {})["kind"] = "customer_data_fitted"
                entry["provenance"].setdefault("source", "guard fixture")
                entry["provenance"].setdefault("confidence", "measured")
            (tmp_path / "synthetic.json").write_text(json.dumps(payload))

            loaded = load_all_packs(tmp_path)
            assert set(loaded) == {"synthetic fitted condition"}, (
                f"the temp directory returned {sorted(loaded)} — the cache is "
                f"keyed on something other than the directory again"
            )
            assert pack_for("synthetic fitted condition", directory=tmp_path) is not None
            assert pack_for("type 2 diabetes", directory=tmp_path) is None, (
                "the shipped pack leaked into a caller's temp directory"
            )
        finally:
            clear_pack_cache()

    def test_the_default_path_still_caches(self):
        """The performance property is not being thrown away with the bug."""
        from spp.cohort import clear_pack_cache, load_all_packs

        clear_pack_cache()
        first = load_all_packs()
        second = load_all_packs()
        assert first is second, "the default directory is re-reading disk"

    def test_refresh_re_reads_disk(self, tmp_path):
        from spp.cohort import clear_pack_cache, load_all_packs

        clear_pack_cache()
        try:
            (tmp_path / "a.json").write_text(
                (Path(PACK_DIR) / "type_2_diabetes.json").read_text()
            )
            assert load_all_packs(tmp_path)
            (tmp_path / "a.json").unlink()
            assert not load_all_packs(tmp_path, refresh=True), (
                "refresh did not re-read; a deleted pack is still being served"
            )
        finally:
            clear_pack_cache()


class TestTheFallbackIsStillAllowed:
    """A generic population is a legitimate design choice for exploration. The
    defect was silence, not the fallback — so nothing here may turn it into an
    error."""

    def test_an_unknown_condition_still_returns_200(self):
        response = client.post("/scenario/preview", json={
            "condition": UNPACKED, "n": 30, "seed": 7, "inclusion": [],
        })
        assert response.status_code == 200

    def test_an_empty_condition_does_not_crash(self):
        response = client.post("/scenario/preview", json={
            "condition": "", "n": 10, "seed": 7, "inclusion": [],
        })
        assert response.status_code in (200, 422)
        if response.status_code == 200:
            assert response.json()["population"]["generic"] is True

    def test_the_note_names_what_was_invented(self):
        provenance = population_provenance(UNPACKED)
        assert provenance["population_label"]
        assert "generic" in provenance["population_note"].lower() or \
               "fallback" in provenance["population_note"].lower()
