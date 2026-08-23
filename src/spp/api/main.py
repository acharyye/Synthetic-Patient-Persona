"""FastAPI surface for the three demo use cases:
  - /persona/interview     : talk to one synthetic patient (grounded)
  - /cohort/generate       : build a synthetic patient panel
  - /protocol/stress-test  : run a draft protocol past a cohort

Design/ideation and stakeholder-simulation only. Nothing returned here is
regulatory evidence, a virtual control arm, or a decision about a real person.
"""
from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from ..assumptions import BURDEN_THRESHOLDS
from ..cohort import cohort_summary, generate_cohort
from ..cohort.residency import RESIDENT
from ..config import settings
from ..foundation import LEDGER
from ..persona import PersonaEngine
from ..protocol.lenient import parse_lenient
from ..protocol import (
    CriterionError,
    attribute_eligibility,
    ProtocolBurden,
    burden_report,
    known_fields,
    rank_by_burden,
    screen,
)
from ..knowledge import fact_detail, load_graph
from ..narration import interview as narration_interview, run_panel
from ..narration.evaluation import load_battery
from ..narration.state_facts import is_state_id, state_detail
from ..narration.room import (
    MEMORY_SEMANTICS,
    available_questions,
    ask,
    free_text_state,
    load_room_cassette,
)
from ..report import compare_cohorts, render_counterfactual, studio_view
from ..schemas import PatientDNA
from ..simulation import (
    attrition_funnel,
    build_report,
    fork,
    run_sensitivity,
    sign_is_stable,
    burden_breakdown,
    retention_summary,
    schedule_from_protocol,
    simulate_cohort,
    survival_curve,
)

from .. import __version__

app = FastAPI(title="Synthetic Patient Persona", version=__version__)
_engine = PersonaEngine()

DISCLAIMER = (
    "Synthetic personas for design and stakeholder simulation. Not medical "
    "advice, not regulatory evidence, not a statistical virtual control arm."
)


class InterviewRequest(BaseModel):
    dna: PatientDNA
    message: str


class CohortRequest(BaseModel):
    condition: str
    n: int = Field(10, ge=1, le=500)
    seed: int | None = 42


class ProtocolRequest(BaseModel):
    condition: str
    n: int = Field(20, ge=1, le=500)
    seed: int | None = 42
    # e.g. ["age>=50", "stage in {moderate, advanced}"]
    inclusion: list[str] = Field(default_factory=list)
    # e.g. ["CKD", "adherence_baseline<0.5", "biomarkers.eGFR < 30"]
    exclusion: list[str] = Field(default_factory=list)
    burden: ProtocolBurden = Field(default_factory=ProtocolBurden)
    # How many of the highest-burden eligible personas to actually interview.
    # Each one is an LLM call when SPP_LIVE=true, so keep it small by default.
    interview_top_n: int = Field(3, ge=0, le=25)


@app.get("/health")
def health() -> dict:
    """Reports whether grounding is real. `graph_live: false` means personas are
    running on the offline stub subgraph, not the knowledge graph.
    """
    stats = _engine.graph.stats()
    return {
        "status": "ok",
        "graph_live": _engine.graph.live,
        "graph_nodes": stats.get("nodes", 0),
        "graph_relationships": stats.get("relationships", 0),
    }


class SimulationRequest(BaseModel):
    condition: str
    n: int = Field(50, ge=1, le=500)
    seed: int | None = 42
    duration_days: int = Field(365, gt=0, le=3650)
    inclusion: list[str] = Field(default_factory=list)
    exclusion: list[str] = Field(default_factory=list)
    burden: ProtocolBurden = Field(default_factory=ProtocolBurden)


@app.post("/simulation/run")
def run_simulation(req: SimulationRequest) -> dict:
    """Screen a cohort, then walk the eligible personas through the schedule.

    Returns the attrition funnel, a survival curve, and the burden breakdown that
    says *which kind* of burden drove the dropouts — travel, scheduling or
    cognitive load lead to different design fixes.

    Read the DIFFERENCE between two runs, not the absolute retention: the hazard
    is tuned to a plausibility target, not fitted to observed retention data.
    See GET /assumptions.
    """
    cohort = generate_cohort(req.condition, req.n, seed=req.seed)

    try:
        screening = screen(cohort, req.inclusion, req.exclusion)
    except CriterionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    eligible_ids = set(screening.eligible_ids)
    eligible = [p for p in cohort if p.patient_id in eligible_ids]

    schedule = schedule_from_protocol(req.burden, duration_days=req.duration_days)
    logs = simulate_cohort(
        eligible, schedule, seed=req.seed or 42, condition=req.condition,
        washout=req.burden.washout_required,
    )

    return {
        "condition": req.condition,
        "schedule": {"visits": len(schedule), "duration_days": schedule.duration_days},
        "funnel": attrition_funnel(logs, screened=len(cohort)),
        "retention": retention_summary(logs),
        "survival_curve": survival_curve(logs, schedule.duration_days),
        "burden_breakdown": burden_breakdown(logs),
        "eligibility_rate": screening.eligibility_rate,
        "disclaimer": DISCLAIMER,
    }


