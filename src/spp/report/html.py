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
