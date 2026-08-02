"""Every heuristic in the simulation core, registered in one place.

This module exists so the answer to "where did that number come from?" is always
the same: here, with a source and a confidence tag. Simulation code reads
coefficients from these objects rather than hard-coding them, which is what makes
sensitivity analysis possible and turns the caveats section into a feature.

Confidence tags are deliberately conservative. Almost everything below is
EXPERT_GUESS — directionally defensible, not fitted. `LEDGER.unsupported()`
returns exactly the set of assumptions whose outputs must never be quoted as
findings, and right now that is most of them. Replacing these with
PUBLISHED_AGGREGATE / TUNED values is what build-order item 1 (Synthea ingest)
and the calibration harness are for.
"""
from __future__ import annotations

from .foundation.ledger import Assumption, Confidence, register

# --------------------------------------------------------------------------
# Adherence: how baseline adherence is derived from a persona's barriers.
# Ported from cohort/generator.py `_derive_adherence`.
# --------------------------------------------------------------------------

ADHERENCE_LITERACY = register(Assumption(
    name="adherence.literacy_effect",
    description="Additive shift to baseline adherence by health-literacy band.",
    params={"low": -0.14, "medium": 0.0, "high": 0.07},
    source="Expert judgement, directionally consistent with adherence literature.",
    confidence=Confidence.EXPERT_GUESS,
    tags=["adherence", "cohort"],
))

ADHERENCE_ACCESS = register(Assumption(
    name="adherence.access_effect",
    description="Additive penalties for access and support barriers.",
    params={
        "transport_none": -0.12,
        "transport_public": -0.04,
        "caregiver_none": -0.06,
        "employment_shift_work": -0.07,
        "residence_rural": -0.03,
        "age_penalty": -0.05,
        "age_penalty_from": 80,
    },
    source="Expert judgement. Signs are well supported; magnitudes are not fitted.",
    confidence=Confidence.EXPERT_GUESS,
    tags=["adherence", "sdoh", "cohort"],
))

ADHERENCE_PILL_BURDEN = register(Assumption(
    name="adherence.pill_burden",
    description="Penalty per medication beyond `free_medications`, plus draw noise.",
    params={"per_extra_medication": -0.035, "free_medications": 2, "noise_sd": 0.08},
    source="Expert judgement; polypharmacy-adherence relationship is real, slope is not.",
    confidence=Confidence.EXPERT_GUESS,
    tags=["adherence", "cohort"],
))

ADHERENCE_BOUNDS = register(Assumption(
    name="adherence.bounds",
    description="Clamp on derived adherence. Nobody is modelled as perfectly zero.",
    params={"min": 0.05, "max": 1.0, "per_drug_noise_sd": 0.06},
    source="Modelling convention.",
    confidence=Confidence.EXPERT_GUESS,
    tags=["adherence", "cohort"],
))

# --------------------------------------------------------------------------
# Participation burden. Ported from protocol/burden.py `_FACTORS`.
# --------------------------------------------------------------------------

BURDEN_FACTORS = register(Assumption(
    name="burden.factor_weights",
    description=(
        "Weight contributed by each barrier when present. Summed, then scaled by "
        "protocol intensity, then clamped to [0, 1]."
    ),
    params={
        "low_adherence": 0.20,
        "no_transport": 0.18,
        "low_literacy": 0.12,
        "working": 0.12,
        "no_caregiver": 0.10,
        "polypharmacy": 0.09,
        "multimorbidity": 0.09,
        "elderly": 0.06,
        "rural": 0.04,
    },
    source="Expert judgement. Ordering is defensible; absolute weights are not.",
    confidence=Confidence.EXPERT_GUESS,
    tags=["burden", "protocol"],
))

BURDEN_THRESHOLDS = register(Assumption(
    name="burden.trigger_thresholds",
    description="Cut-points at which a barrier counts as present.",
    params={
        "low_adherence_below": 0.6,
        "polypharmacy_at_least": 3,
        "multimorbidity_at_least": 3,
        "elderly_from_age": 80,
        "at_risk_score": 0.4,
    },
    source="Expert judgement; conventional round numbers, not derived cut-points.",
    confidence=Confidence.EXPERT_GUESS,
    tags=["burden", "protocol"],
))

BURDEN_INTENSITY = register(Assumption(
    name="burden.protocol_intensity",
    description=(
        "Multiplier applied to the summed barrier weight as the protocol gets "
        "heavier. Amplifies existing barriers; adds nothing to a persona with none."
    ),
    params={
        "base": 1.0,
        "visits_12_plus": 0.15,
        "visits_24_plus": 0.15,
        "daily_diary": 0.10,
        "washout": 0.10,
    },
    source="Expert judgement. The multiplicative form is a modelling choice.",
    confidence=Confidence.EXPERT_GUESS,
    tags=["burden", "protocol"],
))

