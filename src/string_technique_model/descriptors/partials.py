"""Partial salience and pitch-component count (peak-based, configurable)."""

from __future__ import annotations

import numpy as np

from string_technique_model.descriptors.models import (
    AnalysisProfile,
    DescriptorResult,
    MeasurementDomain,
    load_analysis_profile,
)
from string_technique_model.descriptors.spectrum import (
    is_silent,
    mean_spectrum,
    stft_magnitude_power,
    validate_audio,
)

DESCRIPTOR_SALIENCE = "DESC_PARTIAL_SALIENCE"
DESCRIPTOR_COUNT = "DESC_PITCH_COMPONENT_COUNT"
METHOD_SALIENCE = "partial_peak_salience_v1"
METHOD_COUNT = "pitch_component_count_v1"


def detect_peaks(
    freqs: np.ndarray,
    magnitude: np.ndarray,
    *,
    min_separation_hz: float,
    amplitude_threshold_ratio: float,
    noise_floor_percentile: float,
) -> list[dict[str, float]]:
    if magnitude.size < 3:
        return []
    floor = float(np.percentile(magnitude, noise_floor_percentile))
    thresh = max(floor, amplitude_threshold_ratio * float(np.max(magnitude)))
    peaks: list[dict[str, float]] = []
    for i in range(1, len(magnitude) - 1):
        if magnitude[i] >= magnitude[i - 1] and magnitude[i] > magnitude[i + 1] and magnitude[i] >= thresh:
            peaks.append({"frequency_hz": float(freqs[i]), "magnitude": float(magnitude[i])})
    # Enforce minimum separation (keep stronger)
    peaks.sort(key=lambda p: p["magnitude"], reverse=True)
    kept: list[dict[str, float]] = []
    for p in peaks:
        if all(abs(p["frequency_hz"] - q["frequency_hz"]) >= min_separation_hz for q in kept):
            kept.append(p)
    kept.sort(key=lambda p: p["frequency_hz"])
    return kept


def _analyze_partials(
    audio: np.ndarray,
    *,
    measurement_domain: MeasurementDomain,
    sample_rate: float | None,
    profile: AnalysisProfile | None,
) -> tuple[AnalysisProfile, float, list[dict[str, float]], str]:
    profile = profile or load_analysis_profile()
    sr = float(sample_rate if sample_rate is not None else profile.sample_rate_hz)
    x = validate_audio(audio, sr)
    cfg = profile.partials
    if is_silent(x, profile.silence_rms_threshold):
        return profile, sr, [], "silence"
    freqs, mags, _p = stft_magnitude_power(
        x,
        sample_rate=sr,
        fft_size=profile.fft_size,
        hop_size=profile.hop_size,
        window_type=profile.window_type,
    )
    mean_m = mean_spectrum(mags, normalize=False)
    peaks = detect_peaks(
        freqs,
        mean_m,
        min_separation_hz=float(cfg.get("min_separation_hz", 20.0)),
        amplitude_threshold_ratio=float(cfg.get("amplitude_threshold_ratio", 0.02)),
        noise_floor_percentile=float(cfg.get("noise_floor_percentile", 20.0)),
    )
    return profile, sr, peaks, "ok"


def compute_partial_salience(
    audio: np.ndarray,
    *,
    measurement_domain: MeasurementDomain,
    sample_rate: float | None = None,
    profile: AnalysisProfile | None = None,
) -> DescriptorResult:
    profile, sr, peaks, status = _analyze_partials(
        audio, measurement_domain=measurement_domain, sample_rate=sample_rate, profile=profile
    )
    total = sum(p["magnitude"] for p in peaks) or 1.0
    value = [
        {
            "frequency_hz": p["frequency_hz"],
            "magnitude": p["magnitude"],
            "salience": p["magnitude"] / total,
        }
        for p in peaks
    ]
    return DescriptorResult(
        descriptor_id=DESCRIPTOR_SALIENCE,
        value=value,
        unit="relative_salience_0_to_1",
        measurement_domain=measurement_domain,
        sample_rate=sr,
        fft_size=profile.fft_size,
        window_type=profile.window_type,
        hop_size=profile.hop_size,
        frequency_limits=(float(profile.frequency_min_hz), sr / 2.0),
        amplitude_power_convention="mean_magnitude_peaks",
        normalization="salience_sum_to_one_over_detected_peaks",
        temporal_aggregation="mean_magnitude_spectrum",
        silence_policy=profile.silence_policy,
        implementation_version=profile.implementation_version,
        method_id=profile.method_ids.get("partial_salience", METHOD_SALIENCE),
        profile_id=profile.profile_id,
        status=status,
        extras={"n_peaks": len(peaks), "proxy_warning": "not_physical_cello_multiphonic"},
    )


def compute_pitch_component_count(
    audio: np.ndarray,
    *,
    measurement_domain: MeasurementDomain,
    sample_rate: float | None = None,
    profile: AnalysisProfile | None = None,
) -> DescriptorResult:
    profile, sr, peaks, status = _analyze_partials(
        audio, measurement_domain=measurement_domain, sample_rate=sample_rate, profile=profile
    )
    cfg = profile.partials
    count = len(peaks)
    if cfg.get("octave_equivalence"):
        # Collapse peaks related by near-integer octaves (log2 ratio ≈ integer).
        # Tolerance is looser than exact integers to absorb FFT-bin quantization.
        oct_tol = float(cfg.get("octave_log2_tolerance", 0.08))
        kept: list[float] = []
        for p in peaks:
            f = p["frequency_hz"]
            if not any(near_octave_equivalent(f, k, tol=oct_tol) for k in kept):
                kept.append(f)
        count = len(kept)
    return DescriptorResult(
        descriptor_id=DESCRIPTOR_COUNT,
        value=int(count),
        unit="count",
        measurement_domain=measurement_domain,
        sample_rate=sr,
        fft_size=profile.fft_size,
        window_type=profile.window_type,
        hop_size=profile.hop_size,
        frequency_limits=(float(profile.frequency_min_hz), sr / 2.0),
        amplitude_power_convention="mean_magnitude_peaks",
        normalization="none",
        temporal_aggregation="mean_magnitude_spectrum",
        silence_policy=profile.silence_policy,
        implementation_version=profile.implementation_version,
        method_id=profile.method_ids.get("pitch_component_count", METHOD_COUNT),
        profile_id=profile.profile_id,
        status=status,
        extras={
            "octave_equivalence": bool(cfg.get("octave_equivalence", False)),
            "proxy_warning": "not_physical_cello_multiphonic",
        },
    )


def math_log2_ratio(a: float, b: float) -> float:
    import math

    if a <= 0 or b <= 0:
        return float("inf")
    return abs(math.log2(a / b))


def near_octave_equivalent(a: float, b: float, *, tol: float = 0.03) -> bool:
    """True when |log2(a/b)| is within tol of an integer (including unison)."""
    import math

    if a <= 0 or b <= 0:
        return False
    r = abs(math.log2(a / b))
    return abs(r - round(r)) <= tol
