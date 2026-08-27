"""Server-rendered HTML report over a completed run.

First piece of the product surface, and deliberately the dumbest: **pure reads
over artifacts the API already returns.** Nothing here computes a number. If a
figure cannot be rendered, that is an artifact gap to fix upstream — which is the
point of building this before the SPA depends on those artifacts.

Design rule inherited from the roadmap: **provenance is the aesthetic.** Seeds,
prompt and model versions, ledger confidence tags and the unquotable list are
rendered as first-class page furniture, not buried in a tooltip. Every headline
number sits next to what produced it. That is the visible form of everything the
foundation, calibration and narration layers were built to guarantee, and it is
the reason a design reviewer should believe any of it.

No JavaScript, no build step, no external assets — this must render from a file://
URL in a meeting where the wifi has failed.
"""
from __future__ import annotations

import html
from typing import Any

from ..foundation.ledger import LEDGER

STYLE = """
:root {
  --ink:#12161c; --muted:#5b6572; --line:#dfe4ea; --bg:#fbfcfd; --panel:#fff;
  --good:#0f7b4f; --bad:#b3261e; --warn:#8a5a00; --accent:#1c4f8f;
}
* { box-sizing:border-box; }
body {
  margin:0; background:var(--bg); color:var(--ink);
  font:15px/1.55 ui-sans-serif,-apple-system,"Segoe UI",Roboto,sans-serif;
}
.wrap { max-width:1080px; margin:0 auto; padding:32px 24px 80px; }
header { border-bottom:2px solid var(--ink); padding-bottom:16px; margin-bottom:8px; }
h1 { font-size:26px; margin:0 0 4px; letter-spacing:-0.01em; }
h2 { font-size:15px; text-transform:uppercase; letter-spacing:.08em;
     color:var(--muted); margin:36px 0 12px; font-weight:600; }
.sub { color:var(--muted); margin:0; }
.stamp { display:flex; flex-wrap:wrap; gap:6px; margin:14px 0 0; }
.chip { font:12px/1 ui-monospace,SFMono-Regular,Menlo,monospace; background:var(--panel);
        border:1px solid var(--line); border-radius:999px; padding:6px 10px; color:var(--muted); }
.chip b { color:var(--ink); font-weight:600; }
.headline { background:var(--panel); border:1px solid var(--line); border-left:4px solid var(--accent);
            padding:18px 20px; margin:20px 0; }
.headline .big { font-size:30px; font-weight:650; letter-spacing:-0.02em; }
.grid { display:grid; grid-template-columns:repeat(auto-fit,minmax(160px,1fr)); gap:12px; }
.stat { background:var(--panel); border:1px solid var(--line); padding:14px 16px; }
.stat .v { font-size:22px; font-weight:650; }
.stat .k { font-size:12px; color:var(--muted); text-transform:uppercase; letter-spacing:.05em; }
table { width:100%; border-collapse:collapse; background:var(--panel);
        border:1px solid var(--line); font-size:14px; }
th,td { text-align:left; padding:9px 12px; border-bottom:1px solid var(--line); }
th { font-size:12px; text-transform:uppercase; letter-spacing:.05em; color:var(--muted); }
td.num,th.num { text-align:right; font-variant-numeric:tabular-nums; }
tr:last-child td { border-bottom:none; }
.bar { height:8px; background:var(--accent); border-radius:2px; display:inline-block; }
.curve { display:flex; align-items:flex-end; gap:2px; height:120px;
         background:var(--panel); border:1px solid var(--line); padding:10px; }
.curve div { flex:1; background:var(--accent); min-height:1px; }
.curve div.v { background:var(--good); }
.good { color:var(--good); } .bad { color:var(--bad); } .warn { color:var(--warn); }
code,.mono { font:12px/1.5 ui-monospace,SFMono-Regular,Menlo,monospace; }
.caveat { background:#fff8e6; border:1px solid #e8d9a8; border-left:4px solid var(--warn);
          padding:14px 18px; margin:24px 0; font-size:14px; }
footer { margin-top:48px; padding-top:16px; border-top:1px solid var(--line);
         color:var(--muted); font-size:13px; }
"""


