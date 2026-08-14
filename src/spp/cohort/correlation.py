"""Correlated trait sampling via a Gaussian copula.

Independence is the single biggest realism killer in synthetic populations. Draw
age, comorbidity load, literacy, mobility and caregiver support independently and
you get people who don't exist: 92-year-olds with no comorbidities, full-time
shift workers with high mobility and a live-in carer. Attrition analysis over
that population is confidently wrong.

A Gaussian copula fixes it cheaply and separably:

  1. Draw a correlated standard normal vector  z ~ N(0, R).
  2. Push each component through the normal CDF to get uniforms u = Φ(z).
  3. Feed each u into whatever marginal that trait actually has.

The value is that **the correlation structure and the marginals stay
independent knobs**. Prior packs keep owning the marginals (age is still a
truncated normal per condition); this module only decides how the traits move
together. Recalibrating one never silently rewrites the other.

The correlation matrix is specified as sparse pairwise judgements and repaired to
the nearest valid (positive semi-definite) matrix, because hand-written
correlations are almost never internally consistent — asserting a>b, b>c and c>a
is easy to do by accident and impossible to sample from.
"""
from __future__ import annotations

import math
from typing import NamedTuple

import numpy as np

# Trait axes the copula couples. Order is fixed and load-bearing: it indexes the
# correlation matrix and the sampled vector.
TRAIT_AXES: tuple[str, ...] = (
    "age",
    "comorbidity_load",
    "health_literacy",
    "digital_literacy",
    "mobility",
    "caregiver_support",
    "transport_access",
    "financial_security",
)

AXIS_INDEX: dict[str, int] = {name: i for i, name in enumerate(TRAIT_AXES)}


MIN_EIGENVALUE = 1e-6


class NotPositiveDefinite(ValueError):
    """The specified correlations are mutually inconsistent.

    Carries the offending eigenvalue and the axes carrying the most weight in the
    offending eigenvector, so the message points at which judgements to revisit.
    """

    def __init__(self, min_eigenvalue: float, culprits: list[tuple[str, float]]) -> None:
        blame = ", ".join(f"{axis} ({weight:+.2f})" for axis, weight in culprits)
        super().__init__(
            f"correlation matrix is not positive definite "
            f"(min eigenvalue {min_eigenvalue:.2e} < {MIN_EIGENVALUE:.0e}). "
            f"The inconsistency loads most on: {blame}. "
            "Revisit those pairs — do not project, or the ledger number will stop "
            "matching the sampled correlation."
        )
        self.min_eigenvalue = min_eigenvalue
        self.culprits = culprits


class PairCorrection(NamedTuple):
    """One entry moved by an explicit PSD projection."""

    axis_a: str
    axis_b: str
    specified: float
    projected: float

    @property
    def delta(self) -> float:
        return round(self.projected - self.specified, 6)

    def describe(self) -> str:
        return (
            f"{self.axis_a}|{self.axis_b}: {self.specified:+.3f} -> "
            f"{self.projected:+.3f} ({self.delta:+.3f})"
        )


def assemble_matrix(
    pairs: dict[tuple[str, str], float], axes: tuple[str, ...] = TRAIT_AXES
) -> np.ndarray:
    """Sparse pairwise judgements -> full matrix. No repair, no validation."""
    index = {name: i for i, name in enumerate(axes)}
    matrix = np.eye(len(axes))

    for (left, right), value in pairs.items():
        if left not in index or right not in index:
            raise KeyError(f"unknown trait axis in pair {(left, right)!r}")
        if not -1.0 <= value <= 1.0:
            raise ValueError(f"correlation {value} for {(left, right)} is out of range")
        i, j = index[left], index[right]
        matrix[i, j] = matrix[j, i] = value
    return matrix


