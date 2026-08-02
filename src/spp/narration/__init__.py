"""Narration: the only nondeterministic layer, quarantined behind contracts.

Prompt building is pure and golden-tested. Model calls go through record/replay
cassettes. Citation verification is code, never a model judging a model. The
null backend keeps the whole pipeline runnable — and CI-tested — offline.
"""
from .cassette import (
    Cassette,
    CassetteAdapter,
    CassetteMismatch,
    CassetteMiss,
    GatedRecorder,
    Take,
)
from .evaluation import ComplianceReport, run_canary, score
from .structured import (
    Segment,
    StructuredAnswer,
    answer_schema,
    check_structured,
    parse_structured,
)
from .citations import (
    CitationCheck,
    GroundingFailure,
    check_citations,
    extract_citations,
    is_factual,
    strip_citations,
)
from .panel import (
    PanelStatement,
    PanelTranscript,
    Theme,
    extract_themes,
    run_panel,
    should_probe,
    speaking_order,
)
from .interview import InterviewTurn, citation_skeleton, interview
from .prompt import Prompt, build_prompt, prior_turns, render_state

__all__ = [
    "Cassette",
    "ComplianceReport",
    "GatedRecorder",
    "Segment",
    "StructuredAnswer",
    "CassetteAdapter",
    "CassetteMismatch",
    "CassetteMiss",
    "CitationCheck",
    "GroundingFailure",
    "InterviewTurn",
    "PanelStatement",
    "PanelTranscript",
    "Theme",
    "Prompt",
    "Take",
    "answer_schema",
    "build_prompt",
    "check_citations",
    "check_structured",
    "citation_skeleton",
    "extract_citations",
    "extract_themes",
    "interview",
    "is_factual",
    "parse_structured",
    "prior_turns",
    "run_canary",
    "score",
    "render_state",
    "run_panel",
    "should_probe",
    "speaking_order",
    "strip_citations",
]
