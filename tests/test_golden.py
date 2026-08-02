"""Golden scenario regression (roadmap §5.1).

A fixed set of canonical (cohort, scenario) pairs with committed expected
outputs. Any diff is a *reviewed* change, not a surprise — this is what lets the
engine be refactored aggressively without silently moving the numbers a design
review depends on.

LLM output is deliberately excluded: the golden artifact covers the deterministic
simulation core only. Narration is evaluated separately (roadmap §5.3).

To accept an intended change:

    SPP_UPDATE_GOLDEN=1 pytest tests/test_golden.py

then read the diff before committing it.
"""
import json
import os
from datetime import date
from pathlib import Path

import pytest

from spp.cohort import cohort_summary, generate_cohort
from spp.protocol import ProtocolBurden, rank_by_burden, screen

GOLDEN_DIR = Path(__file__).parent / "golden"
AS_OF = date(2026, 8, 1)
UPDATING = os.getenv("SPP_UPDATE_GOLDEN") == "1"

# Canonical scenarios: conditions crossed with protocol shapes that exercise
# different parts of the engine (numeric cut-points, ordinal stages, presence
# terms, negation, empty criteria, heavy vs light participation burden).
SCENARIOS: list[dict] = [
    {
        "name": "t2d_standard",
        "condition": "type 2 diabetes", "n": 100, "seed": 42,
        "inclusion": ["age >= 50", "biomarkers.HbA1c_pct >= 7.5"],
        "exclusion": ["biomarkers.eGFR < 45", "CKD"],
        "burden": {"visits_per_year": 12},
    },
    {
        "name": "t2d_tight",
        "condition": "type 2 diabetes", "n": 100, "seed": 42,
        "inclusion": ["age >= 60", "biomarkers.HbA1c_pct >= 9.0",
                      "stage in {moderate, advanced}"],
        "exclusion": ["CKD", "cardiovascular disease", "adherence_baseline < 0.6"],
        "burden": {"visits_per_year": 24, "daily_diary": True, "washout_required": True},
    },
    {
        "name": "t2d_open_label",
        "condition": "type 2 diabetes", "n": 100, "seed": 7,
        "inclusion": [], "exclusion": [],
        "burden": {"visits_per_year": 4},
    },
    {
        "name": "copd_gold_ladder",
        "condition": "COPD", "n": 100, "seed": 42,
        "inclusion": ["stage >= GOLD2", "age >= 40"],
        "exclusion": ["lung cancer", "biomarkers.FEV1_pct_predicted < 30"],
        "burden": {"visits_per_year": 12, "travel_required": True},
    },
    {
        "name": "copd_severe_only",
        "condition": "COPD", "n": 100, "seed": 13,
        "inclusion": ["stage >= GOLD3", "biomarkers.exacerbations_per_year >= 2"],
        "exclusion": ["not tiotropium"],
        "burden": {"visits_per_year": 26, "daily_diary": True},
    },
    {
        "name": "breast_cancer_early",
        "condition": "breast cancer", "n": 100, "seed": 42,
        "inclusion": ["stage in {I, II}", "sex not in {male}"],
        "exclusion": ["biomarkers.tumour_size_cm > 5.0"],
        "burden": {"visits_per_year": 18, "procedures": ["MRI at weeks 0/12/24"]},
    },
    {
        "name": "breast_cancer_advanced",
        "condition": "breast cancer", "n": 100, "seed": 99,
        "inclusion": ["stage >= III"],
        "exclusion": ["age >= 80", "n_comorbidities >= 3"],
        "burden": {"visits_per_year": 24, "washout_required": True},
    },
    {
        "name": "ra_biologic_naive",
        "condition": "rheumatoid arthritis", "n": 100, "seed": 42,
        "inclusion": ["biomarkers.DAS28 >= 3.2", "methotrexate"],
        "exclusion": ["adalimumab", "interstitial lung disease"],
        "burden": {"visits_per_year": 8},
    },
    {
        "name": "ra_high_burden",
        "condition": "rheumatoid arthritis", "n": 100, "seed": 21,
        "inclusion": ["age >= 18", "health_literacy >= medium"],
        "exclusion": ["sdoh.transport == none"],
        "burden": {"visits_per_year": 30, "daily_diary": True, "washout_required": True},
    },
    {
        "name": "heart_failure_ungrounded",
        "condition": "heart failure", "n": 100, "seed": 42,
        "inclusion": ["stage >= NYHA2", "biomarkers.LVEF_pct < 45"],
        "exclusion": ["CKD"],
        "burden": {"visits_per_year": 12},
    },
    {
        "name": "generic_fallback_condition",
        "condition": "an unmapped condition", "n": 50, "seed": 42,
        "inclusion": ["age >= 50"],
        "exclusion": [],
        "burden": {"visits_per_year": 12},
    },
    {
        "name": "tiny_cohort_edge",
        "condition": "COPD", "n": 1, "seed": 1,
        "inclusion": ["age >= 40"],
        "exclusion": ["CKD"],
        "burden": {"visits_per_year": 12},
    },
]


