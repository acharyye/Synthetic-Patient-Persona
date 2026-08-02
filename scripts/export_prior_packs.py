"""Export the in-code condition priors to versioned JSON prior packs.

    PYTHONPATH=src python scripts/export_prior_packs.py

HISTORICAL — this migration has already run and CONDITION_EPI has since been
removed from epidemiology.py, so this script no longer executes. Retained as
the record of how data/prior_packs/*.json were produced.

One-way migration, run once: `cohort/epidemiology.py` was the source of truth,
the packs are now. Generating them rather than retyping them means the values in
`data/prior_packs/*.json` are provably the ones the system has been running and
testing against — a hand transcription would have silently changed the cohort.

After this, edit the JSON. The Python constants remain only as the fallback for
a condition with no pack.
"""
from __future__ import annotations

import json
from datetime import date

from spp.assumptions import BARRIER_SEVERITY, HEALTH_LITERACY_MIX, TRAIT_CORRELATIONS
from spp.cohort.epidemiology import CONDITION_EPI, ConditionEpi
from spp.cohort.packs import PACK_DIR, PACK_SCHEMA_VERSION, PriorPack

AS_OF = date(2026, 8, 1)

LITERATURE = {
    "source": "Compiled from published prevalence summaries; not fitted to any dataset.",
    "confidence": "expert_guess",
    "as_of": AS_OF.isoformat(),
}
POPULATION = {
    "source": "Approximate adult population shape from health-literacy surveys.",
    "confidence": "published_aggregate",
    "as_of": AS_OF.isoformat(),
}
JUDGEMENT = {
    "source": "Expert judgement. Directions are supported by the health-inequality "
              "literature; magnitudes are not fitted.",
    "confidence": "expert_guess",
    "as_of": AS_OF.isoformat(),
}

# Fields whose realized behaviour is shaped by mechanisms beyond the copula.
STRUCTURAL_PATHS = {
    "comorbidities": [
        "cohort.comorbidity_age_factor scales prevalence by age, stacking a causal "
        "age->comorbidity path on top of the latent age|comorbidity_load correlation",
        "the latent comorbidity_load axis additionally modulates every threshold",
    ],
    "base_adherence": [
        "adherence is DERIVED from literacy, SDOH and pill burden "
        "(see adherence.* assumptions), not sampled from this marginal directly",
    ],
    "stage": [
        "stage is selected by the comorbidity_load axis, so it inherits every "
        "correlation that axis carries",
    ],
}


def marginals_for(epi: ConditionEpi) -> list[dict]:
    entries: list[dict] = [
        {
            "field": "age",
            "family": "normal",
            "params": {"mean": epi.age_mean, "sd": epi.age_sd},
            "support": [epi.age_min, epi.age_max],
            "provenance": LITERATURE,
            "tolerance": 4.0,
        },
        {
            "field": "sex",
            "family": "categorical",
            "params": {
                "female": round(epi.female_fraction, 4),
                "male": round(1.0 - epi.female_fraction, 4),
            },
            "support": ["female", "male", "other"],
            "provenance": LITERATURE,
            "tolerance": 0.06,
        },
        {
            "field": "stage",
            "family": "categorical",
            "params": {k: round(v, 4) for k, v in epi.stage_weights.items()},
            "support": list(epi.stage_weights),
            "provenance": LITERATURE,
            "tolerance": 0.07,
            "structural_paths": STRUCTURAL_PATHS["stage"],
        },
        {
            "field": "comorbidities",
            "family": "bernoulli_set",
            "params": {k: round(v, 4) for k, v in epi.comorbidity_prevalence.items()},
            "provenance": LITERATURE,
            "tolerance": 0.20,
            "structural_paths": STRUCTURAL_PATHS["comorbidities"],
        },
        {
            "field": "health_literacy",
            "family": "categorical",
            "params": dict(HEALTH_LITERACY_MIX.params),
            "support": ["low", "medium", "high"],
            "provenance": POPULATION,
            "tolerance": 0.06,
        },
        {
            "field": "medication_ladder",
            "family": "ladder",
            "params": {"rungs": [list(rung) for rung in epi.medication_ladder]},
            "provenance": LITERATURE,
            "tolerance": 0.0,
        },
        {
            "field": "base_adherence",
            "family": "scalar",
            "params": {"value": epi.base_adherence},
            "provenance": LITERATURE,
            "tolerance": 0.15,
            "structural_paths": STRUCTURAL_PATHS["base_adherence"],
        },
        {
            "field": "dx_delay_months",
            "family": "scalar",
            "params": {"lo": epi.dx_delay_months[0], "hi": epi.dx_delay_months[1]},
            "provenance": LITERATURE,
            "tolerance": 0.0,
        },
    ]

    entries.extend(
        {
            "field": f"biomarker:{spec.name}",
            "family": "normal",
            "params": {
                "mean": spec.mean, "sd": spec.sd,
                "decimals": spec.decimals, "stage_shift": list(spec.stage_shift),
            },
            "support": [spec.lo, spec.hi],
            "provenance": LITERATURE,
            "tolerance": max(1.0, spec.sd * 0.5),
            "structural_paths": (
                ["stage_shift moves the mean by disease stage"] if spec.stage_shift else []
            ),
        }
        for spec in epi.biomarkers
    )
    return entries


def latent_correlations() -> list[dict]:
    """The full explicit matrix. No sparse specs in packs either — an omitted
    pair is an assertion of independence, and packs must say what they assert.
    """
    return [
        {
            "axis_a": key.split("|")[0],
            "axis_b": key.split("|")[1],
            "rho": rho,
            "provenance": JUDGEMENT,
            "tolerance": 0.02,
        }
        for key, rho in sorted(TRAIT_CORRELATIONS.params.items())
    ]


def main() -> None:
    PACK_DIR.mkdir(parents=True, exist_ok=True)
    correlations = latent_correlations()

    for key, epi in CONDITION_EPI.items():
        payload = {
            "schema_version": PACK_SCHEMA_VERSION,
            "name": key.replace(" ", "_"),
            "condition": epi.label,
            "aliases": list(epi.aliases),
            "description": epi.source_note,
            "marginals": marginals_for(epi),
            "latent_correlations": correlations,
            "derivations": {
                "barrier_severity": dict(BARRIER_SEVERITY.params),
                "goal_limit": 3,
                "provenance": JUDGEMENT,
            },
        }

        # Validate before writing: never emit a pack that cannot be loaded.
        pack = PriorPack.model_validate(payload)
        path = PACK_DIR / f"{pack.name}.json"
        path.write_text(
            json.dumps(payload, indent=2, sort_keys=False, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        print(f"wrote {path.relative_to(PACK_DIR.parents[1])}  "
              f"({len(pack.marginals)} marginals, "
              f"{len(pack.latent_correlations)} correlations)")


if __name__ == "__main__":
    main()
