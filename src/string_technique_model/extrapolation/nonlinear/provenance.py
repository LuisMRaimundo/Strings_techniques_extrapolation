"""Human-readable calculation trace strings."""

from __future__ import annotations


def trace_baseline_prediction(*, instrument: str, dynamic: str, midi: float, n_obs: int) -> list[str]:
    return [
        f"baseline:instrument={instrument}",
        f"baseline:dynamic={dynamic}",
        f"baseline:midi={midi:.2f}",
        f"baseline:n_obs={n_obs}",
        "baseline:model=log_penalized_bspline_on_midi",
    ]


def trace_log_ratio_prediction(
    *,
    technique: str,
    alpha_t: float,
    n_obs: int,
    prior_dominated: bool,
    register_shape_identified: bool = False,
    model_id: str = "constant_technique_effect_over_smoothed_baseline",
) -> list[str]:
    lines = [
        f"technique={technique}",
        f"model_id={model_id}",
        f"alpha_t={alpha_t:.6f}",
        f"technique_multiplier=exp(alpha_t)={math_exp(alpha_t):.6f}",
        f"target_technique_observations={n_obs}",
        f"register_shape_identified={str(register_shape_identified).lower()}",
        f"g_t_active={str(register_shape_identified).lower()}",
        f"shape_source={'technique_observations_penalized_spline' if register_shape_identified else 'constant_effect'}",
    ]
    if prior_dominated:
        lines.append("prior_dominated=true")
        lines.append("effect_kind=regularization_assumption_or_config_prior")
    else:
        lines.append("effect=empirical_log_ratio_spline")
    if not register_shape_identified:
        lines.append("prediction=Y=B_smoothed(p)*exp(alpha_t)  # g_t(p)=0")
    else:
        lines.append("prediction=Y=B(p)*exp(alpha_t+g_t(p))")
    lines.append("interval=L=B*exp(mu-z*sigma_logR); U=B*exp(mu+z*sigma_logR)")
    return lines


def math_exp(x: float) -> float:
    import math

    return math.exp(float(x))


def trace_mute_prediction(
    *,
    instrument: str,
    alpha_mute: float,
    n_obs: int,
    prior_dominated: bool,
    model_reduction: str,
    register_shape_identified: bool = False,
    model_id: str = "constant_technique_effect_over_smoothed_baseline",
) -> list[str]:
    lines = [
        "technique=con_sordino",
        f"instrument={instrument}",
        f"model_id={model_id}",
        f"alpha_mute={alpha_mute:.6f}",
        f"technique_multiplier=exp(alpha_mute)={math_exp(alpha_mute):.6f}",
        f"target_technique_observations={n_obs}",
        f"model_reduction={model_reduction}",
        f"register_shape_identified={str(register_shape_identified).lower()}",
        f"g_t_active={str(register_shape_identified).lower()}",
        f"shape_source={'technique_observations_penalized_spline' if register_shape_identified else 'constant_effect'}",
    ]
    if prior_dominated:
        lines.append("prior_dominated=true")
        lines.append("effect_kind=user_assumption_power_db_proxy_on_EWSD_scalar")
    if not register_shape_identified:
        lines.append("prediction=Y=B_smoothed(p)*exp(alpha_mute)  # g(p)=0")
    else:
        lines.append("prediction=Y=B(p)*exp(alpha_mute+g(p))")
    lines.append("interval=L=B*exp(mu-z*sigma_logR); U=B*exp(mu+z*sigma_logR)")
    lines.append("not_spectral_transfer_A_m_f")
    return lines


def trace_constant_legacy(*, technique: str, method: str) -> list[str]:
    return [
        f"technique={technique}",
        "submodel=M0_constant_legacy",
        f"method={method}",
        "warning=provisional_config_multiplier",
    ]


def trace_bayesian_backend(*, status: str) -> list[str]:
    return ["backend=physical_informed_bayesian", f"status={status}"]
