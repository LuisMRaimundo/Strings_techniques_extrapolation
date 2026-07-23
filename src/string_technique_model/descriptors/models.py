"""Typed analysis profiles and descriptor results with full provenance."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from string_technique_model.config import PACKAGE_ROOT, load_yaml, resolve_path

Weighting = Literal["magnitude", "power"]
MeasurementDomain = Literal[
    "radiated_audio",
    "bridge_force",
    "bridge_mobility",
    "string_velocity_at_bow",
    "body_acceleration",
    "unresolved",
]
SilencePolicy = Literal["return_nan", "raise", "zero"]


class AnalysisProfile(BaseModel):
    model_config = ConfigDict(extra="allow")

    profile_id: str
    implementation_version: str
    method_ids: dict[str, str] = Field(default_factory=dict)
    sample_rate_hz: float = 44100.0
    fft_size: int = 4096
    window_type: str = "hann"
    hop_size: int = 1024
    frequency_min_hz: float = 50.0
    frequency_max_hz: float | None = None
    weighting: Weighting = "power"
    normalize_spectrum: bool = False
    silence_rms_threshold: float = 1e-8
    silence_policy: SilencePolicy = "return_nan"
    temporal_aggregation: str = "mean_over_frames"
    amplitude_power_convention: str = (
        "linear_amplitude_time_domain__power_spectrum_frequency_domain"
    )
    centroid: dict[str, Any] = Field(default_factory=dict)
    slope: dict[str, Any] = Field(default_factory=dict)
    hnr: dict[str, Any] = Field(default_factory=dict)
    flux: dict[str, Any] = Field(default_factory=dict)
    variance: dict[str, Any] = Field(default_factory=dict)
    ltas: dict[str, Any] = Field(default_factory=dict)
    partials: dict[str, Any] = Field(default_factory=dict)
    attenuation: dict[str, Any] = Field(default_factory=dict)


class DescriptorResult(BaseModel):
    """Mandatory provenance fields for every descriptor output."""

    model_config = ConfigDict(extra="allow")

    descriptor_id: str
    value: Any
    unit: str
    measurement_domain: MeasurementDomain
    sample_rate: float
    fft_size: int
    window_type: str
    hop_size: int
    frequency_limits: tuple[float, float]
    amplitude_power_convention: str
    normalization: str
    temporal_aggregation: str
    silence_policy: str
    implementation_version: str
    method_id: str
    profile_id: str
    weighting: str | None = None
    status: str = "ok"  # ok | silence | invalid_input | not_comparable
    warnings: list[str] = Field(default_factory=list)
    extras: dict[str, Any] = Field(default_factory=dict)


def load_analysis_profile(path: str | None = None) -> AnalysisProfile:
    default = PACKAGE_ROOT / "configs" / "analysis_profiles" / "default_descriptor_v1.yaml"
    data = load_yaml(resolve_path(path or default))
    return AnalysisProfile.model_validate(data)


def fft_bin_resolution_hz(sample_rate: float, fft_size: int) -> float:
    return float(sample_rate) / float(fft_size)


def centroid_tolerance_hz(sample_rate: float, fft_size: int, *, windows: float = 1.5) -> float:
    """Tolerance from FFT-bin resolution and window main-lobe width factor."""
    return windows * fft_bin_resolution_hz(sample_rate, fft_size)
