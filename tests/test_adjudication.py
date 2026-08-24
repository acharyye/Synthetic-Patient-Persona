"""The v3 decision procedure, and proof that it can reach every verdict.

The same rule as `TestGateCanActuallyFail` in the protocol CI: a gate that cannot
fail is not protection, and a reading that can only come out one way is not an
adjudication. So each branch of the pre-registered tree is exercised against a
synthesised report.

These tests do not check that the thresholds are right — they are pre-registered
and not this file's business. They check that the code follows them.
"""
import json

import pytest

from spp.narration.adjudication import SHAPE_PATH, adjudicate
from spp.narration.evaluation import ComplianceReport


@pytest.fixture(scope="module")
def shape():
    return json.loads(SHAPE_PATH.read_text(encoding="utf-8"))


def report(**overrides) -> ComplianceReport:
    """A run that passes every arm, unless an override says otherwise."""
    base = dict(
        label="synthetic", prompt_version=3, model="stub", adapter_version=1,
        n_cases=30,
        citation_validity=1.0, factual_coverage=1.0,
        system_recall=0.6, model_recall=0.6, f_recall=0.6, f_recall_cases=29,
        state_coverage=0.8, state_citation_share=0.35,
        feeling_fraction=0.25, inline_marker_takes=0,
        retry_rate=0.1, hard_failure_rate=0.0, parse_failure_rate=0.0,
        circumstantial_segments=40, single_segment_rate=0.0,
        factual_fraction_by_tag={
            "burden": 0.8, "mitigation": 0.9,
            "ae": 0.9333, "tx": 1.0, "proc": 0.9, "sym": 0.5,
        },
    )
    tags = overrides.pop("tags", None)
    if tags:
        base["factual_fraction_by_tag"] = {**base["factual_fraction_by_tag"], **tags}
    return ComplianceReport(**{**base, **overrides})


class TestTheArmsComeFromTheFile:
    def test_thresholds_are_read_not_transcribed(self, shape):
        """A bar copied into code is a bar that can drift from the registration."""
        verdict = adjudicate(report())
        burden = next(a for a in verdict.by_arm("recovery") if a.metric == "burden")
        floor = shape["arms"]["recovery"]["floor"]["burden"]
        ceiling = shape["arms"]["recovery"]["ceiling"]["burden"]
        assert burden.bound == f"expected {floor}..{ceiling}"

    def test_every_registered_arm_is_read(self, shape):
        verdict = adjudicate(report())
        read = {arm.arm for arm in verdict.arms}
        registered = {
            name for name in shape["arms"]
            if not name.startswith("$") and name != "sym_is_not_a_control"
        }
        assert registered <= read, f"arms registered but never read: {registered - read}"

    def test_the_amendment_trail_travels_with_the_verdict(self):
        """A reader must be able to see the file was edited, and when."""
        verdict = adjudicate(report())
        assert verdict.amendments
        assert all(a.get("on") for a in verdict.amendments)


class TestItCanReachEveryVerdict:
    """A procedure that can only say one thing is decoration."""

    def test_recovery(self):
        assert adjudicate(report()).reading.startswith("RECOVERY:")

    def test_diagnosis_incomplete_when_the_tags_do_not_recover(self):
        verdict = adjudicate(report(tags={"burden": 0.40, "mitigation": 0.443}))
        assert verdict.reading.startswith("DIAGNOSIS INCOMPLETE")
        assert "second cause" in verdict.reading

    def test_over_correction_when_the_controls_move_too(self):
        """The discriminator. Burden looks great; everything else rose with it."""
        verdict = adjudicate(report(tags={"ae": 0.5, "tx": 0.6, "proc": 0.5}))
        assert verdict.reading.startswith("OVER-CORRECTION")
        assert "controls moved with them" in verdict.reading

    def test_over_correction_when_a_tag_passes_its_ceiling(self):
        verdict = adjudicate(report(tags={"burden": 0.99}))
        assert "OVER-CORRECTION" in verdict.reading

    def test_a_collapse_outranks_an_overshoot(self):
        """One tag over its ceiling and another under its floor is still a
        falsified diagnosis: a tag that did not recover falsifies the claim
        whatever another tag did."""
        verdict = adjudicate(report(tags={"burden": 0.99, "mitigation": 0.40}))
        assert verdict.reading.startswith("DIAGNOSIS INCOMPLETE")

    def test_recovery_without_state_citation_is_not_recovery(self):
        """The purest over-correction signature: relabelled, not grounded."""
        verdict = adjudicate(report(state_coverage=0.1))
        assert verdict.reading.startswith("RECOVERY WITHOUT STATE CITATION")