# --------------------------------------------------------------------------
# Cohort composition.
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# Timeline simulation: per-visit burden, attendance, and dropout hazard.
# --------------------------------------------------------------------------

VISIT_BURDEN = register(Assumption(
    name="timeline.visit_burden",
    description=(
        "Burden vector components accrued by one on-site visit, before "
        "persona-specific sensitivity is applied. Unitless, roughly 'fraction of "
        "one visit's worth of tolerance consumed'."
    ),
    params={
        "time": 0.030,
        "travel": 0.045,
        "procedural": 0.020,
        "cognitive": 0.010,
        "financial": 0.025,
        "scheduling": 0.020,
        "remote_travel_multiplier": 0.1,
        "procedure_increment": 0.012,
        "daily_diary_cognitive": 0.015,
        "washout_procedural": 0.08,
    },
    source="Expert judgement. The relative shape matters more than the scale.",
    confidence=Confidence.EXPERT_GUESS,
    tags=["timeline", "burden"],
))

BURDEN_SENSITIVITY = register(Assumption(
    name="timeline.burden_sensitivity",
    description=(
        "Per-persona multipliers on burden components, by profile signal. A "
        "shift worker weights scheduling friction far above someone retired — "
        "the same protocol is not the same ask."
    ),
    params={
        "base": 1.0,
        "low_mobility_travel": 2.2,
        "no_transport_travel": 2.5,
        "rural_travel": 1.6,
        "shift_work_scheduling": 3.0,
        "working_scheduling": 1.8,
        "caregiving_scheduling": 1.5,
        "low_financial_financial": 2.4,
        "low_literacy_cognitive": 2.0,
        "low_digital_cognitive": 1.8,
        "multimorbidity_time": 1.5,
        "elderly_time": 1.4,
    },
    source="Expert judgement. Magnitudes are illustrative, ordering is the claim.",
    confidence=Confidence.EXPERT_GUESS,
    tags=["timeline", "burden"],
))

ATTENDANCE = register(Assumption(
    name="timeline.attendance",
    description=(
        "Probability a persona attends a scheduled visit. Logistic in adherence, "
        "accumulated burden and barrier load."
    ),
    params={
        "intercept": 3.2,
        "adherence_weight": 2.0,
        "burden_weight": -1.0,
        "barrier_weight": -0.9,
        "visit_burden_weight": -2.2,
        "floor": 0.02,
        "ceiling": 0.99,
    },
    source="Expert judgement, shaped to give plausible per-visit attendance.",
    confidence=Confidence.EXPERT_GUESS,
    tags=["timeline", "hazard"],
))

DROPOUT_HAZARD = register(Assumption(
    name="timeline.dropout_hazard",
    description=(
        "Discrete-time dropout hazard evaluated at each visit. Logistic in "
        "cumulative burden, barrier load, adherence deficit and consecutive "
        "missed visits."
    ),
    params={
        "intercept": -5.6484,
        # FROZEN AT ZERO, not fitted. See source note: unidentifiable from the
        # current anchors. burden_increment_weight carries per-visit burden.
        "cumulative_burden_weight": 0.0,
        "burden_increment_weight": 2.0,
        "barrier_weight": 0.8,
        "adherence_deficit_weight": 1.2,
        "consecutive_missed_weight": 0.6,
        "washout_bump": 0.30,
        "max_per_visit": 0.25,
    },
    source=(
        "intercept and cumulative_burden_weight are fitted JOINTLY by "
        "scripts/calibrate_hazard.py against two anchors — a light protocol "
        "(4 remote visits/yr -> 93% retention) and a heavy one (24 visits/yr with "
        "diary and washout -> 55%). A mid-intensity 12-visit protocol is HELD OUT "
        "and lands at ~81% without being fitted, which is the evidence that the "
        "two-parameter form generalises rather than interpolating.\n\n"
        "IMPORTANT: the anchors are plausibility targets drawn from commonly "
        "reported retention ranges, NOT a fit to any observed dataset. The LEVEL "
        "of the curve is an assumption. Only the DIFFERENCE between two designs "
        "should be read as signal.\n\n"
        "cumulative_burden_weight is FROZEN AT ZERO — unidentifiable from the "
        "current anchors, NOT fitted. The two anchors differ mainly in visit "
        "count, and count already compounds through survival, so the objective is "
        "a flat ridge in this direction: any small value hits both anchors "
        "equally well. (An earlier fit returned 0.047; that was the first "
        "feasible point on the ridge, i.e. noise, not a calibrated quantity. A "
        "number in the ledger reads as calibrated no matter what this note says, "
        "so shipping it would have been misleading.) Freezing to zero lets "
        "burden_increment_weight carry per-visit burden honestly.\n\n"
        "Confirmed dead weight today: with the term at zero, every retention band "
        "still holds (light 94.8%, heavy 58.2%, held-out 81.2%) and the "
        "fixed-visit-count comparison still separates 12 remote (84.2%) from 12 "
        "on-site (81.2%).\n\n"
        "THIRD-ANCHOR PLAN: to identify it for real, add an anchor that varies "
        "per-visit burden at FIXED visit count (12 on-site vs 12 remote). Then "
        "unfreeze and fit intercept + cumulative_burden_weight against the three "
        "anchors. Until that anchor exists, do not treat this coefficient as "
        "evidence that accumulated burden does or does not matter."
    ),
    confidence=Confidence.EXPERT_GUESS,
    tags=["timeline", "hazard", "known-limitation"],
))

