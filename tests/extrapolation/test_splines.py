"""Spline construction and penalized fit tests."""

from __future__ import annotations

import numpy as np

from string_technique_model.extrapolation.nonlinear.splines import (
    bspline_design_matrix,
    fit_penalized_bspline,
    make_knots,
    predict_bspline,
    second_difference_penalty_matrix,
)


def test_design_matrix_shape() -> None:
    x = np.linspace(55, 103, 40)
    knots = make_knots(float(x.min()), float(x.max()), n_interior=5)
    X = bspline_design_matrix(x, knots, degree=3)
    assert X.shape[0] == len(x)
    assert X.shape[1] >= 4


def test_penalized_fit_recovers_smooth_curve() -> None:
    rng = np.random.default_rng(0)
    x = np.linspace(40, 90, 50)
    y = np.exp(0.02 * (x - 65)) + rng.normal(0, 0.05, size=len(x))
    fit = fit_penalized_bspline(x, np.log(y), degree=3, n_basis=8, lam=1.0)
    pred, outside = predict_bspline(x, fit.knots, fit.degree, fit.coeffs)
    assert not any(outside)
    assert np.corrcoef(np.exp(pred), y)[0, 1] > 0.9


def test_outside_domain_flagged() -> None:
    x = np.linspace(55, 80, 20)
    y = np.log(np.linspace(10, 5, 20))
    fit = fit_penalized_bspline(x, y, degree=3, n_basis=6, lam=1.0)
    _pred, outside = predict_bspline(np.array([40.0, 100.0]), fit.knots, fit.degree, fit.coeffs)
    assert outside[0] and outside[1]


def test_penalty_matrix_rank() -> None:
    P = second_difference_penalty_matrix(8)
    assert P.shape == (8, 8)
