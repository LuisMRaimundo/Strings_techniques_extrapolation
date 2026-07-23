"""HNR — spectral-mask definition only (not autocorrelation)."""

from __future__ import annotations

import math

import pytest

from string_technique_model.descriptors.hnr import METHOD_ID, compute_hnr
from string_technique_model.descriptors.models import load_analysis_profile
from string_technique_model.testing.descriptor_asserts import assert_provenance
from string_technique_model.testing.reference_cases import worked_benchmarks
from string_technique_model.testing.signal_generators import generate_signal

pytestmark = pytest.mark.acoustics_stress


@pytest.mark.mathematical_exact
@pytest.mark.benchmark
def test_benchmark_f_hnr_monotonic_with_noise() -> None:
    bench = next(b for b in worked_benchmarks() if b.id == "F")
    assert bench.status == "implemented"
    profile = load_analysis_profile()
    f0 = 220.0
    levels = [0.0, 0.05, 0.2, 0.5]
    values = []
    for nl in levels:
        sig = generate_signal(
            "harmonic_plus_noise",
            duration_s=0.6,
            frequency_hz=f0,
            n_harmonics=8,
            noise_level=nl,
            seed=1,
        )
        result = compute_hnr(
            sig.samples,
            measurement_domain="radiated_audio",
            sample_rate=sig.sample_rate_hz,
            profile=profile,
            f0_hz=f0,
        )
        assert_provenance(result)
        assert result.method_id == METHOD_ID
        assert result.extras["not_autocorrelation_hnr"] is True
        values.append(float(result.value))
    # Monotonic non-increasing as noise increases
    for a, b in zip(values, values[1:], strict=False):
        assert a >= b - 1e-9


@pytest.mark.metamorphic
def test_harmonic_higher_than_noise_and_silence() -> None:
    profile = load_analysis_profile()
    harm = generate_signal("harmonic_sum", duration_s=0.5, frequency_hz=220.0, n_harmonics=8)
    noise = generate_signal("band_limited_noise", duration_s=0.5, seed=2)
    silence = generate_signal("silence", duration_s=0.2)
    h = compute_hnr(
        harm.samples,
        measurement_domain="radiated_audio",
        sample_rate=harm.sample_rate_hz,
        profile=profile,
        f0_hz=220.0,
    )
    n = compute_hnr(
        noise.samples,
        measurement_domain="radiated_audio",
        sample_rate=noise.sample_rate_hz,
        profile=profile,
        f0_hz=220.0,
    )
    s = compute_hnr(
        silence.samples,
        measurement_domain="radiated_audio",
        sample_rate=silence.sample_rate_hz,
        profile=profile,
        f0_hz=220.0,
    )
    assert float(h.value) > float(n.value)
    assert s.status == "silence"
    assert math.isnan(float(s.value))


@pytest.mark.metamorphic
def test_missing_fundamental_and_inharmonic() -> None:
    profile = load_analysis_profile()
    mf = generate_signal("missing_fundamental", duration_s=0.5, frequency_hz=220.0)
    inh = generate_signal("inharmonic", duration_s=0.5)
    r_mf = compute_hnr(
        mf.samples,
        measurement_domain="radiated_audio",
        sample_rate=mf.sample_rate_hz,
        profile=profile,
        f0_hz=220.0,
    )
    r_inh = compute_hnr(
        inh.samples,
        measurement_domain="radiated_audio",
        sample_rate=inh.sample_rate_hz,
        profile=profile,
        f0_hz=220.0,
    )
    assert math.isfinite(float(r_mf.value))
    assert math.isfinite(float(r_inh.value))
    # Inharmonic residual should not exceed a strong harmonic HNR
    harm = generate_signal("harmonic_sum", duration_s=0.5, frequency_hz=220.0, n_harmonics=8)
    r_h = compute_hnr(
        harm.samples,
        measurement_domain="radiated_audio",
        sample_rate=harm.sample_rate_hz,
        profile=profile,
        f0_hz=220.0,
    )
    assert float(r_h.value) > float(r_inh.value)
