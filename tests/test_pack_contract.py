"""Statistical contract, GENERATED from prior-pack contents.

The pack is the single source of truth. Every assertion below is parametrized
over what the packs actually declare — marginals against their own stated
tolerance, latent correlations via the `uniform_pearson` closed form. Nothing
here restates a number that lives in a pack.

Why generated rather than hand-written: a contract written beside the data is a
second copy of the same numbers, and two copies drift. Generated means adding a
pack is adding data, the suite grows itself, and **a new pack cannot ship without
contract coverage by construction**.

This complements, not replaces, the golden files:

    golden diff + contract green  -> implementation changed, distribution intact
    golden diff + contract red    -> the distribution moved; look hard

and now it isolates that per pack.
"""
from datetime import date

import numpy as np
import pytest

from spp.cohort import generate_cohort
from spp.cohort.correlation import TRAIT_AXES, CopulaSampler, uniform_pearson
from spp.cohort.packs import PACK_DIR as PACK_DIR_PATH, PriorPack, load_all_packs

AS_OF = date(2026, 8, 1)
N = 800

PACKS = load_all_packs()
assert PACKS, "no prior packs found — run scripts/export_prior_packs.py"

PACK_IDS = sorted(PACKS)


def _cohort(condition: str):
    return generate_cohort(condition, N, seed=42, as_of=AS_OF)


COHORTS = {condition: _cohort(condition) for condition in PACK_IDS}


# --- parameter sets built from pack contents ------------------------------

def _marginal_cases(family: str) -> list[tuple[str, str]]:
    return [
        (condition, spec.field)
        for condition in PACK_IDS
        for spec in PACKS[condition].marginals
        if spec.family == family
    ]


CATEGORICAL_CASES = _marginal_cases("categorical")
NORMAL_CASES = _marginal_cases("normal")
BERNOULLI_CASES = _marginal_cases("bernoulli_set")
CORRELATION_CASES = [
    (condition, pair.key)
    for condition in PACK_IDS
    for pair in PACKS[condition].latent_correlations
]


def observed_categorical(cohort, field: str) -> dict[str, float]:
    """Realized distribution of a categorical field."""
    values = [getattr(persona, field) for persona in cohort]
    values = [v for v in values if v is not None]
    counts: dict[str, float] = {}
    for value in values:
        counts[str(value)] = counts.get(str(value), 0) + 1
    return {name: count / len(values) for name, count in counts.items()}


class TestPacksAreLoadable:
    @pytest.mark.parametrize("condition", PACK_IDS)
    def test_pack_validates_and_is_psd(self, condition):
        """Load-time validation is the gate: field coverage, parameter sanity and
        the PSD check all run inside PriorPack validation."""
        pack = PACKS[condition]
        assert isinstance(pack, PriorPack)
        matrix = pack.correlation_matrix()
        assert float(np.linalg.eigvalsh(matrix)[0]) > 0.0

    @pytest.mark.parametrize("condition", PACK_IDS)
    def test_every_entry_carries_provenance(self, condition):
        pack = PACKS[condition]
        for spec in pack.marginals:
            assert spec.provenance.source
        for pair in pack.latent_correlations:
            assert pair.provenance.source

    @pytest.mark.parametrize("condition", PACK_IDS)
    def test_unquotable_entries_are_enumerable(self, condition):
        """The caveats stay machine-readable per pack, not just globally."""
        assert PACKS[condition].unquotable()

    @pytest.mark.parametrize("condition", PACK_IDS)
    def test_correlations_are_fully_specified(self, condition):
        """Packs inherit the direct-semantics rule: no sparse specs. An omitted
        pair asserts independence, so a pack must say what it asserts."""
        pack = PACKS[condition]
        assert len(pack.latent_correlations) >= 20


