"""Extract v4's audit slice — seed-chosen takes, exhaustive segments, text only.

    PYTHONPATH=src python scripts/extract_audit_slice.py --release v0.5

WHICH takes become the audit is decided by the RNG and stamped, not by anyone who
has seen an aggregate. The selection seed is committed before the record
completes; running this after the fact reproduces exactly the same slice, which is
what makes "we did not pick the flattering takes" checkable rather than asserted.

Extraction inside the chosen takes is EXHAUSTIVE — every segment of every take,
hash-shuffled, text only. That rule exists because a sheet filtered by anything
classifier-derived makes the resulting labels gold over the SHEET rather than over
the run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from spp.narration.cassette import load_cassette  # noqa: E402
from spp.narration.structured import parse_structured  # noqa: E402

# PRE-COMMITTED before the record completes. Changing either is its own commit.
SELECTION_SEED = 20260825
SLICE_TAKES = 15


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--name", default="narration_battery")
    parser.add_argument("--out", type=Path, default=Path("audit_slice.json"))
    args = parser.parse_args(argv)

    cassette = load_cassette(args.name)
    if cassette is None:
        parser.error(f"no cassette named {args.name!r}")

    # Sort by fingerprint so selection cannot depend on dict insertion order,
    # which is recording order, which is the battery's order.
    keys = sorted(cassette.takes)
    chosen = sorted(random.Random(SELECTION_SEED).sample(keys, min(SLICE_TAKES, len(keys))))

    segments: list[str] = []
    for key in chosen:
        answer = parse_structured(cassette.takes[key].response)
        for segment in (answer.segments if answer else []):
            text = " ".join(segment.text.split())
            if text:
                segments.append(text)

    unique = sorted(set(segments), key=lambda t: hashlib.sha256(t.encode()).hexdigest())
    args.out.write_text(json.dumps({
        "selection_seed": SELECTION_SEED,
        "slice_takes": len(chosen),
        "takes_available": len(keys),
        "prompt_version": cassette.prompt_version,
        "model": cassette.model,
        "segments_extracted": len(segments),
        "segments_unique": len(unique),
        "segments": unique,
    }, indent=1) + "\n", encoding="utf-8")

    print(f"seed {SELECTION_SEED} chose {len(chosen)} of {len(keys)} takes")
    print(f"{len(segments)} segments, {len(unique)} unique -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