def build_correlation_matrix(
    pairs: dict[tuple[str, str], float],
    axes: tuple[str, ...] = TRAIT_AXES,
    *,
    allow_projection: bool = False,
    min_eigenvalue: float = MIN_EIGENVALUE,
) -> tuple[np.ndarray, list[PairCorrection]]:
    """Assemble and gate a correlation matrix. Returns (matrix, corrections).

    **An unspecified pair is asserted uncorrelated, not "unconstrained".** This
    is the easy mistake here: correlation does not propagate through a
    correlation matrix, so declaring a~b and b~c does NOT give you a~c. (Zeros
    imply *conditional* independence in the precision matrix — the inverse — not
    in this one.) If two traits should move together, even indirectly, list the
    pair.

    **The matrix is gated, not silently repaired.** A hand-specified matrix with
    this many strong entries goes non-positive-definite easily — one more tweak
    can do it — and quietly projecting to the nearest PSD matrix would move
    entries, breaking the invariant that the ledger number *is* the latent
    correlation being sampled. So the default is to fail loudly with a diagnostic.

    `allow_projection=True` is available but never silent: it returns the exact
    list of pairs that moved and by how much, and the caller is expected to record
    that in the ledger as a correction. A projection you did not read is a
    correlation structure you no longer specify.

    Returns the LATENT Gaussian correlation matrix. Correlations measured on the
    generated cohort will read lower — see `uniform_pearson`.
    """
    matrix = assemble_matrix(pairs, axes)
    eigenvalues, eigenvectors = np.linalg.eigh((matrix + matrix.T) / 2.0)
    smallest = float(eigenvalues[0])

    if smallest >= min_eigenvalue:
        return matrix, []

    if not allow_projection:
        # Blame the axes loading hardest on the offending eigenvector.
        loadings = eigenvectors[:, 0]
        ranked = sorted(
            ((axes[i], float(loadings[i])) for i in range(len(axes))),
            key=lambda pair: -abs(pair[1]),
        )
        raise NotPositiveDefinite(smallest, ranked[:3])

    projected = nearest_positive_definite(matrix, epsilon=min_eigenvalue)
    corrections = [
        PairCorrection(left, right, value, round(float(projected[
            axes.index(left), axes.index(right)]), 6))
        for (left, right), value in sorted(pairs.items())
        if abs(projected[axes.index(left), axes.index(right)] - value) > 1e-9
    ]
    return projected, corrections


def nearest_positive_definite(matrix: np.ndarray, epsilon: float = 1e-8) -> np.ndarray:
    """Clip negative eigenvalues and renormalise to unit diagonal.

    Cheap standard repair. Exact enough for correlations that are expert
    judgement to one decimal place in the first place.
    """
    symmetric = (matrix + matrix.T) / 2.0
    eigenvalues, eigenvectors = np.linalg.eigh(symmetric)

    if (eigenvalues >= epsilon).all():
        return symmetric

    repaired = eigenvectors @ np.diag(np.clip(eigenvalues, epsilon, None)) @ eigenvectors.T
    # Renormalise so the diagonal is exactly 1 — it is a *correlation* matrix.
    scale = np.sqrt(np.diag(repaired))
    repaired = repaired / np.outer(scale, scale)
    np.fill_diagonal(repaired, 1.0)
    return (repaired + repaired.T) / 2.0


def is_positive_definite(matrix: np.ndarray, epsilon: float = 1e-10) -> bool:
    return bool((np.linalg.eigvalsh((matrix + matrix.T) / 2.0) >= -epsilon).all())


def uniform_pearson(rho: float) -> float:
    """Pearson correlation of the copula's UNIFORMS given latent Gaussian `rho`.

        r_uniform = (6 / pi) * arcsin(rho / 2)

    Ledger numbers are latent Gaussian correlations. Pushing them through the
    copula attenuates the measurable correlation even before any marginal is
    applied — rho=0.45 reads as 0.4334 on the uniforms — and discretising into a
    categorical or count marginal attenuates it much further again.

    This is expected and quantified, not error. It is also why tests assert at
    the latent/uniform level: asserting a realized correlation on a discrete
    marginal while specifying a latent one would need a tolerance wide enough to
    swallow a genuine semantic mistake.
    """
    return (6.0 / math.pi) * math.asin(rho / 2.0)


def _standard_normal_cdf(values: np.ndarray) -> np.ndarray:
    """Φ, via math.erf. Avoids a scipy dependency for one function."""
    return np.array([0.5 * (1.0 + math.erf(v / math.sqrt(2.0))) for v in values])


