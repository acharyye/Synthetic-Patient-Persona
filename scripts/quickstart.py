"""Run the pipeline once, offline, with no external services.

    python scripts/quickstart.py

With SPP_LIVE=false the persona replies are deterministic stubs and the graph
returns a small canned subgraph — the shapes are identical to live mode, so the
whole flow is demoable with nothing running.
"""
from spp.cohort import cohort_summary, generate_cohort
from spp.persona import PersonaEngine
from spp.protocol import ProtocolBurden, burden_report, rank_by_burden, screen
from spp.schemas import Medication, PatientDNA

CONDITION = "type 2 diabetes"
engine = PersonaEngine()


def rule(title: str) -> None:
    print(f"\n{'=' * 72}\n{title}\n{'=' * 72}")


# ---------------------------------------------------------------------------
rule("1. INTERVIEW ONE PERSONA (grounded)")

dna = PatientDNA(
    patient_id="demo-0001",
    age=64,
    sex="female",
    condition=CONDITION,
    stage="moderate",
    comorbidities=["hypertension", "obesity"],
    medications=[Medication(name="metformin", dose="1000mg", adherence=0.7)],
    adherence_baseline=0.7,
    health_literacy="low",
)

out = engine.interview(dna, "How are you managing your medication schedule?")
print("PERSONA REPLY:\n ", out["reply"], "\n")
print("GROUNDED EDGES:")
for edge in out["grounded_edges"]:
    print("  ", edge)


# ---------------------------------------------------------------------------
rule(f"2. GENERATE A COHORT ({CONDITION})")

cohort = generate_cohort(CONDITION, n=200, seed=42)
summary = cohort_summary(cohort)

print(f"n={summary['n']}  mean age {summary['age_mean']} {summary['age_range']}")
print(f"sex: {summary['sex']}")
print(f"stage: {summary['stage']}")
print(f"health literacy: {summary['health_literacy']}")
print(f"mean adherence {summary['adherence_mean']}, "
      f"{summary['adherence_below_50pct']} patients below 0.5")
print(f"mean comorbidity count {summary['mean_comorbidity_count']}")
print("\nexample persona:\n ", cohort[0].summary())


# ---------------------------------------------------------------------------
rule("3. STRESS-TEST A DRAFT PROTOCOL")

inclusion = ["age >= 50", "biomarkers.HbA1c_pct >= 7.5", "stage in {moderate, advanced}"]
exclusion = ["biomarkers.eGFR < 45", "adherence_baseline < 0.5", "CKD"]
burden = ProtocolBurden(
    visits_per_year=24,
    daily_diary=True,
    procedures=["fasting bloods at every visit"],
)

print("inclusion:", inclusion)
print("exclusion:", exclusion)
print("ask      :", burden.describe())

result = screen(cohort, inclusion, exclusion)
print(f"\nELIGIBLE: {result.n_eligible}/{result.n_screened} "
      f"({result.eligibility_rate:.1%})\n")

print(f"{'kind':<10}{'criterion':<40}{'screens out':>12}{'sole reason':>13}")
for impact in result.criteria_impact:
    print(f"{impact.kind:<10}{impact.criterion:<40}"
          f"{impact.screened_out:>7} ({impact.screened_out_rate:>4.0%})"
          f"{impact.sole_reason:>13}")
print("\n'sole reason' = patients who would have qualified but for that one line.")


# ---------------------------------------------------------------------------
rule("4. WHAT PARTICIPATION WOULD COST THE ONES YOU KEPT")

eligible = {p.patient_id: p for p in cohort if p.patient_id in set(result.eligible_ids)}
ranked = rank_by_burden(list(eligible.values()), burden)

for profile in ranked[:3]:
    report = burden_report(engine, eligible[profile.patient_id], burden)
    print(f"\n[{report['patient_id']}] burden {report['score']}")
    print(" ", report["summary"])
    for driver in report["drivers"]:
        print("   -", driver)
    print("  says:", report["response"])

print("\nSynthetic personas for design and stakeholder simulation. Not medical "
      "advice,\nnot regulatory evidence, not a statistical virtual control arm.")


# ---------------------------------------------------------------------------
rule("5. WALK THEM THROUGH THE PROTOCOL (timeline simulation)")

from spp.simulation import (  # noqa: E402
    burden_breakdown, retention_summary, schedule_from_protocol, simulate_cohort,
    survival_curve,
)

designs = [
    ("light   (4/yr, remote)", ProtocolBurden(visits_per_year=4, travel_required=False)),
    ("typical (12/yr, on-site)", ProtocolBurden(visits_per_year=12)),
    ("heavy   (24/yr + diary)", ProtocolBurden(visits_per_year=24, daily_diary=True)),
]

for label, design in designs:
    schedule = schedule_from_protocol(design, duration_days=365)
    logs = simulate_cohort(cohort, schedule, seed=42)
    stats = retention_summary(logs)
    worst = max(burden_breakdown(logs).items(), key=lambda kv: kv[1])
    print(f"\n{label}  [{len(schedule)} visits]")
    print(f"  retention {stats['retention_rate']:.1%}   "
          f"attendance {stats['overall_attendance_rate']:.1%}   "
          f"dominant burden: {worst[0]}")
    curve = survival_curve(logs, 365, points=7)
    print("  " + " ".join(f"d{p['day']}:{p['retention']:.0%}" for p in curve))
    top = list(stats["dropout_reasons"].items())[:2]
    if top:
        print("  why they left: " + ", ".join(f"{r} x{n}" for r, n in top))

print("\nRead the DIFFERENCE between designs, not the absolute retention — the")
print("hazard model is tuned to a plausibility target, not fitted to trial data.")
print("GET /assumptions lists every coefficient and how much to trust it.")
