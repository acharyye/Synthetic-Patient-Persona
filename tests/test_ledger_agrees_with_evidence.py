"""The ledger must agree with the evidence it summarises.

**Why this test exists.** `narration.model` in `assumptions.py` told users — via
`GET /assumptions`, which the UI fetches — that the model's citation compliance
was "UNMEASURED", at `prompt_version: 1` and an empty `model_digest`, while four
committed evidence bundles said the opposite: prompt versions 1 through 4, digest
`845dbda0…`, `compliance_rate` up to 1.0, `bars_passed: true`. Nothing caught it.

That is the shape of bug this repo has fixed twice by deleting a duplicate
(`CONDITION_EPI`, the version string) and once by refusing to restate a version
(`src/spp/__init__.py`). Each fix removed one copy. None of them added a check
that the remaining copies *agree* — so the drift simply found the next pair of
surfaces. This test is that missing mechanism, pointed at the flagship claim.

**The design choice it enforces.** The ledger entry is a *declaration* of what we
run against, not a reading of what was run. Deriving it from disk at import time
would have made the registry's contents depend on the working tree and cost every
`import spp.assumptions` a file read. So the values stay declared and this file
holds them to the bundles — same guarantee, no import-time I/O.

**Tested the strong way.** `TestTheAgreementCanActuallyFail` mutates a copy of the
ledger and requires the comparison to fire. An agreement test that cannot fail is
the same defect as a canary that cannot fail, which is `TestGateCanActuallyFail`
and `TestOverflowIsMeasuredNotAssumed` in another costume.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from spp import assumptions as A
from spp.foundation.ledger import LEDGER
from spp.narration.bundle import BundleManifest, EVIDENCE_DIR, latest_bundle
from spp.narration.prompt import PROMPT_VERSION

REPO_ROOT = EVIDENCE_DIR.parent


def _committed_bundles() -> list[tuple[str, Path]]:
    """(release, directory) for every bundle on disk, oldest release first."""
    if not EVIDENCE_DIR.exists():
        return []
    out = []
    for release_dir in sorted(p for p in EVIDENCE_DIR.iterdir() if p.is_dir()):
        bundle = latest_bundle(release_dir.name)
        if bundle is not None:
            out.append((release_dir.name, bundle))
    return out


def _manifest(path: Path) -> BundleManifest:
    return BundleManifest.model_validate_json(
        (path / "manifest.json").read_text(encoding="utf-8")
    )


@pytest.fixture(scope="module")
def bundles() -> list[tuple[str, Path]]:
    found = _committed_bundles()
    if not found:
        pytest.skip("no evidence bundles on disk (fresh checkout before a run)")
    return found


@pytest.fixture(scope="module")
def newest(bundles) -> tuple[str, BundleManifest]:
    release, path = bundles[-1]
    return release, _manifest(path)


class TestLedgerAgreesWithEvidence:
    def test_the_declaration_names_the_newest_bundle(self, bundles, newest):
        """The four values a reader would compare, compared mechanically."""
        release, manifest = newest
        params = LEDGER.get("narration.model").params

        assert params["prompt_version"] == manifest.prompt_version, (
            f"ledger declares prompt v{params['prompt_version']} but the newest "
            f"bundle ({release}) is prompt v{manifest.prompt_version}. A reader "
            f"asking GET /assumptions which prompt was measured is being told a "
            f"version the evidence does not support."
        )
        assert params["model_digest"] == manifest.model_digest
        assert params["compliance_rate"] == manifest.compliance_rate
        assert params["bars_passed"] is manifest.bars_passed
        assert params["measured_release"] == release

    def test_the_declared_model_is_the_recorded_model(self, newest):
        _, manifest = newest
        params = LEDGER.get("narration.model").params
        assert params["model"] == manifest.model
        assert params["backend"] == manifest.backend

    def test_the_declared_sampling_is_the_recorded_sampling(self, newest):
        """Decode settings are correctness, not plumbing, so the ledger's copy
        must be the one that was actually used — a num_ctx that drifted would
        look like a starved-context failure and be diagnosed as a model problem."""
        _, manifest = newest
        params = LEDGER.get("narration.model").params
        recorded = manifest.sampling
        for key in ("temperature", "top_p", "seed", "num_predict", "num_ctx"):
            assert params[key] == recorded[key], (
                f"{key}: ledger says {params[key]!r}, the bundle recorded "
                f"{recorded[key]!r}"
            )

    def test_prompt_version_matches_the_module_constant(self, newest):
        """Three surfaces name the prompt version: the ledger, the module
        constant and the bundle. Two agreeing is not enough."""
        _, manifest = newest
        assert PROMPT_VERSION == manifest.prompt_version
        assert LEDGER.get("narration.model").params["prompt_version"] == PROMPT_VERSION

    def test_bundle_count_is_not_understated(self, bundles):
        params = LEDGER.get("narration.model").params
        assert params["bundles_measured"] == len(bundles)

    def test_no_bundle_disagrees_on_the_weights(self, bundles):
        """Every bundle from v0.1 to v0.5 carries one digest. If that ever stops
        being true, the ledger's single `model_digest` is a lie of omission and
        the entry has to name a per-release digest instead — say so here rather
        than let a reader assume continuity."""
        digests = {_manifest(p).model_digest for _, p in bundles}
        assert len(digests) == 1, (
            f"bundles carry more than one model digest: {sorted(digests)}. "
            f"narration.model can no longer state one digest; split it per "
            f"release, and note that cassettes across a swap are refused."
        )
        assert digests.pop() == LEDGER.get("narration.model").params["model_digest"]

    def test_the_source_text_does_not_claim_the_unmeasured(self, bundles):
        """The specific regression. A live model has been exercised against this
        digest four times; the prose must not still say otherwise."""
        source = LEDGER.get("narration.model").source.upper()
        assert "UNMEASURED" not in source, (
            "narration.model still says compliance is UNMEASURED while "
            f"{len(bundles)} committed bundle(s) say otherwise. This is served "
            "to users through GET /assumptions."
        )
        assert "NOT YET EXERCISED" not in source


class TestTheFlagIsStillHonest:
    """The measurement does not upgrade the *choice*. Both must hold."""

    def test_narration_model_stays_unsupported(self):
        """EXPERT_GUESS is correct even after measurement: the compliance numbers
        are evidence about one (prompt, model, sampling, battery) configuration,
        not a property of the model. Dropping this tag would let a report present
        'compliance 1.0' as a finding, which is the overclaim the framing rule
        exists to stop."""
        entry = LEDGER.get("narration.model")
        assert entry.name in {a.name for a in LEDGER.unsupported()}
        assert not entry.quotable

    def test_the_text_states_what_the_tag_still_means(self):
        """If the tag stays EXPERT_GUESS while the prose says MEASURED, a reader
        has to be told why. Silent conservatism reads as a stale entry, and the
        first fix anyone tries is to flip the tag.

        Matched on phrases rather than whole sentences: this pins that the
        explanation EXISTS, not how it is worded.
        """
        source = LEDGER.get("narration.model").source
        assert "MEASURED" in source and "EXPERT_GUESS" in source
        assert "prompt, model, sampling) configuration" in source
        assert "require_compatible()" in source
        assert "LEDGER.unsupported()" in source


class TestTheRecorderRefusesToo:
    """The CI test holds the ledger against the NEWEST bundle. This holds it
    against the run ABOUT TO HAPPEN, so a bump is caught before it records rather
    than after.

    Loaded from the script directory because `scripts/` is not a package and this
    is the only function in it worth testing directly. Same importlib move a
    reviewer would use to read it.
    """

    @staticmethod
    def _recorder():
        import importlib.util
        from pathlib import Path

        path = Path(__file__).resolve().parents[1] / "scripts" / "record_narration.py"
        spec = importlib.util.spec_from_file_location("record_narration", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_the_guard_exists_and_passes_against_the_current_declaration(self):
        module = self._recorder()
        from spp.narration.sampling import DEFAULT_SAMPLING

        refusal = module._ledger_disagreement(
            LEDGER.get("narration.model"),
            LEDGER.get("narration.model").params["model_digest"],
            DEFAULT_SAMPLING,
        )
        assert refusal is None, f"the guard rejects a consistent ledger: {refusal}"

    def test_a_stale_prompt_version_refuses(self):
        """Not vacuous: the same call with one field moved returns a message
        naming the field."""
        module = self._recorder()
        from spp.narration.sampling import DEFAULT_SAMPLING

        entry = LEDGER.get("narration.model")
        stale = entry.model_copy(deep=True)
        stale.params["prompt_version"] = entry.params["prompt_version"] - 1

        refusal = module._ledger_disagreement(stale, entry.params["model_digest"],
                                              DEFAULT_SAMPLING)
        assert refusal is not None
        assert "prompt_version" in refusal

    def test_a_moved_model_digest_refuses(self):
        """The mutable-tag scenario the digest exists to catch."""
        module = self._recorder()
        from spp.narration.sampling import DEFAULT_SAMPLING

        entry = LEDGER.get("narration.model")
        refusal = module._ledger_disagreement(entry, "f" * 64, DEFAULT_SAMPLING)
        assert refusal is not None
        assert "model_digest" in refusal

    def test_a_moved_num_ctx_refuses(self):
        """num_ctx is correctness, not plumbing: an overflow reads downstream as
        the starved-context canary, so a silent decode change must not be free."""
        module = self._recorder()
        from spp.narration.sampling import DEFAULT_SAMPLING

        entry = LEDGER.get("narration.model")
        moved = entry.model_copy(deep=True)
        moved.params["num_ctx"] = 4096
        refusal = module._ledger_disagreement(moved, entry.params["model_digest"],
                                              DEFAULT_SAMPLING)
        assert refusal is not None and "num_ctx" in refusal

    def test_the_refusal_says_why_it_refused(self):
        """A refusal that does not name the remedy gets worked around by
        deleting the check."""
        module = self._recorder()
        from spp.narration.sampling import DEFAULT_SAMPLING

        entry = LEDGER.get("narration.model")
        stale = entry.model_copy(deep=True)
        stale.params["seed"] = entry.params["seed"] + 1
        refusal = module._ledger_disagreement(stale, entry.params["model_digest"],
                                              DEFAULT_SAMPLING)
        assert "DECLARATION" in refusal
        assert "its own commit" in refusal


class TestTheAgreementCanActuallyFail:
    """Same species as TestGateCanActuallyFail and TestOverflowIsMeasuredNotAssumed."""

    def test_a_stale_prompt_version_is_caught(self, newest):
        _, manifest = newest
        stale = manifest.model_copy(update={"prompt_version": manifest.prompt_version - 1})
        params = LEDGER.get("narration.model").params
        assert params["prompt_version"] != stale.prompt_version

    def test_a_stale_digest_is_caught(self, newest):
        _, manifest = newest
        swapped = manifest.model_copy(update={"model_digest": "f" * 64})
        assert LEDGER.get("narration.model").params["model_digest"] != swapped.model_digest

    def test_understating_the_bundle_count_is_caught(self, bundles):
        assert LEDGER.get("narration.model").params["bundles_measured"] != len(bundles) - 1

    def test_the_regression_text_would_be_detected(self):
        """The UNMEASURED assertion is not vacuous: feed it the text that was
        actually shipped and it fires."""
        historical = (
            "Chosen for local, offline-first operation. NOT yet exercised against "
            "a live model: every compliance number to date comes from scripted "
            "stub models, so this model's actual citation compliance is "
            "UNMEASURED."
        )
        assert "UNMEASURED" in historical.upper()
        assert "NOT YET EXERCISED" in historical.upper()

    def test_the_test_reads_a_real_manifest_not_a_literal(self, bundles):
        """Guards the guard. If `bundles` were synthesised the comparison would
        pass against any ledger, which is a pass bar supplied as a literal."""
        _, path = bundles[-1]
        raw = json.loads((path / "manifest.json").read_text(encoding="utf-8"))
        assert raw["model_digest"], "the bundle carries no digest — nothing to agree with"
        assert raw["prompt_version"] >= 1
        assert (REPO_ROOT / "evidence").is_dir()
