"""Spectral centroid: C = Σ(f_k W_k) / Σ(W_k)."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from string_technique_model.descriptors.models import (
    AnalysisProfile,
    DescriptorResult,
    MeasurementDomain,
    Weighting,
    load_analysis_profile,
)
from string_technique_model.descriptors.spectrum import (
    SpectrumError,
    band_mask,
    is_silent,
    profile_nyquist,
    stft_magnitude_power,
    validate_audio,
    weights_from_spectrum,
)

DESCRIPTOR_ID = "DESC_SPECTRAL_CENTROID"


def spectral_centroid_from_spectrum(
    freqs: np.ndarray,
    weights: np.ndarray,
    *,
    fmin: float,
    fmax: float,
) -> float:
    mask = band_mask(freqs, fmin=fmin, fmax=fmax)
    f = freqs[mask]
    w = weights[mask]
    denom = float(np.sum(w))
    if denom <= 0 or not math.isfinite(denom):
        return float("nan")
    return float(np.sum(f * w) / denom)


def compute_spectral_centroid(
    audio: np.ndarray,
    *,
    measurement_domain: MeasurementDomain,
    sample_rate: float | None = None,
    profile: AnalysisProfile | None = None,
    weighting: str | None = None,
) -> DescriptorResult:
    profile = profile or load_analysis_profile()
    sr = float(sample_rate if sample_rate is not None else profile.sample_rate_hz)
    x = validate_audio(audio, sr)
    method_id = profile.method_ids.get("spectral_centroid", "spectral_centroid_v1")
    weight_name = str(weighting or profile.centroid.get("weighting") or profile.weighting)
    if weight_name not in {"magnitude", "power"}:
        raise SpectrumError("centroid weighting must be 'magnitude' or 'power'")
    weight_typed: Weighting = "power" if weight_name == "power" else "magnitude"

    fmax = profile_nyquist(profile, sr)
    fmin = float(profile.frequency_min_hz)
    warnings: list[str] = []

    if is_silent(x, profile.silence_rms_threshold):
        if profile.silence_policy == "raise":
            raise SpectrumError("silence under silence_rms_threshold")
        value: Any = 0.0 if profile.silence_policy == "zero" else float("nan")
        status = "silence"
    else:
        freqs, mags, power = stft_magnitude_power(
            x,
            sample_rate=sr,
            fft_size=profile.fft_size,
            hop_size=profile.hop_size,
            window_type=profile.window_type,
        )
        frame_centroids = []
        for i in range(mags.shape[0]):
            w = weights_from_spectrum(mags[i], power[i], weight_typed)
            if profile.normalize_spectrum:
                s = float(np.sum(w))
                if s > 0:
                    w = w / s
            c = spectral_centroid_from_spectrum(freqs, w, fmin=fmin, fmax=fmax)
            if math.isfinite(c):
                frame_centroids.append(c)
        if not frame_centroids:
            value = float("nan")
            status = "silence"
            warnings.append("no_frames_with_positive_weight")
        else:
            value = float(np.mean(frame_centroids))
            status = "ok"

    return DescriptorResult(
        descriptor_id=DESCRIPTOR_ID,
        value=value,
        unit="Hz",
        measurement_domain=measurement_domain,
        sample_rate=sr,
        fft_size=profile.fft_size,
        window_type=profile.window_type,
        hop_size=profile.hop_size,
        frequency_limits=(fmin, fmax),
        amplitude_power_convention=profile.amplitude_power_convention,
        normalization="none" if not profile.normalize_spectrum else "sum_to_one_per_frame",
        temporal_aggregation=profile.temporal_aggregation,
        silence_policy=profile.silence_policy,
        implementation_version=profile.implementation_version,
        method_id=method_id,
        profile_id=profile.profile_id,
        weighting=str(weight_name),
        status=status,
        warnings=warnings,
        extras={"equation": "C = sum(f_k W_k) / sum(W_k)"},
    )


def analytical_two_tone_centroid(
    f1: float,
    f2: float,
    w1: float,
    w2: float,
) -> float:
    """Exact C for two discrete tones with weights W (same convention as configured)."""
    denom = w1 + w2
    if denom <= 0:
        raise ValueError("weights must sum to positive")
    return (f1 * w1 + f2 * w2) / denom
