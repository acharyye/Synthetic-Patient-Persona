"""Write a standalone report file. No server, no JavaScript, no network.

    PYTHONPATH=src python scripts/export_report.py counterfactual \
        --condition "type 2 diabetes" --seed 42 --n 200 \
        --baseline-visits 24 --variant-visits 12 --out heavy-vs-light.html

    PYTHONPATH=src python scripts/export_report.py comparison \
        --condition COPD --left-seed 42 --right-seed 7 --n 300 --out drift.html

This is the piece that makes a result leave the room without its author. The
renderer already produced a self-contained page; until now the only way to obtain
one was to run the API and POST to it, which means the artifact could not be
emailed, attached to a ticket, or opened by someone who was not there.

Everything it writes is a pure read over a computed artifact. The page carries its
own reading protocol, its own seeds and the full assumption ledger, because a
document that travels has to answer "should I believe this" without anyone
present to be asked.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from spp.report import (  # noqa: E402
    compare_cohorts,
    render_bundle,
    render_comparison,
    render_counterfactual,
    render_verdict,
)


def _counterfactual(args: argparse.Namespace) -> str:
    from spp.api.main import CounterfactualRequest, counterfactual
    from spp.protocol import ProtocolBurden

    burden = ProtocolBurden(visits_per_year=args.visits_per_year,
                            daily_diary=args.daily_diary)
    report = counterfactual(CounterfactualRequest(
        condition=args.condition, n=args.n, seed=args.seed,
        duration_days=args.duration_days, burden=burden,
        inclusion=args.inclusion, exclusion=args.exclusion,
        drop_visits=args.drop_visits, remote_visits=args.remote_visits,
    ))
    return render_counterfactual(report)


def _comparison(args: argparse.Namespace) -> str:
    comparison = compare_cohorts(
        args.condition, left_seed=args.left_seed, right_seed=args.right_seed, n=args.n
    )
    payload = comparison.model_dump(mode="json")
    payload["headline"] = comparison.headline()
    return render_comparison(payload)


def _verdict(args: argparse.Namespace) -> str:
    import json

    return render_verdict(json.loads(args.verdict.read_text(encoding="utf-8")))


def _bundle(args: argparse.Namespace) -> str:
    """Read a bundle directory. Missing parts render as missing, never as absent.

    A bundle that was never adjudicated must say so on the page rather than
    quietly omit the section — the reader cannot tell those apart, and one of them
    means the verdict does not exist yet.
    """
    import json

    def load(name: str) -> dict:
        path = args.bundle / name
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}

    adjudication = load("adjudication_v4.json") or load("adjudication.json")
    return render_bundle({
        "manifest": load("manifest.json"),
        "compliance": load("compliance.json"),
        "adjudication": adjudication,
    })


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="kind", required=True)

    cf = sub.add_parser("counterfactual", help="one design change, CRN-paired")
    cf.add_argument("--condition", required=True)
    cf.add_argument("--n", type=int, default=200)
    cf.add_argument("--seed", type=int, default=42)
    cf.add_argument("--duration-days", type=int, default=365)
    cf.add_argument("--visits-per-year", type=int, default=24)
    cf.add_argument("--daily-diary", action="store_true")
    cf.add_argument("--inclusion", nargs="*", default=[])
    cf.add_argument("--exclusion", nargs="*", default=[])
    # The design change. Visit ids are v001..vNNN over the schedule the burden
    # builds — the API rejects an id the schedule does not contain, which is the
    # right place for that check to live.
    cf.add_argument("--drop-visits", nargs="*", default=[],
                    help="e.g. v003 v004 — the visits this design removes")
    cf.add_argument("--remote-visits", nargs="*", default=[],
                    help="e.g. v005 v006 — the visits this design makes remote")
    cf.set_defaults(func=_counterfactual)

    cp = sub.add_parser("comparison", help="two cohorts, distributional across seeds")
    cp.add_argument("--condition", required=True)
    cp.add_argument("--n", type=int, default=300)
    cp.add_argument("--left-seed", type=int, default=42)
    cp.add_argument("--right-seed", type=int, default=7)
    cp.set_defaults(func=_comparison)

    vd = sub.add_parser("verdict", help="a protocol-CI verdict JSON")
    vd.add_argument("--verdict", type=Path, required=True)
    vd.set_defaults(func=_verdict)

    bd = sub.add_parser("bundle", help="an evidence bundle directory")
    bd.add_argument("--bundle", type=Path, required=True)
    bd.set_defaults(func=_bundle)

    for p in (cf, cp, vd, bd):
        p.add_argument("--out", type=Path, required=True)

    args = parser.parse_args(argv)
    page = args.func(args)
    args.out.write_text(page, encoding="utf-8")

    # A file:// page that reaches for the network is a page that breaks in the
    # meeting it was written for. Asserted rather than trusted.
    for forbidden in ("http://", "https://", "<script", "src="):
        if forbidden in page:
            print(f"REFUSED: rendered page contains {forbidden!r} — it must be "
                  "self-contained and open from file:// with no network.")
            return 2

    print(f"wrote {args.out} ({len(page):,} bytes, self-contained)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
