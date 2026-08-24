"""Read an archived evidence bundle against the arms registered before it existed.

    PYTHONPATH=src python scripts/adjudicate_bundle.py evidence/v0.4/<timestamp>
    PYTHONPATH=src python scripts/adjudicate_bundle.py --release v0.4   # latest

Recording and reading are separate acts on purpose. The verdict is a pure
function of `compliance.json`, `quarantine.json` and
`tests/eval/v3_expected_shape.json`, so anyone who doubts the written
`adjudication.json` can delete it and reproduce it here without a model run.

The exit status reports which branch of the pre-registered tree was taken — 0
only for RECOVERY — so a shell cannot silently record a miss as a success. That
is a report, not a gate: an arm below its bound means investigate, and the one
thing it must never mean is editing the shape file in the same breath.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from spp.narration.adjudication import adjudicate_bundle  # noqa: E402
from spp.narration.bundle import latest_bundle  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", nargs="?", type=Path,
                        help="bundle directory; omit to use --release's latest")
    parser.add_argument("--release", default="v0.4",
                        help="release whose latest bundle to read (default: v0.4)")
    args = parser.parse_args(argv)

    directory = args.bundle or latest_bundle(args.release)
    if directory is None or not (directory / "compliance.json").exists():
        parser.error(f"no bundle with a compliance.json at {directory}")

    verdict = adjudicate_bundle(directory)
    print(f"bundle: {directory}\n")
    print(verdict.report())
    print(f"\nwritten: {directory / 'adjudication.json'}")
    return 0 if verdict.reading.startswith("RECOVERY:") else 1


if __name__ == "__main__":
    raise SystemExit(main())