# --------------------------------------------------------------------------
# Narration. The model is an assumption like any coefficient.
# --------------------------------------------------------------------------

NARRATION_MODEL = register(Assumption(
    name="narration.model",
    description=(
        "The model that produces persona speech, and the prompt version it was "
        "recorded against. Registered here because swapping a model changes "
        "outputs exactly as changing a coefficient does — it is not a config "
        "detail. A swap invalidates every cassette (CassetteAdapter refuses to "
        "replay across models) and requires re-running the narration evals."
    ),
    params={
        "backend": "ollama",
        "model": "qwen2.5:7b-instruct",
        # Filled in at record time by scripts/record_narration.py. A tag is a
        # mutable pointer: a registry update can change weights and quantization
        # under the same name, so the digest is the identity that counts.
        "model_digest": "",
        "prompt_version": 1,
        "max_regenerations": 1,
        # num_ctx MUST be explicit — Ollama's default is small and it truncates
        # the prompt head silently, which is indistinguishable downstream from a
        # deliberately starved context.
        "num_ctx": 8192,
        "num_predict": 700,
        "temperature": 0.0,
        "top_p": 1.0,
        "seed": 42,
    },
    source=(
        "Chosen for local, offline-first operation. NOT yet exercised against a "
        "live model: every compliance number to date comes from scripted stub "
        "models written to test the instrument, so this model's actual citation "
        "compliance is UNMEASURED. Pass bars are pre-registered in "
        "tests/eval/pass_bars.json (before any live run); run "
        "scripts/record_narration.py --canary then --record to measure."
    ),
    confidence=Confidence.EXPERT_GUESS,
    tags=["narration", "known-limitation"],
))

PANEL_SPEAKING_ORDER = register(Assumption(
    name="panel.speaking_order",
    description=(
        "Panel turn order: highest barrier load speaks first. Deterministic and "
        "defensible — the most encumbered personas have the most to say about a "
        "design, so a truncated session still contains the signal."
    ),
    params={"strategy": "barrier_load_desc", "probe_after": 3, "max_probes": 2},
    source=(
        "Modelling choice, NOT a neutral default. Later speakers see the "
        "transcript, so the most burdened persona anchors every session. "
        "tests/test_narration.py asserts theme sets are stable under a permuted "
        "order; if that ever fails, themes are order-fragile and a design review "
        "should not lean on them."
    ),
    confidence=Confidence.EXPERT_GUESS,
    tags=["narration", "panel"],
))

HEALTH_LITERACY_MIX = register(Assumption(
    name="cohort.health_literacy_mix",
    description="Population health-literacy distribution, not condition-specific.",
    params={"low": 0.30, "medium": 0.52, "high": 0.18},
    source="Approximate adult population shape from health-literacy surveys.",
    confidence=Confidence.PUBLISHED_AGGREGATE,
    tags=["cohort"],
))

SEX_DISTRIBUTION = register(Assumption(
    name="cohort.other_sex_fraction",
    description="Share of personas recorded outside the female/male binary.",
    params={"fraction": 0.005},
    source="Modelling convention so downstream code exercises the third option.",
    confidence=Confidence.EXPERT_GUESS,
    tags=["cohort"],
))

CORRELATION_PSD_GATE = register(Assumption(
    name="cohort.correlation_psd_gate",
    description=(
        "Validity gate on the trait correlation matrix. Loading fails if the "
        "minimum eigenvalue falls below `min_eigenvalue`. Projection to the "
        "nearest PSD matrix is DISABLED by default and is never silent: enabling "
        "it returns the exact list of pairs that moved and by how much, which must "
        "then be recorded here as a correction. A projected matrix no longer "
        "matches its specification, so the ledger would stop describing what is "
        "actually sampled."
    ),
    params={
        "min_eigenvalue": 1e-6,
        "allow_projection": False,
        "recorded_corrections": [],
    },
    source="Engineering invariant, not an empirical claim.",
    confidence=Confidence.MEASURED,
    tags=["cohort", "correlation", "invariant"],
))

