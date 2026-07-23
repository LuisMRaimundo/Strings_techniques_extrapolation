"""Log-ratio / posterior summary math tests."""

from __future__ import annotations

import math

from string_technique_model.extrapolation.nonlinear.posterior import (
    summarize_frequentist,
    summarize_log_ratio_multiplicative,
)


def test_log_exp_roundtrip_identity() -> None:
    y = 12.5
    assert math.isclose(math.exp(math.log(y)), y)


def test_technique_ordinary_ratio() -> None:
    baseline = 10.0
    log_r = 0.2
    y = baseline * math.exp(log_r)
    assert math.isclose(math.log(y / baseline), log_r)


def test_multiplicative_logR_intervals_scale_with_baseline() -> None:
    p_low = summarize_log_ratio_multiplicative(
        baseline=10.0, log_ratio_mean=-0.12, log_ratio_sd=0.5, prior_dominated=True
    )
    p_high = summarize_log_ratio_multiplicative(
        baseline=40.0, log_ratio_mean=-0.12, log_ratio_sd=0.5, prior_dominated=True
    )
    assert p_low.credible_interval_low is not None and p_high.credible_interval_low is not None
    assert p_low.credible_interval_high is not None and p_high.credible_interval_high is not None
    # Absolute half-width scales with B; relative width similar
    half_low = p_low.credible_interval_high - p_low.mean  # type: ignore[operator]
    half_high = p_high.credible_interval_high - p_high.mean  # type: ignore[operator]
    assert half_high > half_low
    rel_low = half_low / p_low.mean  # type: ignore[operator]
    rel_high = half_high / p_high.mean  # type: ignore[operator]
    assert math.isclose(rel_low, rel_high, rel_tol=1e-9)
    assert p_low.interval_kind == "assumption_distribution_interval"
    assert p_low.credible_interval_low > 0


def test_summarize_frequentist_legacy_additive() -> None:
    p = summarize_frequentist(10.0, 2.0, baseline_mean=8.0)
    assert p.interval_kind == "approximate_additive_interval_original_scale"
