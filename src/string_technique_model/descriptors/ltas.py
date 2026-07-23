"""Long-term average spectrum (LTAS) — vector descriptor object, not a scalar."""

from __future__ import annotations

from typing import Any

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

DESCRIPTOR_ID = "DESC_LTAS"
METHOD_ID = "ltas_mean_power_v1"


def compute_ltas(
    audio: np.ndarray,
    *,
    measurement_domain: MeasurementDomain,
    sample_rate: float | None = None,
    profile: AnalysisProfile | None = None,
) -> DescriptorResult:
    profile = profile or load_analysis_profile()
    sr = float(sample_rate if sample_rate is not None else profile.sample_rate_hz)
    x = validate_audio(audio, sr)
    cfg = profile.ltas
    if cfg.get("averaging_domain") != "power":
        raise SpectrumError("ltas averaging_domain must be power")
    method_id = profile.method_ids.get("ltas", METHOD_ID)
    normalize = bool(cfg.get("normalize", False))

    if is_silent(x, profile.silence_rms_threshold):
        freqs = np.fft.rfftfreq(profile.fft_size, d=1.0 / sr)
        spectrum = np.full_like(freqs, np.nan if profile.silence_policy != "zero" else 0.0)
        status = "silence"
    else:
        freqs, _m, power = stft_magnitude_power(
            x,
            sample_rate=sr,
            fft_size=profile.fft_size,
            hop_size=profile.hop_size,
            window_type=profile.window_type,
        )
        spectrum = mean_spectrum(power, normalize=normalize)
        status = "ok"

    value: dict[str, Any] = {
        "frequencies_hz": freqs.tolist(),
        "spectrum": spectrum.tolist(),
        "averaging_domain": "power",
        "output_units": cfg.get("output_units", "power_linear_mean"),
        "frequency_resolution_hz": float(sr / profile.fft_size),
    }

    return DescriptorResult(
        descriptor_id=DESCRIPTOR_ID,
        value=value,
        unit=str(cfg.get("output_units", "power_linear_mean")),
        measurement_domain=measurement_domain,
        sample_rate=sr,
        fft_size=profile.fft_size,
        window_type=profile.window_type,
        hop_size=profile.hop_size,
        frequency_limits=(float(freqs[0]), float(freqs[-1])),
        amplitude_power_convention="mean_power_spectrum",
        normalization="sum_to_one" if normalize else "none",
        temporal_aggregation="mean_over_frames",
        silence_policy=profile.silence_policy,
        implementation_version=profile.implementation_version,
        method_id=method_id,
        profile_id=profile.profile_id,
        status=status,
        extras={"is_vector_descriptor": True, "scalar_forbidden": True},
    )


def ltas_comparable(a: DescriptorResult, b: DescriptorResult) -> dict[str, Any]:
    """Comparability requires matching domain and analysis settings."""
    if a.measurement_domain != b.measurement_domain:
        return {"status": "not_comparable", "reason": "measurement_domain_mismatch"}
    keys = ("sample_rate", "fft_size", "window_type", "hop_size", "normalization")
    for k in keys:
        if getattr(a, k) != getattr(b, k):
            return {"status": "not_comparable", "reason": f"analysis_mismatch:{k}"}
    return {"status": "comparable"}
