"""B-spline basis and penalized P-spline fitting (numpy-first).

Edge handling
-------------
* Knot vectors repeat ``degree + 1`` boundary knots at ``x_min`` and ``x_max``.
* Basis columns are evaluated with half-open intervals ``[t_i, t_{i+1})`` except
  the last interval, which includes ``x_max``.
* ``predict_bspline`` sets ``outside_range=True`` for any query strictly outside
  ``[x_min, x_max]`` (interior domain of the fitted spline). Callers should widen
  uncertainty or refuse extrapolation when this flag is set.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

try:
    from scipy.interpolate import BSpline as _SciBSpline

    _HAS_SCIPY = True
except ImportError:  # pragma: no cover - scipy is a declared dependency
    _HAS_SCIPY = False


def make_knots(x_min: float, x_max: float, n_interior: int, *, degree: int = 3) -> np.ndarray:
    """Build an open uniform knot vector on ``[x_min, x_max]``."""
    if x_max <= x_min:
        raise ValueError("x_max must exceed x_min")
    if n_interior < 0:
        raise ValueError("n_interior must be non-negative")
    if n_interior == 0:
        interior: np.ndarray = np.array([], dtype=float)
    else:
        interior = np.linspace(x_min, x_max, n_interior + 2, dtype=float)[1:-1]
    return np.concatenate(
        [
            np.full(degree + 1, float(x_min)),
            interior,
            np.full(degree + 1, float(x_max)),
        ]
    )


def n_basis_from_knots(knots: np.ndarray, degree: int) -> int:
    return int(len(knots) - degree - 1)


def second_difference_penalty_matrix(n_coeffs: int) -> np.ndarray:
    """RW2-style penalty: squared second differences of coefficient vector."""
    if n_coeffs <= 2:
        return np.zeros((n_coeffs, n_coeffs), dtype=float)
    d2 = np.zeros((n_coeffs - 2, n_coeffs), dtype=float)
    for i in range(n_coeffs - 2):
        d2[i, i] = 1.0
        d2[i, i + 1] = -2.0
        d2[i, i + 2] = 1.0
    return d2.T @ d2


def _de_boor_basis(x: float, knots: np.ndarray, degree: int) -> np.ndarray:
    """Evaluate all B-spline basis functions at a scalar ``x``."""
    n_basis = n_basis_from_knots(knots, degree)
    if _HAS_SCIPY:
        eye = np.eye(n_basis, dtype=float)
        vals = np.empty(n_basis, dtype=float)
        for i in range(n_basis):
            vals[i] = float(_SciBSpline(knots, eye[i], degree, extrapolate=False)(x))
        return vals

    # Pure-numpy Cox–de Boor fallback
    n_knots = len(knots)

    def basis(i: int, k: int, t: float) -> float:
        if k == 0:
            if i >= n_knots - 1:
                return 0.0
            left, right = knots[i], knots[i + 1]
            if left <= t < right:
                return 1.0
            if i == n_knots - 2 and t == right:
                return 1.0
            return 0.0
        denom1 = knots[i + k] - knots[i]
        term1 = 0.0 if denom1 == 0 else ((t - knots[i]) / denom1) * basis(i, k - 1, t)
        denom2 = knots[i + k + 1] - knots[i + 1]
        term2 = 0.0 if denom2 == 0 else ((knots[i + k + 1] - t) / denom2) * basis(i + 1, k - 1, t)
        return term1 + term2

    return np.array([basis(i, degree, x) for i in range(n_basis)], dtype=float)


def bspline_design_matrix(x: np.ndarray, knots: np.ndarray, degree: int = 3) -> np.ndarray:
    """Return design matrix ``B`` with shape ``(len(x), n_basis)``."""
    x_arr = np.asarray(x, dtype=float).ravel()
    n_basis = n_basis_from_knots(knots, degree)
    mat = np.zeros((len(x_arr), n_basis), dtype=float)
    for row, xi in enumerate(x_arr):
        mat[row, :] = _de_boor_basis(float(xi), knots, degree)
    return mat


@dataclass(frozen=True)
class PenalizedBSplineFit:
    coeffs: np.ndarray
    design: np.ndarray
    knots: np.ndarray
    degree: int
    penalty_lambda: float
    x_min: float
    x_max: float
    fitted: np.ndarray


def fit_penalized_bspline(
    x: np.ndarray,
    y: np.ndarray,
    *,
    degree: int = 3,
    n_basis: int = 8,
    lam: float = 1.0,
) -> PenalizedBSplineFit:
    """Fit ``y ≈ B @ beta`` with ridge on second differences (P-spline style)."""
    x_arr = np.asarray(x, dtype=float).ravel()
    y_arr = np.asarray(y, dtype=float).ravel()
    if len(x_arr) != len(y_arr):
        raise ValueError("x and y must have the same length")
    if len(x_arr) < 2:
        raise ValueError("need at least two observations")

    x_min = float(np.min(x_arr))
    x_max = float(np.max(x_arr))
    n_interior = max(0, int(n_basis) - int(degree) - 1)
    knots = make_knots(x_min, x_max, n_interior, degree=degree)
    design = bspline_design_matrix(x_arr, knots, degree=degree)
    penalty = second_difference_penalty_matrix(design.shape[1])
    lhs = design.T @ design + float(lam) * penalty
    rhs = design.T @ y_arr
    coeffs = np.linalg.solve(lhs, rhs)
    fitted = design @ coeffs
    return PenalizedBSplineFit(
        coeffs=coeffs,
        design=design,
        knots=knots,
        degree=degree,
        penalty_lambda=float(lam),
        x_min=x_min,
        x_max=x_max,
        fitted=fitted,
    )


def predict_bspline(
    x: np.ndarray,
    knots: np.ndarray,
    degree: int,
    coeffs: np.ndarray,
    *,
    x_min: float | None = None,
    x_max: float | None = None,
) -> tuple[np.ndarray, np.ndarray]:
    """Predict spline values; return ``(values, outside_range_mask)``."""
    x_arr = np.asarray(x, dtype=float).ravel()
    if x_min is None:
        x_min = float(knots[degree])
    if x_max is None:
        x_max = float(knots[-(degree + 1)])
    outside = (x_arr < x_min) | (x_arr > x_max)
    design = bspline_design_matrix(x_arr, knots, degree=degree)
    values = design @ np.asarray(coeffs, dtype=float).ravel()
    return values, outside
