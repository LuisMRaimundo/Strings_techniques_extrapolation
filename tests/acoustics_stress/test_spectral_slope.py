"""Spectral slope — method spectral_slope_logfreq_db_linreg_v1."""

from __future__ import annotations

import numpy as np
import pytest

from string_technique_model.descriptors.models import AnalysisProfile, load_analysis_profile
from string_technique_model.descriptors.slope import METHOD_ID, _slope_db_per_log10hz, compute_spectral_slope
from string_technique_model.testing.descriptor_asserts import assert_provenance
from string_technique_model.testing.signal_generators import generate_signal

pytestmark = pytest.mark.acoustics_stress


def _power_law_signal(*, beta: float, duration_s: float = 0.8, sample_rate: float = 44100.0, seed: int = 0) -> np.ndarray:
    """Noise with designed PSD proportional to f^beta (more negative beta → steeper negative slope)."""
    n = int(duration_s * sample_rate)
    rng = np.random.default_rng(seed)
    white = rng.normal(0.0, 1.0, n)
    spec = np.fft.rfft(white)
    freqs = np.fft.rfftfreq(n, d=1.0 / sample_rate)
    scale = np.ones_like(freqs)
    pos = freqs > 0
    scale[pos] = freqs[pos] ** (beta / 2.0)
    spec *= scale
    spec[0] = 0.0
    x = np.fft.irfft(spec, n=n)
    peak = float(np.max(np.abs(x))) or 1.0
    return 0.2 * (x / peak)


@pytest.mark.mathematical_exact
def test_slope_preserves_method_id() -> None:
    sig = generate_signal("harmonic_sum", duration_s=0.4, frequency_hz=220.0, n_harmonics=8)
    result = compute_spectral_slope(
        sig.samples,
        measurement_domain="radiated_audio",
        sample_rate=sig.sample_rate_hz,
        profile=load_analysis_profile(),
    )
    assert_provenance(result)
    assert result.method_id == METHOD_ID
    assert result.extras["frequency_axis"] == "logarithmic_log10"
    assert result.extras["level_axis"] == "decibel_power"
    assert result.extras["exclude_dc"] is True


@pytest.mark.mathematical_exact
def test_exact_constructed_spectrum_rank_order() -> None:
    freqs = np.array([100.0, 200.0, 400.0, 800.0, 1600.0, 3200.0])
    # power ∝ f^beta
    steep = freqs ** (-2.0)
    mild = freqs ** (-1.0)
    flat = freqs ** (0.0)
    s_steep = _slope_db_per_log10hz(freqs, steep, exclude_dc=False)
    s_mild = _slope_db_per_log10hz(freqs, mild, exclude_dc=False)
    s_flat = _slope_db_per_log10hz(freqs, flat, exclude_dc=False)
    assert s_steep < s_mild < s_flat


@pytest.mark.metamorphic
def test_controlled_envelope_rank_order() -> None:
    profile = load_analysis_profile()
    steep = _power_law_signal(beta=-2.0, seed=1)
    mild = _power_law_signal(beta=-1.0, seed=1)
    bright = _power_law_signal(beta=0.0, seed=1)
    s_steep = compute_spectral_slope(steep, measurement_domain="radiated_audio", sample_rate=44100.0, profile=profile)
    s_mild = compute_spectral_slope(mild, measurement_domain="radiated_audio", sample_rate=44100.0, profile=profile)
    s_bright = compute_spectral_slope(bright, measurement_domain="radiated_audio", sample_rate=44100.0, profile=profile)
    assert float(s_steep.value) < float(s_mild.value) < float(s_bright.value)


@pytest.mark.domain_boundary
def test_slope_silence() -> None:
    sig = generate_signal("silence", duration_s=0.2)
    result = compute_spectral_slope(
        sig.samples,
        measurement_domain="radiated_audio",
        sample_rate=sig.sample_rate_hz,
        profile=load_analysis_profile(),
    )
    assert result.status == "silence"


@pytest.mark.adversarial
def test_slope_rejects_undeclared_axes() -> None:
    bad = load_analysis_profile().model_dump()
    bad["slope"] = {
        "frequency_axis": "linear",
        "level_axis": "decibel_power",
        "exclude_dc": True,
        "min_hz": 100.0,
        "max_hz": 5000.0,
    }
    from string_technique_model.descriptors.spectrum import SpectrumError

    with pytest.raises(SpectrumError):
        compute_spectral_slope(
            generate_signal("pure_sine", duration_s=0.2).samples,
            measurement_domain="radiated_audio",
            sample_rate=44100.0,
            profile=AnalysisProfile.model_validate(bad),
        )
