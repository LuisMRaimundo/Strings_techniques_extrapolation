"""Uncertainty sampling stress tests."""

from __future__ import annotations

import numpy as np
import pytest

from string_technique_model.prediction.uncertainty import sample_baseline_density

pytestmark = pytest.mark.acoustics_stress


@pytest.mark.mathematical_exact
def test_zero_uncertainty_is_point_mass() -> None:
    rng = np.random.default_rng(0)
    draws = sample_baseline_density(
        {"baseline_mean": 20.0, "baseline_sd": 0.0, "baseline_value": 20.0},
        n_draws=100,
        rng=rng,
    )
    assert np.allclose(draws, 20.0)


@pytest.mark.mathematical_exact
def test_missing_uncertainty_is_point_mass_not_hidden_default() -> None:
    rng = np.random.default_rng(1)
    draws = sample_baseline_density({"baseline_value": 12.5}, n_draws=50, rng=rng)
    assert np.allclose(draws, 12.5)


@pytest.mark.reproducibility
def test_baseline_sampling_reproducible_with_seed() -> None:
    a = sample_baseline_density(
        {"baseline_mean": 10.0, "baseline_sd": 1.0},
        n_draws=200,
        rng=np.random.default_rng(123),
    )
    b = sample_baseline_density(
        {"baseline_mean": 10.0, "baseline_sd": 1.0},
        n_draws=200,
        rng=np.random.default_rng(123),
    )
    assert np.allclose(a, b)


@pytest.mark.domain_boundary
def test_positive_sd_produces_dispersion() -> None:
    draws = sample_baseline_density(
        {"baseline_mean": 10.0, "baseline_sd": 2.0},
        n_draws=2000,
        rng=np.random.default_rng(0),
    )
    assert float(np.std(draws)) > 0.5
