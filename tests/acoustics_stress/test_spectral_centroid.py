"""Spectral centroid — exact equation, metamorphic, invalid, domain checks."""

from __future__ import annotations

import math

import pytest

from string_technique_model.descriptors.centroid import (
    analytical_two_tone_centroid,
    compute_spectral_centroid,
)
from string_technique_model.descriptors.models import (
    AnalysisProfile,
    centroid_tolerance_hz,
    load_analysis_profile,
)
from string_technique_model.descriptors.spectrum import SpectrumError
from string_technique_model.testing.descriptor_asserts import assert_provenance
from string_technique_model.testing.reference_cases import worked_benchmarks
from string_technique_model.testing.signal_generators import generate_signal

pytestmark = pytest.mark.acoustics_stress


def _profile(**overrides: object) -> AnalysisProfile:
    base = load_analysis_profile().model_dump()
    base.update(overrides)
    return AnalysisProfile.model_validate(base)


@pytest.mark.mathematical_exact
@pytest.mark.benchmark
def test_benchmark_d_1000hz_sine_centroid() -> None:
    bench = next(b for b in worked_benchmarks() if b.id == "D")
    assert bench.status == "implemented"
    profile = _profile()
    sig = generate_signal("pure_sine", duration_s=0.5, frequency_hz=1000.0, amplitude=0.5)
    result = compute_spectral_centroid(
        sig.samples,
        measurement_domain="radiated_audio",
        sample_rate=sig.sample_rate_hz,
        profile=profile,
        weighting="power",
    )
    assert_provenance(result)
    tol = centroid_tolerance_hz(result.sample_rate, result.fft_size)
    assert abs(float(result.value) - 1000.0) <= tol


@pytest.mark.mathematical_exact
@pytest.mark.benchmark
def test_benchmark_e_equal_weight_two_tone() -> None:
    bench = next(b for b in worked_benchmarks() if b.id == "E")
    assert bench.status == "implemented"
    profile = _profile()
    sig = generate_signal("two_tone", duration_s=0.5, f1_hz=500.0, f2_hz=1500.0, a1=0.4, a2=0.4)
    result = compute_spectral_centroid(
        sig.samples,
        measurement_domain="radiated_audio",
        sample_rate=sig.sample_rate_hz,
        profile=profile,
        weighting="power",
    )
    expected = analytical_two_tone_centroid(500.0, 1500.0, 0.4**2, 0.4**2)
    tol = centroid_tolerance_hz(result.sample_rate, result.fft_size)
    assert abs(float(result.value) - expected) <= tol


@pytest.mark.mathematical_exact
def test_unequal_weight_two_tone_power_analytical() -> None:
    a1, a2 = 1.0, 0.5
    expected = analytical_two_tone_centroid(500.0, 1500.0, a1**2, a2**2)
    sig = generate_signal("two_tone", duration_s=0.5, f1_hz=500.0, f2_hz=1500.0, a1=a1, a2=a2)
    result = compute_spectral_centroid(
        sig.samples,
        measurement_domain="radiated_audio",
        sample_rate=sig.sample_rate_hz,
        profile=_profile(),
        weighting="power",
    )
    tol = centroid_tolerance_hz(result.sample_rate, result.fft_size)
    assert abs(float(result.value) - expected) <= tol


@pytest.mark.mathematical_exact
def test_unequal_weight_two_tone_magnitude_analytical() -> None:
    a1, a2 = 1.0, 0.5
    expected = analytical_two_tone_centroid(500.0, 1500.0, a1, a2)
    sig = generate_signal("two_tone", duration_s=0.5, f1_hz=500.0, f2_hz=1500.0, a1=a1, a2=a2)
    result = compute_spectral_centroid(
        sig.samples,
        measurement_domain="radiated_audio",
        sample_rate=sig.sample_rate_hz,
        profile=_profile(centroid={"weighting": "magnitude"}, weighting="magnitude"),
        weighting="magnitude",
    )
    tol = centroid_tolerance_hz(result.sample_rate, result.fft_size)
    assert abs(float(result.value) - expected) <= tol
    assert result.weighting == "magnitude"


@pytest.mark.metamorphic
def test_amplitude_scale_invariance() -> None:
    profile = _profile()
    base = generate_signal("pure_sine", duration_s=0.4, frequency_hz=880.0, amplitude=0.2)
    scaled = base.samples * 4.0
    c1 = compute_spectral_centroid(
        base.samples, measurement_domain="radiated_audio", sample_rate=base.sample_rate_hz, profile=profile
    )
    c2 = compute_spectral_centroid(
        scaled, measurement_domain="radiated_audio", sample_rate=base.sample_rate_hz, profile=profile
    )
    tol = centroid_tolerance_hz(c1.sample_rate, c1.fft_size) * 0.25
    assert abs(float(c1.value) - float(c2.value)) <= tol


@pytest.mark.metamorphic
def test_high_frequency_energy_increases_centroid() -> None:
    low = generate_signal("pure_sine", duration_s=0.4, frequency_hz=400.0)
    high = generate_signal("pure_sine", duration_s=0.4, frequency_hz=2000.0)
    profile = _profile()
    c_low = compute_spectral_centroid(
        low.samples, measurement_domain="radiated_audio", sample_rate=low.sample_rate_hz, profile=profile
    )
    c_high = compute_spectral_centroid(
        high.samples, measurement_domain="radiated_audio", sample_rate=high.sample_rate_hz, profile=profile
    )
    assert float(c_high.value) > float(c_low.value)