def esc(value: Any) -> str:
    return html.escape(str(value), quote=True)


def _chip(label: str, value: Any) -> str:
    return f'<span class="chip">{esc(label)} <b>{esc(value)}</b></span>'


def _stat(key: str, value: Any) -> str:
    return f'<div class="stat"><div class="v">{esc(value)}</div><div class="k">{esc(key)}</div></div>'


def _curve(points: list[dict], key: str = "retention", variant: bool = False) -> str:
    if not points:
        return ""
    bars = "".join(
        f'<div class="{"v" if variant else ""}" style="height:{max(1, round(p[key] * 100))}%" '
        f'title="day {p["day"]}: {p[key]:.1%}"></div>'
        for p in points
    )
    return f'<div class="curve">{bars}</div>'


def _ledger_section() -> str:
    """The assumption ledger, rendered rather than linked.

    Deliberately not collapsed: a reader who does not go looking should still see
    how much of this is judgement. `unquotable` is the machine-readable set whose
    outputs must never be quoted as findings.
    """
    rows = "".join(
        f"<tr><td class='mono'>{esc(a.name)}</td>"
        f"<td>{esc(a.confidence.value)}</td>"
        f"<td>{'<span class=bad>never quote</span>' if not a.quotable else '<span class=good>quotable</span>'}</td>"
        f"<td>{esc(a.source[:150])}{'…' if len(a.source) > 150 else ''}</td></tr>"
        for a in LEDGER
    )
    unquotable = len(LEDGER.unsupported())
    return (
        f"<h2>Assumption ledger — {len(LEDGER)} entries, "
        f"<span class='bad'>{unquotable} not quotable</span></h2>"
        "<table><tr><th>assumption</th><th>confidence</th><th>status</th>"
        f"<th>source</th></tr>{rows}</table>"
    )


