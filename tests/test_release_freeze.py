"""The freeze rule, enforced rather than remembered.

It was prose until 2026-08-25, when a published v0.4 tag was amended and re-cut
locally on the strength of a report that it was unpushed. Nothing was
force-pushed and the rewrite was reverted, but the catch was a human reading an
`ahead/behind` line, not a mechanism. This is the mechanism.
"""
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "check_release_freeze.py"


def run(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-B", str(SCRIPT), *args, "--no-fetch"],
                          capture_output=True, text=True)


def has_remote() -> bool:
    return bool(subprocess.run(["git", "remote"], capture_output=True,
                               text=True).stdout.strip())


class TestItRefusesWhatIsPublished:
    @pytest.mark.skipif(not has_remote(), reason="no remote configured")
    def test_a_published_commit_is_refused(self):
        """Any commit reachable from a remote-tracking branch is frozen."""
        found = subprocess.run(["git", "rev-parse", "--verify", "origin/main"],
                               capture_output=True, text=True)
        if found.returncode != 0:
            pytest.skip("no remote-tracking branch fetched")
        rev = found.stdout.strip()

        result = run("--commit", rev)

        assert result.returncode == 2
        assert "REFUSED" in result.stdout
        assert "NOTE" in result.stdout, "the refusal must name the remedy"

    def test_an_unpublished_tag_is_cleared(self):
        result = run("--tag", "v99.99-does-not-exist")

        assert result.returncode == 0
        assert "clear" in result.stdout

    def test_naming_nothing_is_an_error(self):
        """Refusing on no input beats silently reporting 'clear'."""
        result = run()

        assert result.returncode != 0


class TestItFailsClosed:
    def test_an_unreachable_remote_refuses_rather_than_assumes(self):
        """The dangerous default is 'cannot check, therefore fine'."""
        result = run("--tag", "v0.4", "--remote", "no-such-remote-here")

        assert result.returncode != 0
        assert "clear" not in result.stdout