class CounterfactualRequest(BaseModel):
    condition: str
    n: int = Field(100, ge=1, le=500)
    seed: int | None = 42
    duration_days: int = Field(365, gt=0, le=3650)
    inclusion: list[str] = Field(default_factory=list)
    exclusion: list[str] = Field(default_factory=list)
    burden: ProtocolBurden = Field(default_factory=ProtocolBurden)

    # The design change. Exactly one is applied, in this order.
    drop_visits: list[str] = Field(default_factory=list)
    remote_visits: list[str] = Field(default_factory=list)
    check_sign_stability: bool = True
    sensitivity: bool = False


@app.post("/counterfactual/run")
def counterfactual(req: CounterfactualRequest) -> dict:
    """Fork a scenario, change one thing, re-run under identical seeds, diff.

    The primary output is the **flip table**, not two curves subtracted. Because
    every draw is keyed by stable identity, the two runs are paired per persona,
    so "31 recovered, 11 lost" is exact where a 2-point retention delta would be
    inside the noise.

    `sign_stability` re-runs under a second master seed: if the net flip count
    does not keep its sign, treat the result as a draw artifact, not an effect.
    """
    cohort = generate_cohort(req.condition, req.n, seed=req.seed)

    try:
        screening = screen(cohort, req.inclusion, req.exclusion)
    except CriterionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    eligible_ids = set(screening.eligible_ids)
    eligible = [p for p in cohort if p.patient_id in eligible_ids]
    if not eligible:
        raise HTTPException(status_code=400, detail="no personas survived screening")

    schedule = schedule_from_protocol(req.burden, duration_days=req.duration_days)
    known = {v.visit_id for v in schedule.visits}
    unknown = (set(req.drop_visits) | set(req.remote_visits)) - known
    if unknown:
        raise HTTPException(
            status_code=400,
            detail=f"unknown visit id(s) {sorted(unknown)}; schedule has {sorted(known)}",
        )
    if not req.drop_visits and not req.remote_visits:
        raise HTTPException(
            status_code=400, detail="specify drop_visits and/or remote_visits"
        )

    def mutate(s):
        if req.drop_visits:
            s = s.without(*req.drop_visits)
        if req.remote_visits:
            s = s.remote(*req.remote_visits)
        return s

    change = ", ".join(filter(None, [
        f"drop {req.drop_visits}" if req.drop_visits else "",
        f"remote {req.remote_visits}" if req.remote_visits else "",
    ]))
    seed = req.seed or 42
    diff = fork(eligible, schedule, mutate, seed=seed,
                label=change, condition=req.condition,
                washout=req.burden.washout_required)

    stability = None
    if req.check_sign_stability:
        def rebuild(other_seed: int):
            people = generate_cohort(req.condition, req.n, seed=other_seed)
            verdicts = screen(people, req.inclusion, req.exclusion)
            keep = set(verdicts.eligible_ids)
            return [p for p in people if p.patient_id in keep]

        stability = sign_is_stable(
            rebuild, schedule, mutate, seeds=(seed, seed + 1192),
            condition=req.condition,
        )

    sensitivity = None
    if req.sensitivity:
        report = run_sensitivity(eligible, schedule, perturbation=0.25, seed=seed,
                                 condition=req.condition)
        sensitivity = {
            "headline": report.headline(),
            "perturbation": report.perturbation,
            "ranked": [e.model_dump() for e in report.most_sensitive(8)],
        }

    artifact = build_report(
        diff,
        title=f"{req.condition}: {change}",
        change=change,
        condition=req.condition,
        master_seed=seed,
        schedule_name=schedule.name,
        schedule_visits=len(schedule),
        duration_days=req.duration_days,
        eligibility=attribute_eligibility(screening),
        sign_stability=stability,
        sensitivity=sensitivity,
    )
    return artifact.model_dump()