def render_counterfactual(report: dict) -> str:
    """Render a `/counterfactual/run` artifact. Reads only; computes nothing."""
    provenance = report.get("provenance", {})
    stability = report.get("sign_stability") or {}
    attribution = report.get("eligibility_attribution") or {}

    net = report.get("net_flips", 0)
    direction = "recovered" if net > 0 else ("lost" if net < 0 else "no change")
    tone = "good" if net > 0 else ("bad" if net < 0 else "")

    stamp = "".join([
        _chip("seed", provenance.get("master_seed")),
        _chip("condition", provenance.get("condition")),
        _chip("cohort", provenance.get("cohort_size")),
        _chip("visits", provenance.get("schedule_visits")),
        _chip("days", provenance.get("duration_days")),
        _chip("artifact", f"v{provenance.get('artifact_version')}"),
        _chip("generated", provenance.get("generated_at", "")),
    ])

    flips = "".join(
        f"<tr><td class='mono'>{esc(f['patient_id'])}</td>"
        f"<td>{esc(f['baseline'])} &rarr; {esc(f['variant'])}</td>"
        f"<td>{esc(f.get('baseline_exit_reason') or '—')}</td>"
        f"<td class='num'>day {esc(f.get('diverged_at_day'))}</td></tr>"
        for f in [*report.get("example_recovered", []), *report.get("example_lost", [])]
    ) or "<tr><td colspan=4>no outcome changed</td></tr>"

    rules = "".join(
        f"<tr><td class='mono'>{esc(r['criterion'])}</td><td>{esc(r['kind'])}</td>"
        f"<td class='num'>{r['shapley']:.1f}</td>"
        f"<td class='num'>{r['shapley_share']:.1%}</td>"
        f"<td><span class='bar' style='width:{max(2, round(r['shapley_share'] * 160))}px'></span></td></tr>"
        for r in attribution.get("rules", [])
    )

    burden = "".join(
        f"<tr><td>{esc(k)}</td><td class='num {'good' if v < 0 else 'bad' if v > 0 else ''}'>"
        f"{v:+.4f}</td></tr>"
        for k, v in sorted(report.get("burden_shift", {}).items(),
                           key=lambda kv: kv[1])
    )

    stability_line = ""
    if stability:
        stable = stability.get("sign_stable")
        stability_line = (
            f"<div class='caveat'><b>Sign stability:</b> net flips "
            f"{esc(stability.get('net_flips'))} across seeds "
            f"{esc(stability.get('seeds'))} — "
            f"<span class='{'good' if stable else 'bad'}'>{esc(stability.get('verdict'))}</span>."
            "</div>"
        )

    return f"""<!doctype html><meta charset="utf-8">
<title>{esc(report.get('title', 'Counterfactual'))}</title>
<style>{STYLE}</style>
<div class="wrap">
<header>
  <h1>{esc(report.get("title", "Counterfactual run"))}</h1>
  <p class="sub">Design change: <b>{esc(report.get("change", ""))}</b></p>
  <div class="stamp">{stamp}</div>
</header>

{_reading_protocol()}

<div class="headline">
  <div class="big {tone}">{net:+d} net personas {esc(direction)}</div>
  <div class="sub">+{report.get('recovered', 0)} recovered, &minus;{report.get('lost', 0)} lost,
  {report.get('perturbed', 0)} perturbed without changing outcome,
  {report.get('unchanged', 0)} untouched &nbsp;·&nbsp;
  retention {report.get('baseline_retention', 0):.1%} &rarr; {report.get('variant_retention', 0):.1%}</div>
</div>

<p class="sub">Runs are paired per persona under common random numbers, so these are
<b>exact flips</b>, not a difference of two aggregates. Read the flip count; the
curves are the picture, not the number.</p>

{stability_line}

<h2>Survival — baseline vs variant</h2>
{_curve(report.get("baseline_curve", []))}
{_curve(report.get("variant_curve", []), variant=True)}

<h2>Who changed, and where their trajectories diverged</h2>
<table><tr><th>persona</th><th>outcome</th><th>baseline exit reason</th>
<th class="num">diverged</th></tr>{flips}</table>

<h2>Burden shift by component</h2>
<table><tr><th>component</th><th class="num">change</th></tr>{burden}</table>

<h2>Eligibility attribution — exact Shapley</h2>
<p class="sub">{esc(attribution.get("headline", ""))}
<br><span class="mono">{esc(attribution.get("method", ""))}</span></p>
<table><tr><th>criterion</th><th>kind</th><th class="num">shapley</th>
<th class="num">share</th><th></th></tr>{rules}</table>

{_ledger_section()}

<div class="caveat">{esc(report.get("disclaimer", ""))}</div>

<footer>Seeds, versions and the full assumption ledger are rendered above because
they are part of the result, not metadata about it. Every figure on this page is a
read over the run artifact — nothing was recomputed for display.</footer>
</div>"""


READING_PROTOCOL = [
    ("provenance", "Seed, condition, cohort size and versions. If these do not "
                   "match the run you were told about, stop here."),
    ("what changed", "The flip table. Which named personas changed outcome and at "
                     "which event their trajectories diverged."),
    ("by how much", "Curves and component shifts — the visual, not the number."),
    ("why", "Attribution. Exact Shapley over the rules that excluded people."),
    ("how much is judgement", "The assumption ledger, and the entries whose "
                              "outputs must never be quoted as findings."),
]


