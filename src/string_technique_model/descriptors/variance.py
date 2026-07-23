"""Frame-level spectral variance — variance of per-frame spectral centroids over time."""

from __future__ import annotations

import math

import numpy as np

from string_technique_model.descriptors.centroid import spectral_centroid_from_spectrum
from string_technique_model.descriptors.models import (
    AnalysisProfile,
    DescriptorResult,
    MeasurementDomain,
    load_analysis_profile,
)
from string_technique_model.descriptors.spectrum import (
    SpectrumError,
    is_silent,
    profile_nyquist,
    stft_magnitude_power,
    validate_audio,
    weights_from_spectrum,
)

DESCRIPTOR_ID = "DESC_FRAME_SPECTRAL_VARIANCE"
METHOD_ID = "frame_spectral_variance_centroid_v1"


def compute_frame_spectral_variance(
    audio: np.ndarray,
    *,
    measurement_domain: MeasurementDomain,
    sample_rate: float | None = None,
    profile: AnalysisProfile | None = None,
) -> DescriptorResult:
    """Temporal variance of frame centroids — not within-frame spectral spread."""
    profile = profile or load_analysis_profile()
    sr = float(sample_rate if sample_rate is not None else profile.sample_rate_hz)
    x = validate_audio(audio, sr)
    if profile.variance.get("feature") != "spectral_centroid_hz":
        raise SpectrumError("variance feature must be spectral_centroid_hz")
    method_id = profile.method_ids.get("frame_spectral_variance", METHOD_ID)
    weight_name = profile.weighting
    fmin = float(profile.frequency_min_hz)
    fmax = profile_nyquist(profile, sr)

    if is_silent(x, profile.silence_rms_threshold):
        value = float("nan") if profile.silence_policy != "zero" else 0.0
        status = "silence"
    else:
        freqs, mags, power = stft_magnitude_power(
            x,
            sample_rate=sr,
            fft_size=profile.fft_size,
            hop_size=profile.hop_size,
            window_type=profile.window_type,
        )
        cents = []
        for i in range(mags.shape[0]):
            w = weights_from_spectrum(mags[i], power[i], weight_name)
            c = spectral_centroid_from_spectrum(freqs, w, fmin=fmin, fmax=fmax)
            if math.isfinite(c):
                cents.append(c)
        value = float(np.var(cents)) if len(cents) >= 2 else 0.0
        status = "ok"

    return DescriptorResult(
        descriptor_id=DESCRIPTOR_ID,
        value=value,
        unit="Hz_squared",
        measurement_domain=measurement_domain,
        sample_rate=sr,
        fft_size=profile.fft_size,
        window_type=profile.window_type,
        hop_size=profile.hop_size,
        frequency_limits=(fmin, fmax),
        amplitude_power_convention=profile.amplitude_power_convention,
        normalization="none",
        temporal_aggregation="variance_of_frame_centroids",
        silence_policy=profile.silence_policy,
        implementation_version=profile.implementation_version,
        method_id=method_id,
        profile_id=profile.profile_id,
        weighting=str(weight_name),
        status=status,
        extras={
            "distinction": "temporal_variance_of_centroids_not_within_frame_spread",
            "feature": "spectral_centroid_hz",
        },
    )
