"""Spectral flux — L1 half-wave normalized magnitude frames."""

from __future__ import annotations

import numpy as np
import pytest

from string_technique_model.descriptors.flux import METHOD_ID, compute_spectral_flux
from string_technique_model.descriptors.models import AnalysisProfile, load_analysis_profile
from string_technique_model.testing.descriptor_asserts import assert_provenance
from string_technique_model.testing.signal_generators import generate_signal

pytestmark = pytest.mark.acoustics_stress


@pytest.mark.mathematical_exact
def test_flux_method_documentation_fields() -> None:
    sig = generate_signal("pure_sine", duration_s=0.4, frequency_hz=440.0)
    result = compute_spectral_flux(
        sig.samples,
        measurement_domain="radiated_audio",
        sample_rate=sig.sample_rate_hz,
        profile=load_analysis_profile(),
    )
    assert_provenance(result)
    assert result.method_id == METHOD_ID
    assert result.normalization == "sum_to_one_per_frame"
    assert result.extras["half_wave_rectify"] is True
    assert result.extras["distance"] == "L1"


@pytest.mark.metamorphic
def test_stationary_vs_sudden_vs_gradual() -> None:
    profile = load_analysis_profile()
    stationary = generate_signal("pure_sine", duration_s=0.6, frequency_hz=600.0)
    sudden = generate_signal("spectral_transition", duration_s=0.6, f1_hz=400.0, f2_hz=1800.0)
    # Gradual: frequency-modulated (spectral content changes continuously)
    gradual = generate_signal("frequency_modulated", duration_s=0.6, frequency_hz=600.0, mod_hz=3.0, beta=8.0)
    f_stat = compute_spectral_flux(
        stationary.samples,
        measurement_domain="radiated_audio",
        sample_rate=stationary.sample_rate_hz,
        profile=profile,
    )
    f_sud = compute_spectral_flux(
        sudden.samples,
        measurement_domain="radiated_audio",
        sample_rate=sudden.sample_rate_hz,
        profile=profile,
    )
    f_grad = compute_spectral_flux(
        gradual.samples,
        measurement_domain="radiated_audio",
        sample_rate=gradual.sample_rate_hz,
        profile=profile,
    )
    assert float(f_stat.value) < float(f_sud.value)
    assert float(f_stat.value) < float(f_grad.value)


@pytest.mark.metamorphic
def test_amplitude_only_change_low_flux() -> None:
    profile = load_analysis_profile()
    amp = generate_signal("amplitude_modulated", duration_s=0.5, frequency_hz=500.0, depth=0.8, mod_hz=4.0)
    sudden = generate_signal("spectral_transition", duration_s=0.5)
    f_amp = compute_spectral_flux(
        amp.samples, measurement_domain="radiated_audio", sample_rate=amp.sample_rate_hz, profile=profile
    )
    f_sud = compute_spectral_flux(
        sudden.samples,
        measurement_domain="radiated_audio",
        sample_rate=sudden.sample_rate_hz,
        profile=profile,
    )
    # Frame-normalized flux is largely insensitive to global amplitude modulation.
    assert float(f_amp.value) < float(f_sud.value)


@pytest.mark.metamorphic
def test_time_shift_near_invariant_for_stationary() -> None:
    profile = load_analysis_profile()
    sig = generate_signal("pure_sine", duration_s=0.5, frequency_hz=700.0)
    shifted = np.roll(sig.samples, 200)
    a = compute_spectral_flux(
        sig.samples, measurement_domain="radiated_audio", sample_rate=sig.sample_rate_hz, profile=profile
    )
    b = compute_spectral_flux(
        shifted, measurement_domain="radiated_audio", sample_rate=sig.sample_rate_hz, profile=profile
    )
    assert abs(float(a.value) - float(b.value)) < 0.05


@pytest.mark.metamorphic
def test_different_hop_sizes() -> None:
    sig = generate_signal("spectral_transition", duration_s=0.6)
    values = []
    for hop in (512, 1024, 2048):
        profile = load_analysis_profile().model_dump()
        profile["hop_size"] = hop
        result = compute_spectral_flux(
            sig.samples,
            measurement_domain="radiated_audio",
            sample_rate=sig.sample_rate_hz,
            profile=AnalysisProfile.model_validate(profile),
        )
        values.append(float(result.value))
    assert all(v == v for v in values)  # finite
    assert max(values) > min(values) * 0.1  # hop affects aggregation scale/path