def _reading_protocol() -> str:
    """An ordered protocol, rendered on the page rather than assumed of the reader.

    The evidence bundles have carried one since v0.1 for a reason: a reader who
    meets the headline first reads everything after it looking for confirmation.
    This page is the artifact that leaves the room without its author, so the
    order it should be read in has to travel with it.
    """
    items = "".join(
        f"<li><b>{esc(label)}</b> — {esc(text)}</li>"
        for label, text in READING_PROTOCOL
    )
    return (
        '<div class="protocol"><h2 style="margin-top:0">Read in this order</h2>'
        f"<ol>{items}</ol>"
        "<p class='sub'>Nothing on this page was computed for display. Every "
        "figure is a read over a stored run artifact, and the seeds above "
        "reproduce it exactly.</p></div>"
    )


def render_comparison(comparison: dict) -> str:
    """Render a `CohortComparison` artifact as a standalone page.

    **The identity/distributional invariant is enforced at the renderer, not only
    upstream.** Within a run, common random numbers make persona `i` on each side
    the same persona, so a per-persona delta is signal. Across seeds it is a delta
    between exchangeable strangers, and rendering that in the flip table's visual
    language would lend sampling noise the authority that table earned. So a
    distributional comparison emits **no persona rows here**, whatever it was
    handed — a second enforcement point, because this is the artifact that travels
    without anyone present to explain the distinction.
    """
    mode = comparison.get("mode", "distributional")
    identity = mode == "identity"
    marginals = comparison.get("marginals") or []
    changes = comparison.get("persona_changes") or [] if identity else []

    stamp = "".join([
        _chip("left", comparison.get("left")),
        _chip("right", comparison.get("right")),
        _chip("mode", mode),
        _chip("n", comparison.get("n")),
    ])

    drifted = [m for m in marginals if m.get("notable")]
    rows = "".join(
        f"<tr><td class='mono'>{esc(m.get('field'))}</td>"
        f"<td class='num'>{esc(m.get('left_value'))}</td>"
        f"<td class='num'>{esc(m.get('right_value'))}</td>"
        f"<td class='num'>{esc(m.get('tolerance'))}</td>"
        f"<td>{'<span class=bad>outside band</span>' if m.get('notable') else '<span class=good>within band</span>'}</td>"
        f"</tr>"
        for m in marginals
    ) or "<tr><td colspan=5>no marginals compared</td></tr>"

    if identity:
        persona_rows = "".join(
            f"<tr><td class='mono'>{esc(c.get('patient_id'))}</td>"
            f"<td>{esc(c.get('field'))}</td>"
            f"<td>{esc(c.get('left'))} &rarr; {esc(c.get('right'))}</td></tr>"
            for c in changes
        ) or "<tr><td colspan=3>no persona changed</td></tr>"
        persona_block = (
            "<h2>Who changed — paired by identity, so these deltas are signal</h2>"
            "<table><tr><th>persona</th><th>field</th><th>change</th></tr>"
            f"{persona_rows}</table>"
        )
    else:
        persona_block = (
            "<h2>Per-persona rows — deliberately absent</h2>"
            "<p class='sub'>This is a <b>distributional</b> comparison across "
            "seeds. Persona <i>i</i> on each side is an independent draw, so a "
            "per-pair delta is a difference between exchangeable strangers. "
            "Rendering it here would lend sampling noise the authority the paired "
            "flip table earned, so no rows are emitted.</p>"
        )

    return f"""<!doctype html><meta charset="utf-8">
<title>Cohort comparison — {esc(comparison.get("left"))} vs {esc(comparison.get("right"))}</title>
<style>{STYLE}</style>
<div class="wrap">
<header>
  <h1>Cohort comparison</h1>
  <p class="sub">{esc(comparison.get("headline", ""))}</p>
  <div class="stamp">{stamp}</div>
</header>

{_reading_protocol()}

<h2>Marginals against pack targets — {len(drifted)} of {len(marginals)} outside band</h2>
<p class="sub">Tolerances are read from each pack entry's own <span class="mono">tolerance</span>
field. They are not transcribed here, so this table and the contract suite cannot disagree.</p>
<table><tr><th>field</th><th class="num">left</th><th class="num">right</th>
<th class="num">tolerance</th><th></th></tr>{rows}</table>

{persona_block}

<p class="sub">{esc(comparison.get("note", ""))}</p>

{_ledger_section()}

<footer>Nothing on this page was recomputed for display. The comparison mode is
part of the result: identity pairing is exact, cross-seed pairing does not exist.</footer>
</div>"""