class NarratedInterviewRequest(BaseModel):
    condition: str
    n: int = Field(1, ge=1, le=50)
    seed: int | None = 42
    persona_index: int = Field(0, ge=0)
    question: str
    strict: bool = False


@app.post("/persona/narrate")
def narrate(req: NarratedInterviewRequest) -> dict:
    """Interview a persona with mechanically verified citations.

    Offline this returns the null backend's citation skeleton — structured, cited
    and verifiable — so the whole pipeline (retrieval, prompt, citation gate,
    event append) is exercised without a model. `grounded: false` means the
    answer failed verification after its one permitted retry.
    """
    cohort = generate_cohort(req.condition, req.n, seed=req.seed)
    if req.persona_index >= len(cohort):
        raise HTTPException(status_code=400, detail="persona_index out of range")

    turn = narration_interview(
        cohort[req.persona_index], req.question, strict=req.strict
    )
    return {**turn.model_dump(exclude={"check"}), "disclaimer": DISCLAIMER}


class PanelRequest(BaseModel):
    condition: str
    n: int = Field(6, ge=2, le=12)
    seed: int | None = 42
    topic: str


@app.post("/panel/run")
def panel(req: PanelRequest) -> dict:
    """Run a grounded focus group.

    Turn order, probing and termination are a deterministic state machine; only
    each turn's wording comes from a model. Themes group by shared cited facts,
    so "3 of 6 personas raised travel" is a count over citations rather than a
    judgement call.
    """
    cohort = generate_cohort(req.condition, req.n, seed=req.seed)
    transcript = run_panel(cohort, req.topic)
    return {
        **transcript.model_dump(),
        "ungrounded_statements": len(transcript.ungrounded()),
        "disclaimer": DISCLAIMER,
    }


class PreviewRequest(BaseModel):
    """Keystroke-rate eligibility preview. Deliberately NOT a simulation."""

    condition: str
    n: int = Field(200, ge=1, le=2000)
    seed: int = 42
    inclusion: list[str] = Field(default_factory=list)
    exclusion: list[str] = Field(default_factory=list)
    # Monotonic, supplied by the client. Echoed back so a response that lands
    # out of order can be discarded rather than overwriting a fresher one — a
    # stale attrition number next to the rule on screen is a credibility wound.
    sequence: int = 0


@app.post("/scenario/preview")
def scenario_preview(req: PreviewRequest) -> dict:
    """Per-rule attrition over a resident cohort. One pass, no timeline.

    This is the fast half of the deliberate latency split. Eligibility over a
    cohort already in memory is a single pass and can run on every keystroke;
    timeline simulation cannot, and stays behind an explicit button. Blurring
    that line would make the fast thing feel slow.

    Parsing is LENIENT: a half-typed rule is editor state, not a failure. Invalid
    criteria come back as diagnostics with locations, the valid subset is still
    scored, and `stale` tells the UI to mark the numbers rather than blank them.
    """
    parse = parse_lenient(req.inclusion, req.exclusion)
    cohort, key, cached = RESIDENT.get(req.condition, req.seed, req.n)

    result = screen(cohort, parse.valid_inclusion, parse.valid_exclusion)
    attribution = attribute_eligibility(result)

    return {
        "sequence": req.sequence,
        "cohort": {
            "identity": key.describe(),
            "size": len(cohort),
            "cached": cached,
        },
        "diagnostics": [d.model_dump() for d in parse.diagnostics],
        "stale": not parse.ok,
        "stale_reason": parse.stale_reason(),
        "eligible": result.n_eligible,
        "screened": result.n_screened,
        "eligibility_rate": result.eligibility_rate,
        "criteria_impact": [c.model_dump() for c in result.criteria_impact],
        "attribution": [
            {**r.model_dump(), "shapley": round(r.shapley, 3),
             "shapley_share": round(r.shapley_share, 4)}
            for r in attribution.rules
        ],
    }


@app.get("/scenario/residency")
def residency_stats() -> dict:
    """Cache observability. Eviction is safe because the key IS the identity."""
    return RESIDENT.stats()


@app.post("/counterfactual/report", response_class=HTMLResponse)
def counterfactual_report(req: CounterfactualRequest) -> str:
    """The same artifact as /counterfactual/run, rendered as a standalone page.

    Pure read: nothing is recomputed for display. No JavaScript and no external
    assets, so it opens from a file:// URL in a meeting where the wifi died.
    """
    return render_counterfactual(counterfactual(req))


