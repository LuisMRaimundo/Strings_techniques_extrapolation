"""Optional PyMC / ArviZ Bayesian backend."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from string_technique_model.extrapolation.nonlinear.splines import (
    bspline_design_matrix,
    make_knots,
    second_difference_penalty_matrix,
)


@dataclass(frozen=True)
class BayesianBackendStatus:
    available: bool
    status: str
    capability_status: str
    pymc_version: str | None = None
    arviz_version: str | None = None


def check_backend() -> BayesianBackendStatus:
    """Probe optional Bayesian dependencies without faking inference."""
    try:
        import arviz as az
        import pymc as pm
    except ImportError as exc:
        return BayesianBackendStatus(
            available=False,
            status=f"bayesian_backend_unavailable: {exc.__class__.__name__}",
            capability_status="bayesian_backend_unavailable",
        )
    return BayesianBackendStatus(
        available=True,
        status="bayesian_backend_available",
        capability_status="bayesian_backend_available",
        pymc_version=getattr(pm, "__version__", None),
        arviz_version=getattr(az, "__version__", None),
    )


def fit_bayesian_log_ratio_spline(
    x: np.ndarray,
    y: np.ndarray,
    *,
    degree: int = 3,
    n_basis: int = 8,
    sigma_smooth: float = 1.0,
    draws: int = 500,
    tune: int = 500,
    chains: int = 2,
    random_seed: int | None = 42,
) -> dict[str, Any]:
    """Minimal PyMC log-ratio spline; returns unavailable dict if PyMC missing."""
    backend = check_backend()
    if not backend.available:
        return {
            "available": False,
            "capability_status": backend.capability_status,
            "status": backend.status,
            "idata": None,
            "summary": {},
        }

    import pymc as pm

    x_arr = np.asarray(x, dtype=float).ravel()
    y_arr = np.asarray(y, dtype=float).ravel()
    if len(x_arr) < 3:
        return {
            "available": False,
            "capability_status": "insufficient_observations",
            "status": "need_at_least_three_observations",
            "idata": None,
            "summary": {},
        }

    x_min = float(np.min(x_arr))
    x_max = float(np.max(x_arr))
    n_interior = max(0, n_basis - degree - 1)
    knots = make_knots(x_min, x_max, n_interior, degree=degree)
    design = bspline_design_matrix(x_arr, knots, degree=degree)
    n_spline = design.shape[1]
    d2 = second_difference_penalty_matrix(n_spline)
    # RW2-like prior precision from second-difference matrix
    sqrt_prec = np.linalg.cholesky(d2 + np.eye(n_spline) * 1e-8)

    with pm.Model():
        alpha = pm.Normal("alpha", mu=0.0, sigma=1.0)
        beta = pm.Normal("beta", mu=0.0, sigma=1.0 / sigma_smooth, shape=n_spline)
        pm.Potential("rw2_penalty", -0.5 * pm.math.sum((sqrt_prec @ beta) ** 2))
        sigma = pm.HalfNormal("sigma", sigma=1.0)
        mu = alpha + pm.math.dot(design, beta)
        pm.Normal("y", mu=mu, sigma=sigma, observed=y_arr)
        idata = pm.sample(
            draws=draws,
            tune=tune,
            chains=chains,
            random_seed=random_seed,
            progressbar=False,
            return_inferencedata=True,
        )

    summary: dict[str, Any] = {}
    try:
        import arviz as az

        summ = az.summary(idata, var_names=["alpha", "beta", "sigma"])
        summary = summ.to_dict()
    except Exception as exc:  # pragma: no cover
        summary = {"error": str(exc)}

    return {
        "available": True,
        "capability_status": backend.capability_status,
        "status": "fit_completed",
        "idata": idata,
        "summary": summary,
        "knots": knots,
        "degree": degree,
        "design": design,
    }
