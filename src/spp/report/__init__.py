"""Product surface: rendered artifacts. Pure reads, never recomputation."""
from .compare import CohortComparison, MarginalComparison, compare_cohorts
from .diffwalk import ArtifactDiff, LeafChange, diff_artifacts, walk_leaves
from .html import render_counterfactual
from .studio import MarginalBand, StudioView, studio_view

__all__ = [
    "ArtifactDiff", "CohortComparison", "LeafChange", "MarginalBand",
    "MarginalComparison", "StudioView", "compare_cohorts", "diff_artifacts",
    "render_counterfactual", "studio_view", "walk_leaves",
]
