"""An environment flag that is EMPTY is one that is UNSET, not one that is false.

**Why.** `SPP_LIVE=` is what a shell user types when they mean `unset SPP_LIVE`.
Pydantic rejects an empty string for a `bool` outright, so one character in one
variable produced **33 collection errors** across the whole suite — a red run
that says nothing about the code and buries whatever the person was actually
checking. The audit found it; this file makes it mechanical rather than
remembered.

**The direction that matters.** Tolerating empty is safe because empty means
"offline", which is the default and the honest failure mode. Silently accepting a
real typo in the other direction is not: a live run that quietly reads as offline
produces stub prose and a believer. So `maybe` must still raise.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from spp.config import Settings

ROOT = Path(__file__).resolve().parents[1]


def _read(value: str | None) -> bool:
    """Construct Settings the way the process would, with SPP_LIVE set to `value`.

    Deliberately NOT `Settings(spp_live=value)`: a keyword argument bypasses the
    env-parsing path where the empty string actually arrives, so the test would
    pass against a mechanism the bug never travelled through.
    """
    import os

    saved = os.environ.get("SPP_LIVE")
    try:
        if value is None:
            os.environ.pop("SPP_LIVE", None)
        else:
            os.environ["SPP_LIVE"] = value
        return Settings(_env_file=None).spp_live
    finally:
        os.environ.pop("SPP_LIVE", None)
        if saved is not None:
            os.environ["SPP_LIVE"] = saved


class TestEmptyIsUnset:
    @pytest.mark.parametrize("blank", ["", "   ", "\t"])
    def test_a_blank_value_reads_as_offline(self, blank):
        assert _read(blank) is False

    def test_unset_still_reads_as_offline(self):
        assert _read(None) is False

    def test_the_documented_truthy_set_still_works(self):
        """Not a licence to widen the parser: these are pydantic's own values,
        asserted so this change cannot have narrowed them."""
        for truthy in ("true", "TRUE", "1", "on", "yes"):
            assert _read(truthy) is True, truthy
        for falsy in ("false", "FALSE", "0", "off", "no"):
            assert _read(falsy) is False, falsy

    def test_a_real_typo_still_raises(self):
        """The guard on the guard. If this passes because empty and garbage are
        both swallowed, the change went the wrong way."""
        with pytest.raises(Exception) as excinfo:
            _read("maybe")
        assert "spp_live" in str(excinfo.value)
        assert "boolean" in str(excinfo.value).lower()


class TestTheSuiteCollects:
    """The actual symptom: a red suite that means nothing. Checked in a subprocess
    because collection happens at import time, before any test can arrange it."""

    def test_an_empty_flag_does_not_break_collection(self):
        result = subprocess.run(
            [sys.executable, "-m", "pytest", "--co", "-q", "-p", "no:cacheprovider",
             "tests/test_config_env_flag.py"],
            cwd=ROOT, capture_output=True, text=True, timeout=180,
            env={"SPP_LIVE": "", "PYTHONPATH": "src", "PATH": str(ROOT / ".venv/bin"),
                 "HOME": str(Path.home())},
        )
        assert result.returncode == 0, result.stdout[-2000:] + result.stderr[-2000:]
        assert "error" not in result.stdout.lower().split("\n")[-2], result.stdout[-800:]
