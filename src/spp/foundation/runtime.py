"""What environment produced an artifact, and which differences matter.

The promise is that results are a function of seeds and declared assumptions.
This session established that the *environment* is the third term and that it
had been travelling undeclared: an undeclared `networkx` that existed only on
one machine, and CPython 3.12's switch to Neumaier summation in `sum()`, which
moved a golden with no code change and identical draws.

So every artifact stamps its environment. Enforcement is **tiered**, because
severity should scale to what the evidence can actually distinguish — the same
rule that makes Protocol CI's FAIL require sign-stability:

`lock_hash` — **refuse** on mismatch.
    Different resolved artifacts mean the environment is not the declared one,
    and nothing vouches for an undeclared environment. This is the strict tier
    because it is the one whose blast radius is unbounded: a different numpy is
    a different implementation of the arithmetic underneath the simulation.

`python_version` inside the supported range — **warn**.
    An earlier design refused here. That was written when draws might differ
    across interpreters; they demonstrably do not. Per-persona values are
    identical, goldens are byte-identical on 3.11 and 3.13, and the CI matrix
    re-establishes that on every push. Refusing would assert a danger the system
    does not have. The warning is honest precisely because the matrix is
    standing evidence, so it says so.

`python_version` outside the supported range — **refuse**.
    No matrix leg covers it, so there is no evidence to appeal to.

The tiering is only defensible while the matrix keeps running. If the goldens
are ever removed from the per-interpreter legs, the warn tier loses its backing
and must go back to refusing.
"""
from __future__ import annotations

import hashlib
import sys
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, Field

# Mirrors `requires-python` in pyproject.toml and the CI matrix. Kept as a tuple
# of (major, minor) so comparison is ordering rather than string matching.
MIN_SUPPORTED_PYTHON = (3, 11)

LOCK_FILENAME = "uv.lock"


class EnvironmentMismatch(RuntimeError):
    """The artifact was produced in an environment nothing vouches for."""


@lru_cache(maxsize=1)
def _lock_hash() -> str:
    """sha256 of uv.lock, or "unlocked" when there is no lock to read.

    Absence is recorded rather than raising: the library has to work from a
    source checkout, a wheel, or a vendored copy. An artifact stamped
    "unlocked" is honest about knowing less, and compares equal only to another
    unlocked one.
    """
    here = Path(__file__).resolve()
    for parent in here.parents:
        candidate = parent / LOCK_FILENAME
        if candidate.is_file():
            return hashlib.sha256(candidate.read_bytes()).hexdigest()[:16]
    return "unlocked"


def _numpy_version() -> str:
    try:
        import numpy
    except ImportError:  # pragma: no cover - numpy is a hard dependency
        return "absent"
    return numpy.__version__


class RuntimeStamp(BaseModel):
    """The environment an artifact was produced in."""

    python_version: str = Field(default_factory=lambda: ".".join(map(str, sys.version_info[:3])))
    numpy_version: str = Field(default_factory=_numpy_version)
    lock_hash: str = Field(default_factory=_lock_hash)

    @property
    def python_minor(self) -> tuple[int, int]:
        major, _, rest = self.python_version.partition(".")
        minor, _, _ = rest.partition(".")
        return (int(major), int(minor))

    def describe(self) -> str:
        return (
            f"python={self.python_version} numpy={self.numpy_version} "
            f"lock={self.lock_hash}"
        )

    def check_against(self, other: RuntimeStamp) -> list[str]:
        """Refuse on what nothing vouches for; warn on what CI covers.

        Returns the warnings. Raises `EnvironmentMismatch` for the strict tier,
        so a caller that ignores the return value still cannot proceed on an
        undeclared environment.
        """
        if self.lock_hash != other.lock_hash:
            raise EnvironmentMismatch(
                f"dependency lock differs: {self.lock_hash} vs {other.lock_hash}.\n"
                "Different resolved artifacts are a different environment, and no "
                "CI leg vouches for an undeclared one. Install from the committed "
                "requirements.txt (`pip install -r requirements.txt`) or regenerate "
                "the artifact."
            )

        for stamp in (self, other):
            if stamp.python_minor < MIN_SUPPORTED_PYTHON:
                supported = ".".join(map(str, MIN_SUPPORTED_PYTHON))
                raise EnvironmentMismatch(
                    f"python {stamp.python_version} is below the supported floor "
                    f"({supported}). No CI leg covers it, so there is no evidence "
                    "that results here are comparable."
                )

        if self.python_version != other.python_version:
            return [
                f"interpreters differ ({self.python_version} vs {other.python_version}); "
                "cross-version reproducibility is CI-enforced — the test matrix runs "
                "the byte-exact goldens on every supported interpreter"
            ]
        if self.numpy_version != other.numpy_version:
            # Reachable, and not exotic: it means an installed environment has
            # drifted from the lock that names it — the usual cause being a venv
            # created before the last `uv lock` and never re-synced. Caught this
            # exact case on the machine that wrote the first stamped baseline.
            return [
                f"numpy differs ({self.numpy_version} vs {other.numpy_version}) "
                "under an identical lock hash — an installed environment has "
                "drifted from uv.lock. Re-sync with "
                "`pip install -r requirements.txt`"
            ]
        return []
