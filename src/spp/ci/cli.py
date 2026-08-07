"""`spp ci` — the command CI actually runs.

Host-agnostic on purpose. The GitHub Action is a thin adapter over these
subcommands; porting to GitLab later should mean writing a different YAML file,
not a different tool.

Exit codes: FAIL is 1, WARN and PASS are 0. A warning annotates without blocking,
because the gate refuses to fail on a delta it cannot distinguish from noise —
see `verdict._gate`.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .baseline import (
    IncompatibleBaseline,
    build_baseline,
    diff_summary,
    read_baseline,
    write_baseline,
)
from .render import render_annotations, render_markdown
from .scenario_file import ScenarioError, discover_scenarios, load_scenario
from .verdict import Gates, evaluate, write_verdict

DEFAULT_BASELINE = "ci/baseline.json"
DEFAULT_GATES = "ci/gates.json"


def _baseline_path(scenario_path: Path, explicit: str | None) -> Path:
    if explicit:
        return Path(explicit)
    # Convention: protocols/foo.json -> protocols/foo.baseline.json, so a repo
    # with several scenarios keeps each baseline beside its scenario.
    return scenario_path.with_suffix(".baseline.json")


def cmd_baseline(args: argparse.Namespace) -> int:
    scenario = load_scenario(args.scenario)
    path = _baseline_path(Path(args.scenario), args.baseline)

    previous = None
    if path.exists():
        try:
            previous = read_baseline(path)
        except IncompatibleBaseline as exc:
            print(f"[baseline] existing file unreadable, replacing: {exc}")

    fresh = build_baseline(scenario)

    # The golden-file reading rule: print what changed so an unexpected diff is
    # visible BEFORE it is committed.
    print(diff_summary(previous, fresh))

    if args.check:
        if previous is None:
            print("\nno committed baseline to check against")
            return 1
        drifted = (
            previous.scenario_hash != fresh.scenario_hash
            or previous.outcomes != fresh.outcomes
        )
        print("\nbaseline is stale" if drifted else "\nbaseline is current")
        return 1 if drifted else 0

    write_baseline(fresh, path)
    print(f"\nwrote {path}")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    scenario = load_scenario(args.scenario)
    path = _baseline_path(Path(args.scenario), args.baseline)

    try:
        baseline = read_baseline(path)
    except IncompatibleBaseline as exc:
        print(f"::error file={args.scenario}::{exc}")
        return 1

    gates = Gates.load(args.gates) if Path(args.gates).exists() else Gates()

    try:
        # Inside the guard: resolving the sign-stability control can itself
        # reject the baseline, and that must surface as an annotation rather
        # than a traceback.
        baseline_scenario = _baseline_scenario(scenario, baseline)
        verdict = evaluate(
            baseline, scenario, baseline_scenario, gates=gates,
            check_sign_stability=not args.no_sign_stability,
        )
    except IncompatibleBaseline as exc:
        print(f"::error file={args.scenario}::{exc}")
        return 1

    markdown = render_markdown(verdict)
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    write_verdict(verdict, out_dir / "verdict.json")
    (out_dir / "verdict.md").write_text(markdown, encoding="utf-8")

    for annotation in render_annotations(verdict, args.scenario):
        print(annotation)
    print(markdown)
    print(f"[ci] wrote {out_dir/'verdict.json'} and {out_dir/'verdict.md'}")
    return verdict.exit_code


def _baseline_scenario(candidate, baseline):
    """The design the baseline captured — the sign-stability control.

    Read from the baseline itself. There is deliberately NO fallback to the
    candidate: comparing a candidate against itself yields zero flips at every
    seed, which reports "not sign-stable", which downgrades every FAIL to WARN.
    A gate that can never fail is worse than no gate, so a baseline without a
    stored scenario is a hard error telling you to regenerate it.
    """
    from .scenario_file import ScenarioFile

    if not baseline.scenario:
        raise IncompatibleBaseline(
            f"baseline for {baseline.scenario_name!r} predates stored scenarios, so "
            "there is no control for the sign-stability run. Regenerate it with "
            "`spp ci baseline <scenario>` — without it every FAIL would silently "
            "downgrade to WARN."
        )
    return ScenarioFile.model_validate(baseline.scenario)


def cmd_list(args: argparse.Namespace) -> int:
    for path in discover_scenarios(args.root):
        try:
            scenario = load_scenario(path)
        except ScenarioError as exc:
            print(f"{path}\tINVALID\t{exc}")
            continue
        print(f"{path}\t{scenario.short_hash}\t{scenario.name}")
    return 0


def changed_scenarios(changed: list[str], root: str = "protocols") -> list[str]:
    """Filter a list of changed paths down to scenario files under `root`.

    Split out and unit-tested rather than tested through git — the plan is
    explicit that testing git itself is overkill.
    """
    prefix = f"{root.rstrip('/')}/"
    return sorted(
        path for path in changed
        if path.startswith(prefix)
        and path.endswith((".json", ".yaml", ".yml"))
        and not path.endswith(".baseline.json")
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="spp ci", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    baseline = sub.add_parser("baseline", help="write or check the pinned baseline")
    baseline.add_argument("scenario")
    baseline.add_argument("--baseline", default=None)
    baseline.add_argument("--check", action="store_true",
                          help="exit 1 if the committed baseline is stale; write nothing")
    baseline.set_defaults(func=cmd_baseline)

    check = sub.add_parser("check", help="gate a candidate against its baseline")
    check.add_argument("scenario")
    check.add_argument("--baseline", default=None)
    check.add_argument("--gates", default=DEFAULT_GATES)
    check.add_argument("--out", default="ci/out")
    check.add_argument("--no-sign-stability", action="store_true",
                       help="skip the second-seed run (faster; FAIL becomes unguarded)")
    check.set_defaults(func=cmd_check)

    listing = sub.add_parser("list", help="list scenario files and their hashes")
    listing.add_argument("--root", default="protocols")
    listing.set_defaults(func=cmd_list)

    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (ScenarioError, IncompatibleBaseline) as exc:
        # Never let a CI failure surface as a traceback: an unreadable error is
        # an error nobody acts on.
        print(f"::error::{exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
