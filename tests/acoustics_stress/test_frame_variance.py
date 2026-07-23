"""Frame-level spectral variance (temporal) vs within-frame spread."""

from __future__ import annotations

import numpy as np
import pytest

from string_technique_model.descriptors.models import load_analysis_profile
from string_technique_model.descriptors.variance import METHOD_ID, compute_frame_spectral_variance
from string_technique_model.testing.descriptor_asserts import assert_provenance
from string_technique_model.testing.signal_generators import generate_signal

pytestmark = pytest.mark.acoustics_stress


@pytest.mark.mathematical_exact
def test_variance_method_is_temporal_centroid() -> None:
    sig = generate_signal("harmonic_sum", duration_s=0.5, frequency_hz=196.0, n_harmonics=6)
    result = compute_frame_spectral_variance(
        sig.samples,
        measurement_domain="radiated_audio",
        sample_rate=sig.sample_rate_hz,
        profile=load_analysis_profile(),
    )
    assert_provenance(result)
    assert result.method_id == METHOD_ID
    assert result.extras["distinction"] == "temporal_variance_of_centroids_not_within_frame_spread"


@pytest.mark.metamorphic
def test_stationary_lower_than_alternating() -> None:
    profile = load_analysis_profile()
    stationary = generate_signal("harmonic_sum", duration_s=0.7, frequency_hz=220.0, n_harmonics=6)
    alternating = generate_signal("alternating_tones", duration_s=0.7, f1_hz=400.0, f2_hz=1800.0)
    v_stat = compute_frame_spectral_variance(
        stationary.samples,
        measurement_domain="radiated_audio",
        sample_rate=stationary.sample_rate_hz,
        profile=profile,
    )
    v_alt = compute_frame_spectral_variance(
        alternating.samples,
        measurement_domain="radiated_audio",
        sample_rate=alternating.sample_rate_hz,
        profile=profile,
    )
    assert float(v_alt.value) > float(v_stat.value)


@pytest.mark.metamorphic
def test_progressive_spectral_displacement() -> None:
    profile = load_analysis_profile()
    progressive = generate_signal(
        "frequency_modulated", duration_s=0.7, frequency_hz=500.0, mod_hz=2.0, beta=12.0
    )
    stationary = generate_signal("pure_sine", duration_s=0.7, frequency_hz=500.0)
    v_p = compute_frame_spectral_variance(
        progressive.samples,
        measurement_domain="radiated_audio",
        sample_rate=progressive.sample_rate_hz,
        profile=profile,
    )
    v_s = compute_frame_spectral_variance(
        stationary.samples,
        measurement_domain="radiated_audio",
        sample_rate=stationary.sample_rate_hz,
        profile=profile,
    )
    assert float(v_p.value) > float(v_s.value)


@pytest.mark.metamorphic
def test_stochastic_spectral_modulation() -> None:
    profile = load_analysis_profile()
    noise = generate_signal("band_limited_noise", duration_s=0.6, seed=7)
    harm = generate_signal("harmonic_sum", duration_s=0.6, frequency_hz=220.0, n_harmonics=5)
    v_n = compute_frame_spectral_variance(
        noise.samples, measurement_domain="radiated_audio", sample_rate=noise.sample_rate_hz, profile=profile
    )
    v_h = compute_frame_spectral_variance(
        harm.samples, measurement_domain="radiated_audio", sample_rate=harm.sample_rate_hz, profile=profile
    )
    assert float(v_n.value) >= 0.0
    assert float(v_h.value) >= 0.0
    # Stochastic broadband typically has higher temporal centroid variance than a stationary complex.
    assert float(v_n.value) > float(v_h.value) or np.isclose(float(v_h.value), 0.0, atol=1.0)