class TestMarginalContract:
    @pytest.mark.parametrize("condition,field", CATEGORICAL_CASES,
                             ids=[f"{c}:{f}" for c, f in CATEGORICAL_CASES])
    def test_categorical_matches_pack_within_its_tolerance(self, condition, field):
        spec = PACKS[condition].marginal(field)
        observed = observed_categorical(COHORTS[condition], field)

        for name, expected in spec.params.items():
            got = observed.get(name, 0.0)
            assert abs(got - float(expected)) <= spec.tolerance, (
                f"{condition}/{field}/{name}: {got:.3f} vs pack {expected} "
                f"(tolerance {spec.tolerance})"
            )

    @pytest.mark.parametrize("condition,field", NORMAL_CASES,
                             ids=[f"{c}:{f}" for c, f in NORMAL_CASES])
    def test_normal_matches_pack_within_its_tolerance(self, condition, field):
        spec = PACKS[condition].marginal(field)
        cohort = COHORTS[condition]

        if field.startswith("biomarker:"):
            name = field.split(":", 1)[1]
            values = [p.biomarkers[name] for p in cohort if name in p.biomarkers]
            # stage_shift moves the mean per stage, so the pooled mean is a
            # weighted blend, not `mean` — assert support and spread only.
            if spec.params.get("stage_shift"):
                lo, hi = spec.support
                assert all(lo <= v <= hi for v in values)
                return
        else:
            values = [getattr(p, field) for p in cohort]

        assert values
        assert abs(float(np.mean(values)) - spec.params["mean"]) <= spec.tolerance, (
            f"{condition}/{field}: mean {np.mean(values):.2f} vs pack "
            f"{spec.params['mean']} (tolerance {spec.tolerance})"
        )
        if spec.support:
            lo, hi = spec.support
            assert lo <= min(values) <= max(values) <= hi

    @pytest.mark.parametrize("condition,field", BERNOULLI_CASES,
                             ids=[f"{c}:{f}" for c, f in BERNOULLI_CASES])
    def test_bernoulli_set_preserves_pack_ordering(self, condition, field):
        """Absolute prevalence is shifted by the structural paths the pack itself
        declares (age factor, latent load), so the contract is on ORDERING —
        which those monotone modulations preserve."""
        spec = PACKS[condition].marginal(field)
        cohort = COHORTS[condition]
        assert spec.structural_paths, (
            "a field modulated outside the copula must declare structural_paths, "
            "or a reader will file a bug against correct behaviour"
        )

        observed: dict[str, int] = {}
        for persona in cohort:
            for name in getattr(persona, field):
                observed[name] = observed.get(name, 0) + 1

        top_pack = {
            name for name, _ in sorted(
                spec.params.items(), key=lambda kv: -float(kv[1])
            )[:3]
        }
        top_observed = {
            name for name, _ in sorted(observed.items(), key=lambda kv: -kv[1])[:3]
        }
        assert len(top_pack & top_observed) >= 2, (
            f"{condition}/{field}: top observed {top_observed} vs pack {top_pack}"
        )


class TestLatentCorrelationContract:
    """Asserted at the level the pack specifies: latent Gaussian rho, checked via
    the closed-form attenuation to the uniforms. Never on realized discrete
    marginals — that tolerance would have to be wide enough to hide a real bug.
    """

    @staticmethod
    def _realized(condition: str) -> np.ndarray:
        sampler = CopulaSampler(PACKS[condition].correlation_matrix())
        gen = np.random.default_rng(0)
        draws = np.array([
            [d[a] for a in TRAIT_AXES]
            for d in (sampler.draw(gen) for _ in range(30_000))
        ])
        return np.corrcoef(draws.T)

    @pytest.mark.parametrize("condition,key", CORRELATION_CASES,
                             ids=[f"{c}:{k}" for c, k in CORRELATION_CASES])
    def test_each_declared_pair_reproduces_after_known_attenuation(
        self, condition, key, realized_cache
    ):
        pack = PACKS[condition]
        pair = next(p for p in pack.latent_correlations if p.key == key)
        realized = realized_cache[condition]
        index = {name: i for i, name in enumerate(TRAIT_AXES)}

        i, j = index[pair.axis_a], index[pair.axis_b]
        expected = uniform_pearson(pair.rho)
        assert abs(realized[i, j] - expected) <= pair.tolerance, (
            f"{condition}/{key}: latent {pair.rho:+.2f} -> expected uniform "
            f"{expected:+.4f}, got {realized[i, j]:+.4f}"
        )

    @pytest.mark.parametrize("condition", PACK_IDS)
    def test_pairs_the_pack_omits_really_are_uncorrelated(
        self, condition, realized_cache
    ):
        pack = PACKS[condition]
        realized = realized_cache[condition]
        index = {name: i for i, name in enumerate(TRAIT_AXES)}
        declared = {
            tuple(sorted((p.axis_a, p.axis_b))) for p in pack.latent_correlations
        }

        for left in TRAIT_AXES:
            for right in TRAIT_AXES:
                if left >= right or tuple(sorted((left, right))) in declared:
                    continue
                i, j = index[left], index[right]
                assert abs(realized[i, j]) < 0.03, (
                    f"{condition}: {left}|{right} undeclared but realized "
                    f"{realized[i, j]:+.3f}"
                )


@pytest.fixture(scope="session")
def realized_cache():
    """Sampled once per pack — 30k draws per condition is the expensive part."""
    return {
        condition: TestLatentCorrelationContract._realized(condition)
        for condition in PACK_IDS
    }


