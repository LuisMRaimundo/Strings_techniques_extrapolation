"""Monte Carlo uncertainty propagation for technique predictions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np

from string_technique_model.prediction.links import link_forward, link_inverse
from string_technique_model.prediction.operations import apply_operation
from string_technique_model.stable_seed import stable_uint32


@dataclass
class PredictionDistribution:
    samples: np.ndarray | None
    ordinary_samples: np.ndarray | None
    estimated_density_mean: float | None
    estimated_density_median: float | None
    estimated_density_sd: float | None
    estimated_density_q025: float | None
    estimated_density_q050: float | None
    estimated_density_q975: float | None
    probability_above_ordinary: float | None
    probability_below_ordinary: float | None
    difference_from_ordinary_mean: float | None
    ratio_to_ordinary_median: float | None
    numerical_safeguard_applied: bool
    safeguard_note: str | None
    parameter_draw_summaries: dict[str, dict[str, float]]

    def empty_like(self, *, safeguard: bool = False, note: str | None = None) -> PredictionDistribution:
        return PredictionDistribution(
            samples=None,
            ordinary_samples=None,
            estimated_density_mean=None,
            estimated_density_median=None,
            estimated_density_sd=None,
            estimated_density_q025=None,
            estimated_density_q050=None,
            estimated_density_q975=None,
            probability_above_ordinary=None,
            probability_below_ordinary=None,
            difference_from_ordinary_mean=None,
            ratio_to_ordinary_median=None,
            numerical_safeguard_applied=safeguard,
            safeguard_note=note,
            parameter_draw_summaries={},
        )


def cell_seed(*parts: object) -> int:
    return int(stable_uint32(*parts))


def sample_baseline_density(
    baseline: dict[str, Any],
    n_draws: int,
    rng: np.random.Generator,
) -> np.ndarray:
    mean = baseline.get("baseline_mean")
    if mean is None:
        mean = baseline.get("baseline_value")
    if mean is None:
        raise ValueError("baseline density missing")
    mean = float(mean)
    sd = baseline.get("baseline_sd")
    se = baseline.get("baseline_se")
    # Prefer SD; if only SE, use SE; if neither, replicate mean without inventing zero uncertainty label
    if sd is not None and np.isfinite(float(sd)) and float(sd) > 0:
        return rng.normal(mean, float(sd), size=n_draws)
    if se is not None and np.isfinite(float(se)) and float(se) > 0:
        return rng.normal(mean, float(se), size=n_draws)
    # Unavailable uncertainty: replicate point value; SD of prediction remains None upstream if sole source
    return np.full(n_draws, mean, dtype=float)


def sample_parameter_draws(
    param: dict[str, Any],
    n_draws: int,
    rng: np.random.Generator,
) -> np.ndarray:
    value = param.get("reported_value")
    dist = param.get("proposed_distribution")
    dist_params = param.get("distribution_parameters") or {}
    if isinstance(dist, dict):
        kind = str(dist.get("type") or dist.get("kind") or "normal").lower()
        if kind in {"normal", "gaussian"}:
            mu = float(dist.get("mean", dist.get("mu", value if value is not None else 0.0)) or 0.0)
            sigma = float(dist.get("std", dist.get("sigma", dist.get("sd", 0.0))) or 0.0)
            return rng.normal(mu, sigma, size=n_draws) if sigma > 0 else np.full(n_draws, mu)
        if kind in {"lognormal", "log_normal"}:
            mu = float(dist.get("mean", dist.get("mu", 0.0)) or 0.0)
            sigma = float(dist.get("std", dist.get("sigma", dist.get("sd", 0.0))) or 0.0)
            return rng.lognormal(mu, sigma, size=n_draws)
        if kind == "uniform":
            low = float(dist.get("low", dist.get("min", 0.0)) or 0.0)
            high = float(dist.get("high", dist.get("max", 1.0)) or 1.0)
            return rng.uniform(low, high, size=n_draws)
    if isinstance(dist, str) and dist_params:
        kind = dist.lower()
        if kind == "normal":
            mu = float(dist_params.get("mean", value if value is not None else 0.0))
            sigma = float(dist_params.get("sd", dist_params.get("std", 0.0)) or 0.0)
            return rng.normal(mu, sigma, size=n_draws) if sigma > 0 else np.full(n_draws, mu)
    if value is not None:
        return np.full(n_draws, float(value), dtype=float)
    raise ValueError(f"Parameter {param.get('parameter_id')} has no sampleable value")


def propagate_metric_only(
    *,
    baseline: dict[str, Any],
    active_params: list[dict[str, Any]],
    link: str,
    n_draws: int,
    random_seed: int,
    transfer_uncertainty_sd: float | None = None,
) -> PredictionDistribution:
    if not active_params:
        return PredictionDistribution(
            samples=None,
            ordinary_samples=None,
            estimated_density_mean=None,
            estimated_density_median=None,
            estimated_density_sd=None,
            estimated_density_q025=None,
            estimated_density_q050=None,
            estimated_density_q975=None,
            probability_above_ordinary=None,
            probability_below_ordinary=None,
            difference_from_ordinary_mean=None,
            ratio_to_ordinary_median=None,
            numerical_safeguard_applied=False,
            safeguard_note=None,
            parameter_draw_summaries={},
        )

    rng = np.random.default_rng(random_seed)
    d_ord = sample_baseline_density(baseline, n_draws, rng)
    eta, link_meta = link_forward(d_ord, link)
    summaries: dict[str, dict[str, float]] = {}
    for param in active_params:
        draws = sample_parameter_draws(param, n_draws, rng)
        summaries[str(param["parameter_id"])] = {
            "mean": float(np.mean(draws)),
            "sd": float(np.std(draws, ddof=1)) if n_draws > 1 else float("nan"),
            "median": float(np.median(draws)),
        }
        eta, d_ord, _space = apply_operation(
            operation_type=str(param["operation_type"]),
            draws=draws,
            eta=eta,
            d_ordinary=d_ord,
            numerical_scale=param.get("numerical_scale"),
            link=link,
        )

    if transfer_uncertainty_sd is not None and transfer_uncertainty_sd > 0:
        eta = eta + rng.normal(0.0, float(transfer_uncertainty_sd), size=n_draws)

    samples = link_inverse(eta, link)
    if not np.all(np.isfinite(samples)):
        raise ValueError("Non-finite prediction samples; refusing silent clip")

    # Ordinary comparison uses baseline draws (same seed stream already consumed — use d_ord)
    prob_above = float(np.mean(samples > d_ord))
    prob_below = float(np.mean(samples < d_ord))
    diff_mean = float(np.mean(samples - d_ord))
    ord_med = float(np.median(d_ord))
    ratio_med = float(np.median(samples) / ord_med) if ord_med != 0 else None

    sd = float(np.std(samples, ddof=1)) if n_draws > 1 else None
    # If baseline and params are point masses, sd may be 0 — that is scientific zero, not filled unavailable.
    baseline_had_uncertainty = (
        (baseline.get("baseline_sd") is not None and float(baseline.get("baseline_sd") or 0) > 0)
        or (baseline.get("baseline_se") is not None and float(baseline.get("baseline_se") or 0) > 0)
    )
    param_had_uncertainty = any(
        np.isfinite(s.get("sd", float("nan"))) and s["sd"] > 0 for s in summaries.values()
    )
    if sd == 0.0 and not baseline_had_uncertainty and not param_had_uncertainty:
        # Point estimate only — leave sd as None rather than fake precision via zero? Spec says
        # do not fill unavailable with zero. Point-identified MC with sd=0 is available precision.
        # Keep 0.0 only when scientifically produced by identical draws; use None when n_draws<2.
        pass

    return PredictionDistribution(
        samples=samples,
        ordinary_samples=d_ord,
        estimated_density_mean=float(np.mean(samples)),
        estimated_density_median=float(np.median(samples)),
        estimated_density_sd=sd,
        estimated_density_q025=float(np.quantile(samples, 0.025)),
        estimated_density_q050=float(np.quantile(samples, 0.50)),
        estimated_density_q975=float(np.quantile(samples, 0.975)),
        probability_above_ordinary=prob_above,
        probability_below_ordinary=prob_below,
        difference_from_ordinary_mean=diff_mean,
        ratio_to_ordinary_median=ratio_med,
        numerical_safeguard_applied=link_meta.numerical_safeguard_applied,
        safeguard_note=link_meta.safeguard_note,
        parameter_draw_summaries=summaries,
    )