def run_scenario(spec: dict) -> dict:
    """Deterministic simulation output for one scenario. No LLM, no clock."""
    cohort = generate_cohort(spec["condition"], spec["n"], seed=spec["seed"], as_of=AS_OF)
    result = screen(cohort, spec["inclusion"], spec["exclusion"])

    eligible = [p for p in cohort if p.patient_id in set(result.eligible_ids)]
    protocol = ProtocolBurden(**spec["burden"])
    ranked = rank_by_burden(eligible, protocol)

    return {
        "scenario": spec["name"],
        "condition": spec["condition"],
        "seed": spec["seed"],
        "n": spec["n"],
        "cohort_summary": cohort_summary(cohort),
        "screening": {
            "n_eligible": result.n_eligible,
            "eligibility_rate": result.eligibility_rate,
            "criteria_impact": [c.model_dump() for c in result.criteria_impact],
        },
        "eligible_summary": cohort_summary(eligible),
        "burden": {
            "n_scored": len(ranked),
            "mean_score": (
                round(sum(p.score for p in ranked) / len(ranked), 4) if ranked else 0.0
            ),
            "top": [p.model_dump() for p in ranked[:5]],
        },
    }


def canonical_json(payload: dict) -> str:
    """Stable serialisation — sorted keys so a diff shows real change only."""
    return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"


@pytest.mark.parametrize("spec", SCENARIOS, ids=lambda s: s["name"])
def test_golden_scenario(spec):
    actual = canonical_json(run_scenario(spec))
    path = GOLDEN_DIR / f"{spec['name']}.json"

    if UPDATING:
        GOLDEN_DIR.mkdir(parents=True, exist_ok=True)
        path.write_text(actual, encoding="utf-8")
        pytest.skip(f"golden file written: {path.name}")

    assert path.exists(), (
        f"missing golden file {path.name}. Generate with "
        "SPP_UPDATE_GOLDEN=1 pytest tests/test_golden.py"
    )
    assert actual == path.read_text(encoding="utf-8"), (
        f"scenario {spec['name']!r} changed. If intended, regenerate with "
        "SPP_UPDATE_GOLDEN=1 and review the diff."
    )


@pytest.mark.parametrize("spec", SCENARIOS, ids=lambda s: s["name"])
def test_same_seed_is_byte_identical(spec):
    """The Phase 0 exit criterion, asserted directly."""
    assert canonical_json(run_scenario(spec)) == canonical_json(run_scenario(spec))


def test_the_suite_covers_the_engine_surface():
    """Guard against the suite quietly narrowing as scenarios get edited."""
    all_rules = [r for s in SCENARIOS for r in (*s["inclusion"], *s["exclusion"])]
    assert any(">=" in r for r in all_rules), "no numeric comparison covered"
    assert any(" in {" in r for r in all_rules), "no set membership covered"
    assert any(r.startswith("not ") for r in all_rules), "no negation covered"
    assert any("biomarkers." in r for r in all_rules), "no namespaced lookup covered"
    assert any("sdoh." in r for r in all_rules), "no SDOH lookup covered"
    assert any(not s["inclusion"] and not s["exclusion"] for s in SCENARIOS), (
        "no empty-criteria scenario covered"
    )
    assert {s["condition"] for s in SCENARIOS} >= {
        "type 2 diabetes", "COPD", "breast cancer", "rheumatoid arthritis"
    }