BARRIER_SEVERITY = register(Assumption(
    name="traits.barrier_severity",
    description=(
        "Severity assigned to each derived barrier. Feeds the dropout hazard and "
        "orders the barrier list a persona narrates from."
    ),
    params={
        "transport": 0.30,
        "scheduling": 0.24,
        "cost": 0.22,
        "unsupported": 0.20,
        "adherence": 0.20,
        "mobility": 0.18,
        "comprehension": 0.16,
        "competing_care": 0.15,
        "distance": 0.14,
        "transport_fragile": 0.12,
        "pill_burden": 0.12,
        "digital_access": 0.10,
    },
    source="Expert judgement. Relative ordering is the defensible part.",
    confidence=Confidence.EXPERT_GUESS,
    tags=["traits", "hazard"],
))

TRAIT_CORRELATIONS = register(Assumption(
    name="cohort.trait_correlations",
    description=(
        "Pairwise correlations between persona trait axes, fed to the Gaussian "
        "copula. Keys are 'axis_a|axis_b'. Convention: higher = 'more' of what the "
        "axis is named, so caregiver_support 0.9 means well supported.\n\n"
        "SEMANTICS (decided once, do not mix): these are LATENT GAUSSIAN "
        "correlations — the rho of the copula's underlying normal, which is what a "
        "copula fit to real data would estimate. They are NOT the correlations you "
        "will measure on the generated cohort. Pushing rho through the copula "
        "attenuates it to (6/pi)*arcsin(rho/2) on the uniforms (0.45 -> 0.4334), "
        "and discretising into a categorical or count marginal attenuates it "
        "substantially further. That is expected and quantified, not error.\n\n"
        "A pair omitted here is asserted UNCORRELATED. Correlation does not "
        "propagate through shared neighbours in a correlation matrix, so every "
        "relationship that should exist must be listed explicitly."
    ),
    params={
        # Ageing: sicker, less mobile, less digitally confident, more likely
        # to have someone helping, less likely to still be driving.
        "age|comorbidity_load": 0.45,
        "age|mobility": -0.40,
        "age|digital_literacy": -0.45,
        "age|caregiver_support": 0.20,
        "age|transport_access": -0.25,
        "age|financial_security": 0.10,
        # Deprivation clusters rather than scattering — the single most
        # consequential group here for attrition realism.
        "health_literacy|digital_literacy": 0.55,
        "health_literacy|financial_security": 0.35,
        "health_literacy|transport_access": 0.20,
        "health_literacy|caregiver_support": 0.10,
        "digital_literacy|financial_security": 0.30,
        "digital_literacy|mobility": 0.15,
        "financial_security|transport_access": 0.45,
        "financial_security|caregiver_support": 0.20,
        "financial_security|mobility": 0.20,
        "transport_access|mobility": 0.35,
        # Illness burden erodes mobility and finances, and pulls in support.
        "comorbidity_load|mobility": -0.35,
        "comorbidity_load|financial_security": -0.20,
        "comorbidity_load|health_literacy": -0.15,
        "comorbidity_load|transport_access": -0.15,
        "comorbidity_load|caregiver_support": 0.15,
        "mobility|caregiver_support": -0.15,
    },
    source=(
        "Expert judgement. Directions are well supported by health-inequality "
        "literature; magnitudes are not fitted to any dataset."
    ),
    confidence=Confidence.EXPERT_GUESS,
    tags=["cohort", "correlation"],
))

COMORBIDITY_AGE_SLOPE = register(Assumption(
    name="cohort.comorbidity_age_factor",
    description=(
        "Comorbidity prevalence is scaled by intercept + slope*(age - pivot). "
        "Independent Bernoulli draws — correlation structure is NOT modelled."
    ),
    params={"intercept": 0.75, "slope": 0.010, "pivot_age": 45, "cap": 0.95},
    source="Expert judgement. The independence assumption is a known limitation.",
    confidence=Confidence.EXPERT_GUESS,
    tags=["cohort", "known-limitation"],
))

EPIDEMIOLOGY_PRIORS = register(Assumption(
    name="cohort.condition_priors",
    description=(
        "Per-condition age/sex/stage/comorbidity/biomarker priors in "
        "cohort/epidemiology.py. Order-of-magnitude literature ballparks."
    ),
    params={"source_module": "spp.cohort.epidemiology", "conditions": 5},
    source="Compiled from published prevalence summaries; not fitted to any dataset.",
    confidence=Confidence.EXPERT_GUESS,
    tags=["cohort", "known-limitation"],
))