class TestTheHoldsFromV2:
    def test_a_quarantined_take_is_counted(self):
        """A run can look clean because its failures went somewhere else."""
        clean = adjudicate(report(), quarantined=0)
        dirty = adjudicate(report(), quarantined=3)
        assert all(a.passed for a in clean.by_arm("holds_from_v2"))
        assert not all(a.passed for a in dirty.by_arm("holds_from_v2"))

    def test_an_inline_marker_regression_is_caught(self):
        verdict = adjudicate(report(inline_marker_takes=2))
        marker = next(a for a in verdict.by_arm("holds_from_v2")
                      if a.metric == "inline_marker_takes")
        assert not marker.passed

    def test_a_persona_that_never_feels_fails_its_floor(self):
        verdict = adjudicate(report(feeling_fraction=0.02))
        assert not next(a for a in verdict.by_arm("feeling_floor")).passed

    def test_graph_recall_being_cannibalised_is_caught(self):
        verdict = adjudicate(report(f_recall=0.2))
        arm = next(a for a in verdict.by_arm("f_recall_holds_independently"))
        assert not arm.passed
        assert "cannibalising" in arm.note


class TestCaveatsTravelWithTheNumbers:
    def test_the_comparability_break_is_always_stated(self):
        verdict = adjudicate(report())
        assert any("NOT comparable" in caveat for caveat in verdict.caveats)

    def test_a_thin_denominator_weakens_its_own_verdict(self):
        verdict = adjudicate(report(circumstantial_segments=3))
        assert any("very little" in caveat for caveat in verdict.caveats)

    def test_degeneracy_sends_the_reader_to_the_takes(self):
        verdict = adjudicate(report(single_segment_rate=0.7))
        assert any("read the raw takes" in caveat for caveat in verdict.caveats)

    def test_the_report_renders_without_a_verdict_being_implied(self):
        text = adjudicate(report()).report()
        assert "READING:" in text and "CAVEATS" in text


class TestReadingAnArchivedBundle:
    """The verdict is a read over the bundle, never a by-product of recording.

    A reader who doubts `adjudication.json` must be able to delete it and get the
    same file back without a model run — otherwise the verdict is something you
    have to take on trust from whoever happened to be at the keyboard.
    """

    def bundle(self, tmp_path, **overrides):
        from spp.narration.bundle import BundleManifest, write_bundle

        return write_bundle(
            "v0.4",
            BundleManifest(
                release="v0.4", backend="ollama", model="stub", prompt_version=3,
                battery_cases=30, accepted_takes=30,
            ),
            compliance={"report": report(**overrides).model_dump()},
            quarantine=[],
            sampled_takes=[{"case_id": "one"}],
            root=tmp_path,
        )

    def test_it_reproduces_the_verdict_from_the_archived_files(self, tmp_path):
        from spp.narration.adjudication import adjudicate_bundle

        directory = self.bundle(tmp_path)
        first = adjudicate_bundle(directory)
        written = json.loads((directory / "adjudication.json").read_text())

        (directory / "adjudication.json").unlink()
        assert adjudicate_bundle(directory).model_dump() == first.model_dump()
        assert written == first.model_dump()

    def test_quarantined_takes_reach_the_holds_from_v2_arm(self, tmp_path):
        """A run can look clean precisely because its failures went elsewhere.
        The count lives in quarantine.json, not in the report."""
        from spp.narration.adjudication import adjudicate_bundle
        from spp.narration.bundle import write_bundle, BundleManifest

        directory = write_bundle(
            "v0.4",
            BundleManifest(release="v0.4", backend="ollama", model="stub",
                           prompt_version=3),
            compliance={"report": report().model_dump()},
            quarantine=[{"failure_reason": "uncited claim"}],
            root=tmp_path,
        )
        arm = next(a for a in adjudicate_bundle(directory).by_arm("holds_from_v2")
                   if a.metric == "quarantine")
        assert arm.observed == 1.0 and not arm.passed

    def test_the_verdict_is_read_last(self, tmp_path):
        """Meeting the verdict before the raw takes would colour the reading of
        them, which is the whole point of the ordered protocol."""
        from spp.narration.adjudication import adjudicate_bundle

        directory = self.bundle(tmp_path)
        assert "adjudication.json" not in (directory / "README.md").read_text()

        adjudicate_bundle(directory)
        readme = (directory / "README.md").read_text()
        assert readme.index("compliance.json") < readme.index("adjudication.json")
        assert readme.index("takes/") < readme.index("adjudication.json")