def render_verdict(verdict: dict) -> str:
    """Render a protocol-CI `Verdict` as a standalone page.

    **The downgrade is rendered, not resolved.** A FAIL requires the drop to
    exceed its gate AND to be sign-stable across two master seeds; a drop that
    flips direction when the population is redrawn is below the paired design's
    resolution and becomes a WARN. That rule is the gate refusing to assert what
    its own method cannot distinguish, and a page showing only the final word
    would hide the most defensible thing about it. So the sign-stability line sits
    next to the outcome, with the per-seed net flips visible.
    """
    outcome = str(verdict.get("outcome", "")).upper()
    tone = {"PASS": "good", "FAIL": "bad", "WARN": "warn"}.get(outcome, "")
    stability = verdict.get("sign_stability") or {}
    config = verdict.get("config") or {}
    recovered = verdict.get("recovered") or []
    lost = verdict.get("lost") or []
    warnings = verdict.get("environment_warnings") or []

    stamp = "".join([
        _chip("scenario", verdict.get("scenario_name")),
        _chip("condition", config.get("condition")),
        _chip("pack", f"{config.get('pack_id')}@{config.get('pack_version')}"),
        _chip("seed", config.get("cohort_seed")),
        _chip("cohort", config.get("cohort_size")),
        _chip("engine", f"v{config.get('engine_version')}"),
        _chip("baseline", str(verdict.get("baseline_hash", ""))[:12]),
        _chip("candidate", str(verdict.get("candidate_hash", ""))[:12]),
    ])

    seeds = stability.get("seeds") or []
    nets = stability.get("net_flips") or []
    stable = stability.get("stable")
    stability_rows = "".join(
        f"<tr><td class='mono'>{esc(s)}</td><td class='num'>{esc(n):}</td></tr>"
        for s, n in zip(seeds, nets)
    ) or "<tr><td colspan=2>not re-run</td></tr>"

    flips = "".join(
        f"<tr><td class='mono'>{esc(f.get('patient_id'))}</td>"
        f"<td>{esc(f.get('direction'))}</td>"
        f"<td>{esc(f.get('baseline_exit_reason') or '—')}</td>"
        f"<td class='num'>day {esc(f.get('diverged_at_day'))}</td></tr>"
        for f in [*recovered, *lost]
    ) or "<tr><td colspan=4>no outcome changed</td></tr>"

    attribution = "".join(
        f"<tr><td class='mono'>{esc(a.get('criterion'))}</td>"
        f"<td>{esc(a.get('kind'))}</td>"
        f"<td class='num'>{esc(a.get('baseline_share'))}</td>"
        f"<td class='num'>{esc(a.get('candidate_share'))}</td>"
        f"<td class='num'>{esc(a.get('baseline_sole_reason'))} &rarr; "
        f"{esc(a.get('candidate_sole_reason'))}</td></tr>"
        for a in (verdict.get("attribution_deltas") or [])
    ) or "<tr><td colspan=5>no criterion moved</td></tr>"

    warn_block = (
        "<h2>Environment</h2><ul>"
        + "".join(f"<li class='warn'>{esc(w)}</li>" for w in warnings)
        + "</ul>"
    ) if warnings else ""

    return f"""<!doctype html><meta charset="utf-8">
<title>Protocol CI — {esc(verdict.get("scenario_name"))} — {esc(outcome)}</title>
<style>{STYLE}</style>
<div class="wrap">
<header>
  <h1>Protocol CI verdict</h1>
  <p class="sub">{esc(verdict.get("reason", ""))}</p>
  <div class="stamp">{stamp}</div>
</header>

{_reading_protocol()}

<div class="headline">
  <div class="big {tone}">{esc(outcome)}</div>
  <div class="sub">{len(recovered)} recovered, {len(lost)} lost,
  {esc(verdict.get("perturbed", 0))} perturbed without changing outcome,
  {esc(verdict.get("unchanged", 0))} untouched &nbsp;·&nbsp;
  retention {esc(verdict.get("baseline_retention"))} &rarr;
  {esc(verdict.get("candidate_retention"))}
  ({esc(verdict.get("retention_delta_pp"))} pp)</div>
</div>

<h2>Sign stability — why this outcome and not a stronger one</h2>
<p class="sub">A FAIL requires the drop to exceed its gate <b>and</b> to keep its
sign when the population is redrawn under a second master seed. A drop that flips
direction is below this design's resolution, and the gate downgrades it to WARN
rather than assert what its method cannot distinguish. Stability here:
<b class="{'good' if stable else 'warn'}">{'stable' if stable else 'not stable'}</b>.</p>
<table><tr><th>master seed</th><th class="num">net flips</th></tr>{stability_rows}</table>

<h2>Who changed</h2>
<p class="sub">Runs are paired per persona under common random numbers, so these
are exact flips rather than a difference of two aggregates.</p>
<table><tr><th>persona</th><th>direction</th><th>baseline exit</th>
<th class="num">diverged</th></tr>{flips}</table>

<h2>Eligibility attribution — exact Shapley</h2>
<table><tr><th>criterion</th><th>kind</th><th class="num">baseline share</th>
<th class="num">candidate share</th><th class="num">sole reason</th></tr>{attribution}</table>

{warn_block}

{_ledger_section()}

<footer>Gates are pre-registered in <span class="mono">ci/gates.json</span>, chosen
before any verdict existed. Nothing on this page was recomputed for display.</footer>
</div>"""


