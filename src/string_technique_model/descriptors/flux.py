"""Spectral flux — L1 half-wave rectified difference of normalized magnitude frames."""

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
    stft_magnitude_power,
    validate_audio,
)

DESCRIPTOR_ID = "DESC_SPECTRAL_FLUX"
METHOD_ID = "spectral_flux_l1_halfwave_v1"


def compute_spectral_flux(
    audio: np.ndarray,
    *,
    measurement_domain: MeasurementDomain,
    sample_rate: float | None = None,
    profile: AnalysisProfile | None = None,
) -> DescriptorResult:
    profile = profile or load_analysis_profile()
    sr = float(sample_rate if sample_rate is not None else profile.sample_rate_hz)
    x = validate_audio(audio, sr)
    cfg = profile.flux
    if not cfg.get("normalize_frames", True) or not cfg.get("half_wave_rectify", True):
        raise SpectrumError("flux profile must set normalize_frames=true and half_wave_rectify=true")
    if cfg.get("distance") != "L1":
        raise SpectrumError("flux profile distance must be L1 for method spectral_flux_l1_halfwave_v1")
    method_id = profile.method_ids.get("spectral_flux", METHOD_ID)

    if is_silent(x, profile.silence_rms_threshold):
        value = float("nan") if profile.silence_policy != "zero" else 0.0
        status = "silence"
    else:
        _f, mags, _p = stft_magnitude_power(
            x,
            sample_rate=sr,
            fft_size=profile.fft_size,
            hop_size=profile.hop_size,
            window_type=profile.window_type,
        )
        fluxes = []
        prev = None
        for i in range(mags.shape[0]):
            frame = mags[i]
            s = float(np.sum(frame))
            norm = frame / s if s > 0 else frame
            if prev is not None:
                diff = norm - prev
                if cfg.get("half_wave_rectify", True):
                    diff = np.maximum(diff, 0.0)
                fluxes.append(float(np.sum(np.abs(diff))))
            prev = norm
        value = float(np.mean(fluxes)) if fluxes else 0.0
        status = "ok" if math.isfinite(value) else "silence"

    return DescriptorResult(
        descriptor_id=DESCRIPTOR_ID,
        value=value,
        unit="normalized_L1_halfwave",
        measurement_domain=measurement_domain,
        sample_rate=sr,
        fft_size=profile.fft_size,
        window_type=profile.window_type,
        hop_size=profile.hop_size,
        frequency_limits=(float(profile.frequency_min_hz), sr / 2.0),
        amplitude_power_convention="magnitude_spectrum_L1_normalized_frames",
        normalization="sum_to_one_per_frame",
        temporal_aggregation="mean_over_frame_transitions",
        silence_policy=profile.silence_policy,
        implementation_version=profile.implementation_version,
        method_id=method_id,
        profile_id=profile.profile_id,
        status=status,
        extras={"half_wave_rectify": True, "distance": "L1"},
    )
