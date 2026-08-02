"""Timeline simulation: the deterministic core that decides what happens.

Nothing in this package calls an LLM. Personas walk a schedule, accrue burden,
miss visits and drop out according to seeded draws against ledger-registered
hazards. Narration explains the resulting event logs afterwards.
"""
from .counterfactual import DiffResult, Flip, diff_runs, fork, sign_is_stable
from .hazard import attendance_probability, dominant_reason, dropout_probability
from .report import DiffReport, RunProvenance, build_report
from .schedule import (
    ScheduledVisit,
    VisitSchedule,
    burden_sensitivity,
    experienced_burden,
)
from .sensitivity import SensitivityReport, perturbed, run_sensitivity
from .survival import (
    attrition_funnel,
    burden_breakdown,
    retention_summary,
    survival_curve,
)
from .timeline import schedule_from_protocol, simulate_cohort, simulate_persona

__all__ = [
    "DiffReport",
    "DiffResult",
    "Flip",
    "ScheduledVisit",
    "SensitivityReport",
    "VisitSchedule",
    "attendance_probability",
    "attrition_funnel",
    "build_report",
    "burden_breakdown",
    "burden_sensitivity",
    "diff_runs",
    "dominant_reason",
    "dropout_probability",
    "experienced_burden",
    "fork",
    "perturbed",
    "retention_summary",
    "run_sensitivity",
    "sign_is_stable",
    "schedule_from_protocol",
    "simulate_cohort",
    "simulate_persona",
    "survival_curve",
]