BUNDLE_READING_ORDER = [
    ("canary", "Did the instrument demonstrate it can fail? An eval that cannot "
               "fail is not evidence, so this comes first."),
    ("raw takes", "The seed-chosen sampled responses, in full. No aggregate here "
                  "catches degeneracy; only reading does."),
    ("quarantine", "Every rejected response with its reason. This file is the "
                   "compliance dataset, and its size relative to the cassette is "
                   "the headline result."),
    ("aggregates", "Scores and the pre-registered pass-bar verdicts."),
    ("adjudication", "The arms registered before the run, read against what "
                     "happened. Last, because meeting the verdict first colours "
                     "the reading of everything above it."),
]


def render_bundle(bundle: dict) -> str:
    """Render an evidence bundle summary, **in the bundle's own reading order**.

    The order is the constraint, not the styling. A bundle that let a reader skip
    to the numbers would defeat the protocol it ships with, so the aggregates sit
    fourth and the adjudication last on this page exactly as they do in the
    directory's README. A summary page that led with the verdict would be a nicer
    document and a worse artifact.
    """
    manifest = bundle.get("manifest") or {}
    report = (bundle.get("compliance") or {}).get("report") or {}
    verdict = (bundle.get("compliance") or {}).get("verdict") or {}
    adjudication = bundle.get("adjudication") or {}
    runtime = manifest.get("runtime") or {}

    identity = manifest.get("model", "")
    if manifest.get("model_digest"):
        identity = f"{identity}@{str(manifest['model_digest'])[:19]}"

    stamp = "".join([
        _chip("release", manifest.get("release")),
        _chip("model", identity),
        _chip("prompt", f"v{manifest.get('prompt_version')}"),
        _chip("recorded", manifest.get("recorded_at", "")),
        _chip("python", runtime.get("python_version")),
        _chip("numpy", runtime.get("numpy_version")),
        _chip("lock", runtime.get("lock_hash")),
    ])

    order = "".join(
        f"<li><b>{esc(label)}</b> — {esc(text)}</li>"
        for label, text in BUNDLE_READING_ORDER
    )

    bars = "".join(
        f"<tr><td class='mono'>{esc(b.get('metric'))}</td>"
        f"<td>{esc(b.get('kind'))}</td>"
        f"<td class='num'>{esc(b.get('observed'))}</td>"
        f"<td class='num'>{esc(b.get('bar'))}</td>"
        f"<td>{'<span class=good>pass</span>' if b.get('passed') else '<span class=bad>MISS</span>'}</td></tr>"
        for b in (verdict.get("bars") or [])
    ) or "<tr><td colspan=5>no bars recorded</td></tr>"

    arms = "".join(
        f"<tr><td class='mono'>{esc(a.get('metric'))}</td>"
        f"<td>{esc(a.get('bound'))}</td>"
        f"<td class='num'>{esc(a.get('observed'))}</td>"
        f"<td>{'<span class=good>pass</span>' if a.get('passed') else ('<span class=bad>MISS</span>' if a.get('passed') is False else '<span class=warn>not adjudicable</span>')}</td></tr>"
        for a in (adjudication.get("arms") or [])
    ) or "<tr><td colspan=4>not adjudicated</td></tr>"

    quarantined = manifest.get("quarantined_takes", 0)
    return f"""<!doctype html><meta charset="utf-8">
<title>Evidence bundle — {esc(manifest.get("release"))}</title>
<style>{STYLE}</style>
<div class="wrap">
<header>
  <h1>Evidence bundle — {esc(manifest.get("release"))}</h1>
  <p class="sub">One run of the compliance battery, against one configuration.</p>
  <div class="stamp">{stamp}</div>
</header>

<div class="protocol"><h2 style="margin-top:0">Read in this order</h2>
<ol>{order}</ol>
<p class="sub">This ordering is the protocol the bundle ships with, reproduced
here rather than replaced. A summary page that opened with the verdict would be a
nicer document and a worse artifact.</p></div>

<h2>1 · Canary — could the instrument fail?</h2>
<p class="sub">Degraded configurations were scored alongside the real one and the
run refuses to record unless they score worse.
<b class="{'good' if manifest.get('canary_sensitive') else 'bad'}">
{'sensitive — the eval detects degradation' if manifest.get('canary_sensitive') else 'NOT DEMONSTRATED for this run'}</b></p>

<h2>2 · Raw takes</h2>
<p class="sub">{esc(manifest.get("accepted_takes", 0))} accepted of
{esc(manifest.get("battery_cases", 0))} cases. The seed-chosen sample is in
<span class="mono">takes/</span> and is meant to be read in full — no metric on
this page catches degeneracy. Segments per take {esc(report.get("mean_segments_per_take"))},
single-segment rate {esc(report.get("single_segment_rate"))}.</p>

<h2>3 · Quarantine</h2>
<p class="sub"><b class="{'good' if not quarantined else 'bad'}">{esc(quarantined)}</b>
responses failed the citation gate and were not recorded. Only responses that pass
may persist; a recording made from a non-compliant response would replay
<span class="mono">grounded: true</span> forever.</p>

<h2>4 · Aggregates and pre-registered bars</h2>
<p class="sub">Bars were registered {esc(verdict.get("registered_on", "before the first live run"))}.</p>
<table><tr><th>metric</th><th>kind</th><th class="num">observed</th>
<th class="num">bar</th><th></th></tr>{bars}</table>

<h2>5 · Adjudication — the arms registered before the run</h2>
<p class="sub">{esc(adjudication.get("verdict", adjudication.get("reading", "")))}</p>
<table><tr><th>metric</th><th>bound</th><th class="num">observed</th><th></th></tr>{arms}</table>

<div class="caveat">{esc(manifest.get("caveat", ""))}</div>

<footer>The bundle directory is the record. This page is a read over it, and the
directory stays authoritative — including anything the bundle says it could not
fix about itself.</footer>
</div>"""