class TestPacksAreTheSourceOfTruth:
    def test_the_in_code_table_is_gone(self):
        """Two copies of the same priors drift. There must be exactly one."""
        import spp.cohort.epidemiology as epi

        assert not hasattr(epi, "CONDITION_EPI"), (
            "CONDITION_EPI was migrated into prior packs and must not come back"
        )

    @pytest.mark.parametrize("condition", PACK_IDS)
    def test_for_condition_reads_the_pack(self, condition):
        """The generator's view must be the pack's contents, not a parallel copy."""
        from spp.cohort import for_condition

        pack = PACKS[condition]
        resolved = for_condition(condition)

        assert resolved.label == pack.condition
        assert resolved.age_mean == pack.marginal("age").params["mean"]
        assert resolved.age_sd == pack.marginal("age").params["sd"]
        assert resolved.female_fraction == pytest.approx(
            pack.marginal("sex").params["female"]
        )
        assert resolved.stage_weights.keys() == pack.marginal("stage").params.keys()
        assert (
            resolved.comorbidity_prevalence.keys()
            == pack.marginal("comorbidities").params.keys()
        )

    def test_an_unmapped_condition_falls_back_without_a_pack(self):
        from spp.cohort import for_condition
        from spp.cohort.epidemiology import GENERIC_EPI

        assert for_condition("a condition nobody packed").label == GENERIC_EPI.label
        assert for_condition("").label == GENERIC_EPI.label

    def test_aliases_resolve_through_packs(self):
        from spp.cohort import for_condition

        assert for_condition("T2D").label == "type 2 diabetes"
        assert for_condition("copd").label == "COPD"

    def test_a_malformed_pack_fails_at_load_with_a_useful_error(self, tmp_path):
        """Community packs must fail loudly, not downstream in generation."""
        import json

        from spp.cohort.packs import PackError, load_pack

        bad = tmp_path / "bad.json"
        bad.write_text(json.dumps({
            "schema_version": 1, "name": "bad", "condition": "bad",
            "marginals": [], "latent_correlations": [],
        }))
        with pytest.raises(PackError, match="missing required marginals"):
            load_pack(bad)

    def test_a_non_psd_pack_is_rejected_at_load(self, tmp_path):
        """The PSD gate runs at pack load, so the eigenvector diagnostic reaches
        whoever wrote the pack."""
        import json

        from spp.cohort.packs import PackError, load_pack

        template = json.loads(
            (PACK_DIR_PATH / "type_2_diabetes.json").read_text(encoding="utf-8")
        )
        template["latent_correlations"] = [
            {"axis_a": "age", "axis_b": "mobility", "rho": 0.95,
             "provenance": {"source": "x", "confidence": "expert_guess"}},
            {"axis_a": "mobility", "axis_b": "financial_security", "rho": 0.95,
             "provenance": {"source": "x", "confidence": "expert_guess"}},
            {"axis_a": "age", "axis_b": "financial_security", "rho": -0.95,
             "provenance": {"source": "x", "confidence": "expert_guess"}},
        ]
        path = tmp_path / "nonpsd.json"
        path.write_text(json.dumps(template))

        with pytest.raises(PackError, match="not positive definite"):
            load_pack(path)


class TestPersonaIdentityIsGloballyUnique:
    """The ID collision was a class, not an instance.

    `synthetic-0000` existed in every condition, so any dict, file, report or
    route keyed on a bare patient_id was a latent collision — the compliance eval
    hit exactly that. Fixed at the source rather than per-consumer, because
    Phase 4 turns these into `/persona/{id}` and an ambiguous id becomes a
    user-facing wrong-page bug.
    """

    def test_ids_do_not_collide_across_conditions(self):
        from spp.cohort import generate_cohort

        seen: dict[str, str] = {}
        for condition in PACK_IDS:
            for persona in generate_cohort(condition, 8, seed=42, as_of=AS_OF):
                assert persona.patient_id not in seen, (
                    f"{persona.patient_id} appears in both {seen.get(persona.patient_id)} "
                    f"and {condition}"
                )
                seen[persona.patient_id] = condition

    def test_ids_do_not_collide_across_seeds(self):
        from spp.cohort import generate_cohort

        a = {p.patient_id for p in generate_cohort("COPD", 6, seed=1, as_of=AS_OF)}
        b = {p.patient_id for p in generate_cohort("COPD", 6, seed=2, as_of=AS_OF)}
        assert not (a & b)

    def test_ids_are_stable_for_the_same_draw(self):
        from spp.cohort import generate_cohort

        first = [p.patient_id for p in generate_cohort("COPD", 6, seed=42, as_of=AS_OF)]
        second = [p.patient_id for p in generate_cohort("COPD", 6, seed=42, as_of=AS_OF)]
        assert first == second

    def test_ids_are_url_safe(self):
        """They become route segments in Phase 4."""
        import re

        from spp.cohort import generate_cohort

        for condition in PACK_IDS:
            for persona in generate_cohort(condition, 3, seed=42, as_of=AS_OF):
                assert re.fullmatch(r"[a-z0-9-]+", persona.patient_id), persona.patient_id

    def test_the_id_encodes_its_provenance(self):
        from spp.cohort import make_patient_id

        assert make_patient_id("type 2 diabetes", 42, 7) == "type-2-diabetes-s42-0007"
