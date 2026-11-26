"""Print the Synthea-vs-prior table for one condition. Writes nothing.

    PYTHONPATH=src python scripts/derive_synthea_marginals.py \
        --export data/synthea/structural_seed11 --condition "type 2 diabetes"

The table is the artifact `diff_before_adopt` requires: it is read before any
value is adopted, and adoption may be declined per entry. An export whose
MANIFEST declares a structural run prints the same table marked FEEDS NO TARGET.

Exit status: 0 when the table may feed targets, 3 when it may not — so a shell
that pipes this into an adoption step cannot do it from a structural run.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from spp.cohort.packs import pack_for  # noqa: E402
from spp.ingest.synthea_derive import derive  # noqa: E402
from spp.ingest.synthea_loader import load_synthea  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--export", type=Path, required=True, help="Synthea CSV export directory")
    parser.add_argument("--condition", required=True)
    args = parser.parse_args(argv)

    pack = pack_for(args.condition)
    if pack is None:
        parser.error(f"no prior pack for {args.condition!r}")

    load = load_synthea(args.export)
    print(load.report.headline())
    print()
    table = derive(load, pack)
    print(table.render())
    return 0 if table.feeds_targets else 3


if __name__ == "__main__":
    raise SystemExit(main())
