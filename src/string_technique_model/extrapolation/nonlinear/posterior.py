"""Posterior / approximate predictive summaries."""

from __future__ import annotations

import math
from typing import Any

from string_technique_model.extrapolation.nonlinear.domain import PosteriorPrediction

_Z95 = 1.959963984540054

LOG_RATIO_INTERVAL_FORMULA = (
    "L=B*exp(mu_logR - z*sigma_logR); U=B*exp(mu_logR + z*sigma_logR); "
    "z=1.95996398454 for nominal 95%; uncertainty belongs to logR"
)


def summarize_frequentist(
    mean: float,
    sd: float | None = None,
    *,
    baseline_mean: float | None = None,
) -> PosteriorPrediction:
    """Legacy additive interval on the original scale (M0 / non-log paths)."""
    sd_val = float(sd) if sd is not None and sd > 0 else float("nan")
    if math.isnan(sd_val):
        lo = hi = None
    else:
        half = _Z95 * sd_val
        lo, hi = float(mean) - half, float(mean) + half
    prob_above = None
    if baseline_mean is not None and sd_val and not math.isnan(sd_val) and sd_val > 0:
        z = (float(mean) - float(baseline_mean)) / sd_val
        prob_above = 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))
    return PosteriorPrediction(
        mean=float(mean),
        median=float(mean),
        sd=None if math.isnan(sd_val) else sd_val,
        credible_interval_low=lo,
        credible_interval_high=hi,
        credible_level=0.95,
        interval_kind="approximate_additive_interval_original_scale",
        interval_formula="L=mean-z*sd; U=mean+z*sd (legacy additive; not preferred for logR models)",
        probability_above_ordinary=prob_above,
    )


def summarize_log_ratio_multiplicative(
    *,
    baseline: float,
    log_ratio_mean: float,
    log_ratio_sd: float | None,
    level: float = 0.95,
    prior_dominated: bool = False,
    sigma_origin: str | None = None,
) -> PosteriorPrediction:
    """Multiplicative interval when uncertainty lives on log R.

    When prior-dominated / assumption-based, these are **assumption distribution
    intervals**, not confidence or posterior credible intervals.
    """
    b = float(baseline)
    mu = float(log_ratio_mean)
    mean_y = b * math.exp(mu)
    sd = float(log_ratio_sd) if log_ratio_sd is not None and log_ratio_sd > 0 else float("nan")
    z = _Z95 if abs(level - 0.95) < 1e-9 else 1.96
    if math.isnan(sd):
        lo = hi = None
        y_sd = None
        prob_above = None
    else:
        lo = b * math.exp(mu - z * sd)
        hi = b * math.exp(mu + z * sd)
        y_sd = mean_y * sd
        prob_above = 0.5 * (1.0 + math.erf((mu / sd) / math.sqrt(2.0)))

    if prior_dominated:
        interval_kind = "assumption_distribution_interval"
        interval_type = "assumption_distribution_interval"
    else:
        interval_kind = "multiplicative_from_logR_normal"
        interval_type = "approximate_predictive_interval_logR"
    _ = sigma_origin  # documented via apply_posterior_to_result

    return PosteriorPrediction(
        mean=mean_y,
        median=mean_y,
        sd=y_sd,
        log_ratio_mean=mu,
        log_ratio_sd=None if math.isnan(sd) else sd,
        credible_interval_low=lo,
        credible_interval_high=hi,
        credible_level=level,
        interval_kind=interval_kind,
        interval_formula=LOG_RATIO_INTERVAL_FORMULA
        + f"; interval_type={interval_type}; NOT a classical confidence interval",
        probability_above_ordinary=prob_above,
    )


def summarize_bayesian_idata(idata: Any, *, var_name: str = "alpha") -> PosteriorPrediction | None:
    """Summarize ArviZ InferenceData when backend available."""
    if idata is None:
        return None
    try:
        import arviz as az
    except ImportError:
        return None

    summ = az.summary(idata, var_names=[var_name])
    if var_name not in summ.index:
        return None
    row = summ.loc[var_name]
    mean = float(row["mean"])
    sd = float(row["sd"])
    lo = float(row.get("hdi_3%", row["mean"] - 1.96 * sd))
    hi = float(row.get("hdi_97%", row["mean"] + 1.96 * sd))
    return PosteriorPrediction(
        mean=mean,
        median=float(row.get("median", mean)),
        sd=sd,
        credible_interval_low=lo,
        credible_interval_high=hi,
        credible_level=0.94,
        interval_kind="bayesian_hdi_from_arviz",
        interval_formula="ArviZ HDI on sampled parameter",
        probability_above_ordinary=None,
    )


def apply_posterior_to_result(
    pred: PosteriorPrediction,
    *,
    prior_dominated: bool = False,
    sigma_origin: str | None = None,
    sigma_value: float | None = None,
    sigma_estimated_from_data: bool | None = None,
) -> dict[str, Any]:
    interval_type = pred.interval_kind
    if prior_dominated or (pred.interval_kind or "").startswith("assumption_"):
        interval_type = "assumption_distribution_interval"
    return {
        "posterior_mean": pred.mean,
        "posterior_median": pred.median,
        "posterior_sd": pred.sd,
        "log_ratio_mean": pred.log_ratio_mean,
        "log_ratio_sd": pred.log_ratio_sd,
        "credible_interval_low": pred.credible_interval_low,
        "credible_interval_high": pred.credible_interval_high,
        "probability_above_ordinary": pred.probability_above_ordinary,
        "interval_kind": pred.interval_kind,
        "interval_type": interval_type,
        "interval_formula": pred.interval_formula,
        "credible_interval_probability": pred.credible_level,
        "sigma_origin": sigma_origin
        or (
            "prior_config_alpha_sd_not_estimated_from_data"
            if prior_dominated
            else "logR_uncertainty"
        ),
        "sigma_value": sigma_value if sigma_value is not None else pred.log_ratio_sd,
        "sigma_estimated_from_data": (
            False if prior_dominated else (True if sigma_estimated_from_data is None else sigma_estimated_from_data)
        ),
    }
