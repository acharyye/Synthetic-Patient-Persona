"""`verdict.md` — the PR comment. This is the entire UI for Protocol CI.

A reviewer reads this in a diff view, with thirty seconds of attention, so it
leads with the decision and the number of *people* affected. The flip count sits
above the percentage deliberately: paired runs make "7 personas flipped" exact,
while a retention delta invites reading as a difference of two aggregates. The
one-liner under the count says so, exactly as the HTML report does.

Config stamps go at the bottom rather than the top — present for anyone who
needs to reproduce the run, out of the way of the decision.
"""
from __future__ import annotations

from .verdict import Verdict

_BADGE = {
    "PASS": "✅ **PASS**",
    "WARN": "⚠️ **WARN**",
    "FAIL": "❌ **FAIL**",
}

# Marker so CI can find and update its own comment in place rather than posting
# a new one on every push.
COMMENT_MARKER = "<!-- spp-protocol-ci -->"


def render_markdown(verdict: Verdict, max_flips: int = 8) -> str:
    lines: list[str] = [COMMENT_MARKER, ""]
    lines.append(f"### {_BADGE[verdict.outcome]} — Protocol CI: `{verdict.scenario_name}`")
    lines.append("")
    lines.append(verdict.reason)
    lines.append("")

    # Headline: people first, percentage second.
    net = verdict.net_flips
    lines.append(
        f"**{len(verdict.lost)} personas lost, {len(verdict.recovered)} recovered "
        f"({net:+d} net)** · retention "
        f"{verdict.baseline_retention:.1%} → {verdict.candidate_retention:.1%} "
        f"({verdict.retention_delta_pp:+.2f}pp)"
    )
    lines.append("")
    lines.append(
        "> Baseline and candidate run under identical seeds, so these are exact "
        "per-persona flips — not a difference of two aggregates."
    )
    lines.append("")
    lines.append(f"Sign stability: {verdict.sign_stability.describe()}")
    lines.append("")

    # Environment differences the matrix vouches for. Surfaced rather than
    # refused, and never as an error badge — a reader who sees red for something
    # CI proves is safe learns to ignore red.
    for warning in verdict.environment_warnings:
        lines.append(f"> ⚠️ {warning}")
        lines.append("")

    flips = [*verdict.lost, *verdict.recovered]
    if flips:
        lines.append("#### Who moved")
        lines.append("")
        lines.append("| persona | change | exit reason |")
        lines.append("|---|---|---|")
        for row in flips[:max_flips]:
            reason = row.variant_exit_reason or row.baseline_exit_reason or "—"
            lines.append(f"| `{row.patient_id}` | {row.direction} | {reason} |")
        if len(flips) > max_flips:
            lines.append(f"| … | _{len(flips) - max_flips} more in `verdict.json`_ | |")
        lines.append("")
    else:
        lines.append("_No persona changed outcome._")
        lines.append("")

    moved = [d for d in verdict.attribution_deltas if abs(d.share_delta) > 1e-9]
    if moved:
        lines.append("#### Which rule is responsible")
        lines.append("")
        lines.append("| criterion | share of exclusions | sole-reason |")
        lines.append("|---|---|---|")
        for delta in moved[:6]:
            marker = " _(new)_" if delta.is_new else ""
            lines.append(
                f"| `{delta.criterion}`{marker} | "
                f"{delta.baseline_share:.1%} → {delta.candidate_share:.1%} "
                f"({delta.share_delta * 100:+.1f}pp) | "
                f"{delta.baseline_sole_reason} → {delta.candidate_sole_reason} |"
            )
        lines.append("")
        lines.append(
            "_Shapley share of the exclusion veto game — exact, not sampled. "
            "Sole-reason counts personas who would have qualified but for that "
            "one line._"
        )
        lines.append("")

    lines.append("<details><summary>Configuration</summary>")
    lines.append("")
    lines.append("```")
    lines.append(f"scenario   {verdict.candidate_hash[:12]} (baseline {verdict.baseline_hash[:12]})")
    lines.append(f"population {verdict.config.describe()}")
    lines.append(f"ledger     v{verdict.config.ledger_schema_version}, "
                 f"{verdict.ledger.get('count', 0)} assumptions")
    lines.append(f"gates      fail at {verdict.gates.retention_drop_pp.get('fail')}pp, "
                 f"warn at {verdict.gates.retention_drop_pp.get('warn')}pp, "
                 f"sign-stability required for fail: "
                 f"{verdict.gates.require_sign_stability_for_fail}")
    lines.append(f"generated  {verdict.generated_at}")
    lines.append("```")
    lines.append("")
    lines.append(
        "Thresholds are pre-registered in `ci/gates.json`. Simulated under "
        "stated assumptions — a retention *level* is an assumption, the "
        "*difference* between two designs is the signal."
    )
    lines.append("</details>")
    return "\n".join(lines) + "\n"


def render_annotations(verdict: Verdict, scenario_path: str) -> list[str]:
    """GitHub workflow-command annotations pointing at the scenario file."""
    level = {"FAIL": "error", "WARN": "warning", "PASS": "notice"}[verdict.outcome]
    title = f"Protocol CI {verdict.outcome}"
    message = verdict.reason.replace("\n", " ")
    return [f"::{level} file={scenario_path},title={title}::{message}"]