class RoomRequest(BaseModel):
    condition: str
    seed: int = 42
    n: int = Field(6, ge=1, le=50)
    persona_index: int = Field(0, ge=0)
    question: str | None = None


def _room_persona(req: RoomRequest):
    cohort = generate_cohort(req.condition, req.n, seed=req.seed)
    if req.persona_index >= len(cohort):
        raise HTTPException(status_code=400, detail="persona_index out of range")
    return cohort[req.persona_index]


@app.post("/room/session")
def room_session(req: RoomRequest) -> dict:
    """What this persona can be asked, and with what evidence behind each answer.

    In cassette mode the recorded questions ARE the interface — a free-text box
    would be a machine for cache misses, since cassettes key on a prompt hash
    that embeds the persona and its retrieved facts. Free text is reported as
    disabled with the reason, and unlocks when a live backend is configured.
    """
    dna = _room_persona(req)
    cassette = load_room_cassette()
    battery = load_battery()
    questions = available_questions(dna, cassette, battery)

    return {
        "persona": {
            "id": dna.patient_id,
            "summary": dna.summary(),
            "context": dna.context(),
            "barriers": [b.model_dump() for b in dna.barriers],
        },
        "evidence_mode": "cassette" if cassette else "skeleton",
        "cassette": (
            {"model": cassette.model, "backend": cassette.backend,
             "prompt_version": cassette.prompt_version, "takes": len(cassette.takes)}
            if cassette else None
        ),
        "questions": [q.model_dump() for q in questions],
        "free_text": free_text_state(cassette, live=settings.spp_live),
        "memory_semantics": MEMORY_SEMANTICS,
        "disclaimer": DISCLAIMER,
    }


@app.post("/room/ask")
def room_ask(req: RoomRequest) -> dict:
    """Answer one question, always naming the evidence behind it."""
    if not req.question:
        raise HTTPException(status_code=400, detail="question is required")
    dna = _room_persona(req)
    answer = ask(dna, req.question, cassette=load_room_cassette())
    return {**answer.model_dump(), "evidence_label": answer.evidence.label(),
            "disclaimer": DISCLAIMER}


@app.post("/room/fact/{fact_id}")
def room_fact(fact_id: str, req: RoomRequest) -> dict:
    """Citation click-through: the fact, its provenance, and its simulation link.

    Dispatches on the id's namespace. A `P-`/`B-`/`J-` id is the persona's own
    declared state and resolves against the persona; anything else is graph
    knowledge and resolves against the graph. The two payloads are distinct
    models carrying a `kind`, because a reader who cannot tell which provenance
    they are looking at is the exact ambiguity the four-namespace split exists to
    prevent.

    When the fact concerns a Barrier, `simulation_link` names which of this
    persona's derived barriers resolves to it — the participation-subgraph join,
    made visible, from either side.
    """
    dna = _room_persona(req)
    if is_state_id(fact_id):
        state = state_detail(dna, fact_id)
        if state is None:
            raise HTTPException(
                status_code=404,
                detail=f"{fact_id!r} is not on file for {dna.patient_id}",
            )
        return state.model_dump()

    detail = fact_detail(load_graph(), fact_id, persona=dna)
    if detail is None:
        raise HTTPException(status_code=404, detail=f"no fact {fact_id!r}")
    return detail.model_dump()


class StudioRequest(BaseModel):
    condition: str
    n: int = Field(300, ge=10, le=2000)
    seed: int = 42


@app.post("/studio/marginals")
def studio_marginals(req: StudioRequest) -> dict:
    """Observed marginals against the tolerance bands the PACK declares.

    Thresholds are read from each pack entry, never transcribed here — these
    charts are the pack-generated contract suite made visible, reading the same
    field the tests assert against.
    """
    view = studio_view(req.condition, n=req.n, seed=req.seed)
    return {
        **view.model_dump(),
        "headline": view.headline(),
        "out_of_band": [b.field for b in view.out_of_band],
        "disclaimer": DISCLAIMER,
    }


class CohortDiffRequest(BaseModel):
    condition: str
    n: int = Field(300, ge=10, le=2000)
    left_seed: int = 42
    right_seed: int = 43
    # Positional pairing across seeds, for checking generation reproducibility
    # only. Still emits no per-persona rows.
    determinism_debug: bool = False


