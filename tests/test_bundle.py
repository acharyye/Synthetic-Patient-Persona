"""The evidence bundle: the first live numbers, archived so they can be audited."""
import json

from spp.narration.bundle import BUNDLE_VERSION, BundleManifest, latest_bundle, write_bundle


def manifest(**overrides) -> BundleManifest:
    base = dict(
        release="v0.1", backend="ollama", model="qwen2.5:7b-instruct",
        model_digest="sha256:deadbeefcafe0123456789", prompt_version=1,
        sampling={"num_ctx": 8192, "temperature": 0.0, "seed": 42},
        battery_cases=30, accepted_takes=27, quarantined_takes=3,
        compliance_rate=0.9, canary_sensitive=True, bars_passed=True,
    )
    return BundleManifest(**{**base, **overrides})


class TestBundleContents:
    def test_it_archives_everything_needed_to_audit_the_run(self, tmp_path):
        bundle = write_bundle(
            "v0.1", manifest(), canary={"sensitive": True},
            compliance={"report": {}}, sampled_takes=[{"case_id": "a"}],
            quarantine=[{"failure_reason": "uncited claim"}], root=tmp_path,
        )
        names = {p.name for p in bundle.iterdir()}
        assert {"manifest.json", "canary.json", "compliance.json",
                "quarantine.json", "takes", "README.md"} <= names

    def test_the_manifest_pins_the_exact_configuration(self, tmp_path):
        bundle = write_bundle("v0.1", manifest(), root=tmp_path)
        payload = json.loads((bundle / "manifest.json").read_text())

        assert payload["model_digest"].startswith("sha256:")
        assert payload["prompt_version"] == 1
        assert payload["sampling"]["num_ctx"] == 8192
        assert payload["bundle_version"] == BUNDLE_VERSION

    def test_the_manifest_states_what_the_evidence_is_not(self, tmp_path):
        bundle = write_bundle("v0.1", manifest(), root=tmp_path)
        caveat = json.loads((bundle / "manifest.json").read_text())["caveat"]
        assert "not a validation of the model in general" in caveat

    def test_sampled_takes_are_archived_individually(self, tmp_path):
        bundle = write_bundle(
            "v0.1", manifest(),
            sampled_takes=[{"case_id": "one"}, {"case_id": "two"}], root=tmp_path)
        takes = sorted(p.name for p in (bundle / "takes").iterdir())
        assert len(takes) == 2
        assert "one" in takes[0] and "two" in takes[1]

    def test_the_readme_puts_the_canary_first(self, tmp_path):
        """The reading protocol, made durable — a bundle that let a later reader
        skip to the aggregates would defeat the protocol it records."""
        bundle = write_bundle("v0.1", manifest(), root=tmp_path)
        readme = (bundle / "README.md").read_text()

        assert readme.index("canary.json") < readme.index("compliance.json")
        assert "only reading does" in readme

    def test_bundles_are_discoverable_by_release(self, tmp_path):
        write_bundle("v0.1", manifest(), root=tmp_path)
        assert latest_bundle("v0.1", root=tmp_path) is not None
        assert latest_bundle("v9.9", root=tmp_path) is None


class TestLedgerVersioning:
    def test_the_bundle_records_which_ledger_it_was_written_against(self, tmp_path):
        """Assumption names are the ledger's keys and appear in every stamped
        report. Phase 5 namespacing renames them, which would orphan this
        bundle's references — the version travels so an alias table can be
        scoped to a release rather than guessed at."""
        from spp.foundation import LEDGER_SCHEMA_VERSION

        bundle = write_bundle("v0.1", manifest(), root=tmp_path)
        payload = json.loads((bundle / "manifest.json").read_text())
        assert payload["ledger_schema_version"] == LEDGER_SCHEMA_VERSION

    def test_the_ledger_snapshot_carries_it_too(self):
        from spp.foundation import LEDGER, LEDGER_SCHEMA_VERSION

        assert LEDGER.snapshot()["ledger_schema_version"] == LEDGER_SCHEMA_VERSION

    def test_the_readme_shows_it(self, tmp_path):
        bundle = write_bundle("v0.1", manifest(), root=tmp_path)
        assert "ledger schema" in (bundle / "README.md").read_text()
