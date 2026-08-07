"""Protocol CI — the gate you can't ship past.

Packaging, not new capability: the existing counterfactual engine re-shaped as a
CLI, a baseline contract, a verdict, and CI glue. **Pure core** — nothing on this
path may call the LLM adapter, and a test enforces that rather than a comment.
"""
from .baseline import (
    Baseline,
    ConfigStamp,
    IncompatibleBaseline,
    build_baseline,
    diff_summary,
    read_baseline,
    write_baseline,
)
from .render import COMMENT_MARKER, render_annotations, render_markdown
from .scenario_file import (
    ENGINE_VERSION,
    ScenarioError,
    ScenarioFile,
    VisitSpec,
    discover_scenarios,
    dump_scenario,
    load_scenario,
)
from .verdict import Gates, Verdict, evaluate, write_verdict

__all__ = [
    "COMMENT_MARKER", "Baseline", "ConfigStamp", "ENGINE_VERSION", "Gates",
    "IncompatibleBaseline", "ScenarioError", "ScenarioFile", "Verdict",
    "VisitSpec", "build_baseline", "diff_summary", "discover_scenarios",
    "dump_scenario", "evaluate", "load_scenario", "read_baseline",
    "render_annotations", "render_markdown", "write_baseline", "write_verdict",
]