@app.post("/studio/diff")
def studio_diff(req: CohortDiffRequest) -> dict:
    """Compare two cohorts in the only mode their inputs support.

    Identity pairing (same seed) gets per-persona rows, because the same person
    on both sides makes a delta signal. Different seeds draw independent samples,
    so the comparison goes distributional — per-pair deltas would be sampling
    noise rendered with the flip table's authority.
    """
    comparison = compare_cohorts(
        req.condition, req.left_seed, req.right_seed, n=req.n,
        allow_determinism_debug=req.determinism_debug,
    )
    return {
        "left": comparison.left, "right": comparison.right,
        "mode": comparison.mode,
        "headline": comparison.headline(),
        "note": comparison.note,
        "n": comparison.n,
        "marginals": [
            {**m.model_dump(), "delta": m.delta,
             "left_within": m.left_within, "right_within": m.right_within}
            for m in comparison.marginals
        ],
        "out_of_band": [m.field for m in comparison.out_of_band],
        "persona_changes": [c.model_dump() for c in comparison.persona_changes],
        "summary_changes": [c.model_dump() for c in comparison.summary_diff.changes],
        "unchanged_fields": comparison.summary_diff.unchanged,
        "disclaimer": DISCLAIMER,
    }


@app.get("/assumptions")
def assumptions() -> dict:
    """Every heuristic the simulation uses, with source and confidence.

    `unsupported` lists the assumptions whose outputs must never be quoted as
    findings. Exposing this is deliberate: the caveats are part of the product,
    not a disclaimer buried in a README.
    """
    snapshot = LEDGER.snapshot()
    return {
        **snapshot,
        "unsupported": [a.name for a in LEDGER.unsupported()],
        "note": (
            "Assumptions tagged expert_guess are directionally defensible design "
            "judgement, not fitted values. Numbers derived from them are "
            "simulated under stated assumptions, never findings."
        ),
    }


@app.get("/protocol/fields")
def protocol_fields() -> dict:
    """Fields and syntax available to inclusion/exclusion criteria."""
    return {
        "fields": known_fields(),
        "syntax": [
            "age >= 50",
            "biomarkers.HbA1c_pct > 7.5",
            "stage in {moderate, advanced}",
            "sex not in {male}",
            "CKD",
            "not metformin",
        ],
        "semantics": "inclusion criteria are ANDed; exclusion criteria are ORed",
    }


@app.post("/persona/interview")
def interview(req: InterviewRequest) -> dict:
    return {**_engine.interview(req.dna, req.message), "disclaimer": DISCLAIMER}


@app.post("/cohort/generate")
def cohort(req: CohortRequest) -> dict:
    people = generate_cohort(req.condition, req.n, seed=req.seed)
    return {
        "n": len(people),
        "summary": cohort_summary(people),
        "cohort": [p.model_dump(mode="json") for p in people],
        "disclaimer": DISCLAIMER,
    }


@app.post("/protocol/stress-test")
def stress_test(req: ProtocolRequest) -> dict:
    """Screen a synthetic cohort against a draft protocol, then ask the personas
    it would keep whether taking part is realistic for them.

    Returns three things worth acting on:
      * `criteria_impact` — which single criterion is costing you the most
        candidates (`sole_reason` = would have qualified but for that line).
      * `at_risk` — eligible on paper, high participation burden.
      * `interviews` — those personas answering in their own words.
    """
    people = generate_cohort(req.condition, req.n, seed=req.seed)

    try:
        result = screen(people, req.inclusion, req.exclusion)
    except CriterionError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    eligible_ids = set(result.eligible_ids)
    eligible = [p for p in people if p.patient_id in eligible_ids]

    burden_ranked = rank_by_burden(eligible, req.burden)
    by_id = {p.patient_id: p for p in eligible}
    interviews = [
        burden_report(_engine, by_id[profile.patient_id], req.burden)
        for profile in burden_ranked[: req.interview_top_n]
    ]

    return {
        "condition": req.condition,
        "screening": {
            "n_screened": result.n_screened,
            "n_eligible": result.n_eligible,
            "eligibility_rate": result.eligibility_rate,
            "criteria_impact": [c.model_dump() for c in result.criteria_impact],
            "verdicts": [v.model_dump() for v in result.verdicts],
        },
        "cohort_summary": cohort_summary(people),
        "eligible_summary": cohort_summary(eligible),
        "at_risk": [
            p.model_dump()
            for p in burden_ranked
            if p.score >= BURDEN_THRESHOLDS.params["at_risk_score"]
        ],
        "interviews": interviews,
        "disclaimer": DISCLAIMER,
    }
