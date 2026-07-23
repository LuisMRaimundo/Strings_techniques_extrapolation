"""Convergence and diagnostic status helpers."""

from __future__ import annotations

from typing import Any

from string_technique_model.extrapolation.nonlinear.domain import ConvergenceStatus, PosteriorDiagnostic


def from_rhat_ess(
    *,
    rhat_max: float | None,
    ess_bulk_min: float | None,
    ess_tail_min: float | None = None,
    divergences: int | None = None,
    rhat_threshold: float = 1.01,
    ess_threshold: float = 400.0,
) -> ConvergenceStatus:
    if rhat_max is None and ess_bulk_min is None:
        return ConvergenceStatus.NOT_APPLICABLE
    flags: list[str] = []
    if rhat_max is not None and rhat_max > rhat_threshold:
        flags.append("rhat_above_threshold")
    if ess_bulk_min is not None and ess_bulk_min < ess_threshold:
        flags.append("ess_below_threshold")
    if ess_tail_min is not None and ess_tail_min < ess_threshold:
        flags.append("ess_tail_below_threshold")
    if divergences:
        flags.append("divergences_present")
    if flags:
        return ConvergenceStatus.DIVERGED
    return ConvergenceStatus.CONVERGED


def from_frequentist_flags(
    *,
    outside_range: bool = False,
    prior_dominated: bool = False,
    insufficient_data: bool = False,
) -> ConvergenceStatus:
    if insufficient_data:
        return ConvergenceStatus.APPROXIMATE_FREQUENTIST
    if outside_range or prior_dominated:
        return ConvergenceStatus.APPROXIMATE_FREQUENTIST
    return ConvergenceStatus.APPROXIMATE_FREQUENTIST


def summarize_idata(idata: Any) -> PosteriorDiagnostic:
    if idata is None:
        return PosteriorDiagnostic(flags=["no_idata"])
    try:
        import arviz as az
    except ImportError:
        return PosteriorDiagnostic(flags=["arviz_unavailable"])

    summ = az.summary(idata)
    rhat_max = float(summ["r_hat"].max()) if "r_hat" in summ.columns else None
    ess_bulk_min = float(summ["ess_bulk"].min()) if "ess_bulk" in summ.columns else None
    ess_tail_min = float(summ["ess_tail"].min()) if "ess_tail" in summ.columns else None
    flags: list[str] = []
    if rhat_max and rhat_max > 1.01:
        flags.append("rhat_above_threshold")
    if ess_bulk_min and ess_bulk_min < 400:
        flags.append("ess_below_threshold")
    return PosteriorDiagnostic(
        rhat_max=rhat_max,
        ess_bulk_min=ess_bulk_min,
        ess_tail_min=ess_tail_min,
        flags=flags,
    )