@pytest.mark.metamorphic
def test_low_frequency_energy_decreases_centroid() -> None:
    mid = generate_signal("two_tone", duration_s=0.4, f1_hz=500.0, f2_hz=1500.0, a1=0.5, a2=0.5)
    low_heavy = generate_signal("two_tone", duration_s=0.4, f1_hz=500.0, f2_hz=1500.0, a1=1.0, a2=0.2)
    profile = _profile()
    c_mid = compute_spectral_centroid(
        mid.samples, measurement_domain="radiated_audio", sample_rate=mid.sample_rate_hz, profile=profile
    )
    c_low = compute_spectral_centroid(
        low_heavy.samples,
        measurement_domain="radiated_audio",
        sample_rate=low_heavy.sample_rate_hz,
        profile=profile,
    )
    assert float(c_low.value) < float(c_mid.value)


@pytest.mark.domain_boundary
def test_silence_and_near_silence() -> None:
    profile = _profile()
    silence = generate_signal("silence", duration_s=0.2)
    near = generate_signal("near_silence", duration_s=0.2)
    r1 = compute_spectral_centroid(
        silence.samples, measurement_domain="radiated_audio", sample_rate=silence.sample_rate_hz, profile=profile
    )
    r2 = compute_spectral_centroid(
        near.samples, measurement_domain="radiated_audio", sample_rate=near.sample_rate_hz, profile=profile
    )
    assert r1.status == "silence" and math.isnan(float(r1.value))
    assert r2.status == "silence" and math.isnan(float(r2.value))


@pytest.mark.adversarial
def test_clipped_signal_finite() -> None:
    sig = generate_signal("clipped", duration_s=0.3)
    result = compute_spectral_centroid(
        sig.samples,
        measurement_domain="radiated_audio",
        sample_rate=sig.sample_rate_hz,
        profile=_profile(),
    )
    assert result.status == "ok"
    assert math.isfinite(float(result.value))


@pytest.mark.metamorphic
def test_different_fft_sizes_tolerance_scales() -> None:
    sig = generate_signal("pure_sine", duration_s=0.5, frequency_hz=1000.0)
    for fft in (2048, 4096, 8192):
        profile = _profile(fft_size=fft, hop_size=fft // 4)
        result = compute_spectral_centroid(
            sig.samples,
            measurement_domain="radiated_audio",
            sample_rate=sig.sample_rate_hz,
            profile=profile,
        )
        tol = centroid_tolerance_hz(result.sample_rate, result.fft_size)
        assert abs(float(result.value) - 1000.0) <= tol


@pytest.mark.metamorphic
def test_different_sample_rates() -> None:
    for sr in (22050.0, 44100.0, 48000.0):
        sig = generate_signal("pure_sine", duration_s=0.4, frequency_hz=1000.0, sample_rate_hz=sr)
        profile = _profile(sample_rate_hz=sr)
        result = compute_spectral_centroid(
            sig.samples,
            measurement_domain="radiated_audio",
            sample_rate=sr,
            profile=profile,
        )
        tol = centroid_tolerance_hz(sr, result.fft_size)
        assert abs(float(result.value) - 1000.0) <= tol


@pytest.mark.mathematical_exact
def test_frequency_limit_truncation() -> None:
    # With fmax below 1500 Hz, equal-amplitude two-tone collapses toward 500 Hz.
    sig = generate_signal("two_tone", duration_s=0.5, f1_hz=500.0, f2_hz=1500.0, a1=0.5, a2=0.5)
    profile = _profile(frequency_max_hz=900.0)
    result = compute_spectral_centroid(
        sig.samples,
        measurement_domain="radiated_audio",
        sample_rate=sig.sample_rate_hz,
        profile=profile,
        weighting="power",
    )
    tol = centroid_tolerance_hz(result.sample_rate, result.fft_size)
    assert abs(float(result.value) - 500.0) <= tol


@pytest.mark.adversarial
def test_invalid_audio_raises() -> None:
    with pytest.raises(SpectrumError):
        compute_spectral_centroid(
            generate_signal("nan_contaminated", duration_s=0.1).samples,
            measurement_domain="radiated_audio",
            sample_rate=44100.0,
        )


@pytest.mark.measurement_domain
def test_microphone_vs_bridge_force_centroid_not_comparable() -> None:
    sig = generate_signal("pure_sine", duration_s=0.3, frequency_hz=1000.0)
    profile = _profile()
    mic = compute_spectral_centroid(
        sig.samples, measurement_domain="radiated_audio", sample_rate=sig.sample_rate_hz, profile=profile
    )
    bridge = compute_spectral_centroid(
        sig.samples, measurement_domain="bridge_force", sample_rate=sig.sample_rate_hz, profile=profile
    )
    # Same synthetic numbers, but literature comparison across domains is forbidden.
    assert mic.measurement_domain != bridge.measurement_domain
    from string_technique_model.descriptors.engine import domains_comparable

    cmp = domains_comparable(mic.measurement_domain, bridge.measurement_domain)
    assert cmp["status"] == "not_comparable"
    assert cmp["classification"] == "not_comparable"
