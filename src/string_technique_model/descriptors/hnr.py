"""Harmonic-to-noise ratio — spectral-mask definition (not autocorrelation)."""

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

DESCRIPTOR_ID = "DESC_HNR"
METHOD_ID = "hnr_spectral_mask_v1"


def _estimate_f0_hz(freqs: np.ndarray, power: np.ndarray, *, fmin: float = 70.0, fmax: float = 500.0) -> float:
    mask = (freqs >= fmin) & (freqs <= fmax)
    if not np.any(mask):
        return float("nan")
    idx = int(np.argmax(power[mask]))
    return float(freqs[mask][idx])


def spectral_mask_hnr_db(
    freqs: np.ndarray,
    power: np.ndarray,
    *,
    f0_hz: float,
    n_harmonics: int,
    halfwidth_bins: int,
) -> float:
    if not math.isfinite(f0_hz) or f0_hz <= 0:
        raise SpectrumError("f0_hz must be positive for spectral-mask HNR")
    df = float(freqs[1] - freqs[0]) if len(freqs) > 1 else 1.0
    harm_mask = np.zeros_like(power, dtype=bool)
    for k in range(1, n_harmonics + 1):
        target = k * f0_hz
        if target > freqs[-1]:
            break
        center = int(round(target / df))
        lo = max(center - halfwidth_bins, 0)
        hi = min(center + halfwidth_bins + 1, len(power))
        harm_mask[lo:hi] = True
    e_h = float(np.sum(power[harm_mask]))
    e_n = float(np.sum(power[~harm_mask]))
    if e_h <= 0 and e_n <= 0:
        return float("nan")
    if e_n <= 0:
        return 120.0  # practically infinite; capped
    return 10.0 * math.log10(e_h / e_n)


def compute_hnr(
    audio: np.ndarray,
    *,
    measurement_domain: MeasurementDomain,
    sample_rate: float | None = None,
    profile: AnalysisProfile | None = None,
    f0_hz: float | None = None,
) -> DescriptorResult:
    profile = profile or load_analysis_profile()
    sr = float(sample_rate if sample_rate is not None else profile.sample_rate_hz)
    x = validate_audio(audio, sr)
    cfg = profile.hnr
    if cfg.get("definition") != "spectral_mask_harmonic_vs_residual":
        raise SpectrumError("HNR profile must use definition=spectral_mask_harmonic_vs_residual")
    n_harm = int(cfg.get("n_harmonics", 10))
    half_w = int(cfg.get("harmonic_halfwidth_bins", 2))
    method_id = profile.method_ids.get("hnr", METHOD_ID)
    fmin = float(profile.frequency_min_hz)
    fmax = sr / 2.0

    if is_silent(x, profile.silence_rms_threshold):
        value = float("nan") if profile.silence_policy != "zero" else 0.0
        status = "silence"
        used_f0 = f0_hz
    else:
        freqs, _m, power = stft_magnitude_power(
            x,
            sample_rate=sr,
            fft_size=profile.fft_size,
            hop_size=profile.hop_size,
            window_type=profile.window_type,
        )
        mean_p = mean_spectrum(power, normalize=False)
        used_f0 = f0_hz if f0_hz is not None else cfg.get("f0_hz")
        if used_f0 is None:
            used_f0 = _estimate_f0_hz(freqs, mean_p)
        value = spectral_mask_hnr_db(
            freqs,
            mean_p,
            f0_hz=float(used_f0),
            n_harmonics=n_harm,
            halfwidth_bins=half_w,
        )
        status = "ok" if math.isfinite(value) else "silence"

    return DescriptorResult(
        descriptor_id=DESCRIPTOR_ID,
        value=value,
        unit="dB",
        measurement_domain=measurement_domain,
        sample_rate=sr,
        fft_size=profile.fft_size,
        window_type=profile.window_type,
        hop_size=profile.hop_size,
        frequency_limits=(fmin, fmax),
        amplitude_power_convention="power_ratio_to_dB_10log10",
        normalization="none",
        temporal_aggregation="mean_power_spectrum",
        silence_policy=profile.silence_policy,
        implementation_version=profile.implementation_version,
        method_id=method_id,
        profile_id=profile.profile_id,
        status=status,
        extras={
            "definition": "spectral_mask_harmonic_vs_residual",
            "f0_hz": used_f0,
            "n_harmonics": n_harm,
            "not_autocorrelation_hnr": True,
        },
    )
