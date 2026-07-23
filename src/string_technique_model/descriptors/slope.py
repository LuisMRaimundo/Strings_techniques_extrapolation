"""Spectral slope — log-frequency vs dB-power linear regression."""

from __future__ import annotations

import math

import numpy as np

from string_technique_model.descriptors.models import (
    AnalysisProfile,
    DescriptorResult,
    MeasurementDomain,
    load_analysis_profile,
)
from string_technique_model.descriptors.spectrum import (
    SpectrumError,
    is_silent,
    mean_spectrum,
    stft_magnitude_power,
    validate_audio,
)

DESCRIPTOR_ID = "DESC_SPECTRAL_SLOPE"
METHOD_ID = "spectral_slope_logfreq_db_linreg_v1"


def _slope_db_per_log10hz(freqs: np.ndarray, power: np.ndarray, *, exclude_dc: bool) -> float:
    mask = freqs > 0
    if exclude_dc:
        mask &= np.arange(len(freqs)) > 0
    f = freqs[mask]
    p = power[mask]
    p = np.maximum(p, 1e-30)
    x = np.log10(f)
    y = 10.0 * np.log10(p)  # dB power
    if x.size < 2:
        return float("nan")
    # Ordinary least squares slope dy/dx
    x_mean = float(np.mean(x))
    y_mean = float(np.mean(y))
    var_x = float(np.sum((x - x_mean) ** 2))
    if var_x <= 0:
        return float("nan")
    cov = float(np.sum((x - x_mean) * (y - y_mean)))
    return cov / var_x


def compute_spectral_slope(
    audio: np.ndarray,
    *,
    measurement_domain: MeasurementDomain,
    sample_rate: float | None = None,
    profile: AnalysisProfile | None = None,
) -> DescriptorResult:
    profile = profile or load_analysis_profile()
    sr = float(sample_rate if sample_rate is not None else profile.sample_rate_hz)
    x = validate_audio(audio, sr)
    cfg = profile.slope
    fmin = float(cfg.get("min_hz", 100.0))
    fmax = float(cfg.get("max_hz", 5000.0))
    exclude_dc = bool(cfg.get("exclude_dc", True))
    method_id = profile.method_ids.get("spectral_slope", METHOD_ID)

    if cfg.get("frequency_axis") != "logarithmic" or cfg.get("level_axis") != "decibel_power":
        raise SpectrumError(
            "slope profile must declare frequency_axis=logarithmic and level_axis=decibel_power "
            f"for method {method_id}"
        )

    if is_silent(x, profile.silence_rms_threshold):
        value = float("nan") if profile.silence_policy != "zero" else 0.0
        status = "silence"
    else:
        freqs, _mags, power = stft_magnitude_power(
            x,
            sample_rate=sr,
            fft_size=profile.fft_size,
            hop_size=profile.hop_size,
            window_type=profile.window_type,
        )
        mean_p = mean_spectrum(power, normalize=False)
        band = (freqs >= fmin) & (freqs <= fmax)
        value = _slope_db_per_log10hz(freqs[band], mean_p[band], exclude_dc=exclude_dc)
        status = "ok" if math.isfinite(value) else "silence"

    return DescriptorResult(
        descriptor_id=DESCRIPTOR_ID,
        value=value,
        unit="dB_per_decade_log10Hz",
        measurement_domain=measurement_domain,
        sample_rate=sr,
        fft_size=profile.fft_size,
        window_type=profile.window_type,
        hop_size=profile.hop_size,
        frequency_limits=(fmin, fmax),
        amplitude_power_convention="power_spectrum_to_dB_for_regression",
        normalization="none",
        temporal_aggregation="mean_power_spectrum_then_regression",
        silence_policy=profile.silence_policy,
        implementation_version=profile.implementation_version,
        method_id=method_id,
        profile_id=profile.profile_id,
        status=status,
        extras={
            "frequency_axis": "logarithmic_log10",
            "level_axis": "decibel_power",
            "exclude_dc": exclude_dc,
        },
    )