class CopulaSampler:
    """Draws correlated uniforms in [0, 1), one vector per persona.

    Correlation is *within* a persona across traits, never across personas — so
    each persona is still an independent draw and per-persona seed isolation
    (see foundation/rng.py) survives intact. That matters: it is what lets a
    single persona be re-simulated on its own and come out identical.
    """

    def __init__(self, matrix: np.ndarray, axes: tuple[str, ...] = TRAIT_AXES) -> None:
        if matrix.shape != (len(axes), len(axes)):
            raise ValueError(
                f"matrix is {matrix.shape}, expected {(len(axes), len(axes))}"
            )
        self.axes = axes
        self.matrix = matrix
        # Cholesky needs strict positive definiteness; nudge the diagonal if the
        # repaired matrix sits exactly on the boundary.
        try:
            self._chol = np.linalg.cholesky(matrix)
        except np.linalg.LinAlgError:
            self._chol = np.linalg.cholesky(matrix + np.eye(len(axes)) * 1e-6)

    def draw(self, rng: np.random.Generator) -> dict[str, float]:
        """One persona's correlated uniforms, keyed by trait name.

        Higher is 'more' in the direction the axis is named: higher
        `caregiver_support` means better supported, higher `comorbidity_load`
        means sicker. Keep that convention — the correlation signs assume it.
        """
        normals = self._chol @ rng.standard_normal(len(self.axes))
        uniforms = _standard_normal_cdf(normals)
        return dict(zip(self.axes, (float(u) for u in uniforms)))


def uniform_to_choice(u: float, weights: dict[str, float]) -> str:
    """Invert a categorical marginal at quantile `u`.

    Insertion order of `weights` defines the ordinal direction, so a trait axis
    correlates sensibly with the category it selects.
    """
    total = math.fsum(weights.values())
    if total <= 0:
        raise ValueError("weights must sum to a positive number")

    cumulative = 0.0
    for name, weight in weights.items():
        cumulative += weight / total
        if u < cumulative:
            return name
    return next(reversed(weights))


def uniform_to_normal(u: float, mean: float, sd: float, lo: float, hi: float) -> float:
    """Invert a bounded normal marginal at quantile `u`.

    Uses a rational approximation to the normal quantile function (Acklam), then
    clamps. Quantile inversion rather than rejection sampling because the copula
    hands us a *specific* quantile — rejecting and redrawing would discard
    exactly the correlation we went to the trouble of creating.
    """
    u = min(max(u, 1e-9), 1 - 1e-9)
    z = _normal_quantile(u)
    return float(min(max(mean + sd * z, lo), hi))


# Acklam's inverse-normal-CDF approximation. |error| < 1.15e-9 over (0, 1).
_A = (-3.969683028665376e01, 2.209460984245205e02, -2.759285104469687e02,
      1.383577518672690e02, -3.066479806614716e01, 2.506628277459239e00)
_B = (-5.447609879822406e01, 1.615858368580409e02, -1.556989798598866e02,
      6.680131188771972e01, -1.328068155288572e01)
_C = (-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e00,
      -2.549732539343734e00, 4.374664141464968e00, 2.938163982698783e00)
_D = (7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e00,
      3.754408661907416e00)
_P_LOW, _P_HIGH = 0.02425, 1 - 0.02425


def _normal_quantile(p: float) -> float:
    if p < _P_LOW:
        q = math.sqrt(-2 * math.log(p))
        return (((((_C[0] * q + _C[1]) * q + _C[2]) * q + _C[3]) * q + _C[4]) * q + _C[5]) / \
               ((((_D[0] * q + _D[1]) * q + _D[2]) * q + _D[3]) * q + 1)
    if p > _P_HIGH:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((_C[0] * q + _C[1]) * q + _C[2]) * q + _C[3]) * q + _C[4]) * q + _C[5]) / \
                ((((_D[0] * q + _D[1]) * q + _D[2]) * q + _D[3]) * q + 1)
    q = p - 0.5
    r = q * q
    return (((((_A[0] * r + _A[1]) * r + _A[2]) * r + _A[3]) * r + _A[4]) * r + _A[5]) * q / \
           (((((_B[0] * r + _B[1]) * r + _B[2]) * r + _B[3]) * r + _B[4]) * r + 1)
