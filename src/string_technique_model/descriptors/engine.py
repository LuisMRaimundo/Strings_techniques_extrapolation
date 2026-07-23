"""Descriptor computation dispatch."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import numpy as np

from string_technique_model.descriptors.centroid import compute_spectral_centroid
from string_technique_model.descriptors.flux import compute_spectral_flux
from string_technique_model.descriptors.hnr import compute_hnr
from string_technique_model.descriptors.ltas import compute_ltas
from string_technique_model.descriptors.models import (
    AnalysisProfile,
    DescriptorResult,
    MeasurementDomain,
    load_analysis_profile,
)
from string_technique_model.descriptors.partials import (
    compute_partial_salience,
    compute_pitch_component_count,
)
from string_technique_model.descriptors.slope import compute_spectral_slope
from string_technique_model.descriptors.spectrum import compare_domains
from string_technique_model.descriptors.variance import compute_frame_spectral_variance

_IMPLEMENTATIONS: dict[str, Callable[..., DescriptorResult]] = {
    "DESC_SPECTRAL_CENTROID": compute_spectral_centroid,
    "DESC_SPECTRAL_SLOPE": compute_spectral_slope,
    "DESC_HNR": compute_hnr,
    "DESC_SPECTRAL_FLUX": compute_spectral_flux,
    "DESC_FRAME_SPECTRAL_VARIANCE": compute_frame_spectral_variance,
    "DESC_LTAS": compute_ltas,
    "DESC_PARTIAL_SALIENCE": compute_partial_salience,
    "DESC_PITCH_COMPONENT_COUNT": compute_pitch_component_count,
}


def implemented_descriptor_ids() -> list[str]:
    return sorted(_IMPLEMENTATIONS)


def compute_descriptor(
    descriptor_id: str,
    audio: np.ndarray,
    *,
    measurement_domain: MeasurementDomain,
    sample_rate: float | None = None,
    profile: AnalysisProfile | None = None,
    **kwargs: Any,
) -> DescriptorResult:
    if descriptor_id not in _IMPLEMENTATIONS:
        raise KeyError(
            f"Descriptor {descriptor_id} has no numerical implementation. "
            f"Implemented: {implemented_descriptor_ids()}"
        )
    profile = profile or load_analysis_profile()
    fn = _IMPLEMENTATIONS[descriptor_id]
    return fn(
        audio,
        measurement_domain=measurement_domain,
        sample_rate=sample_rate,
        profile=profile,
        **kwargs,
    )


def domains_comparable(a: MeasurementDomain | str, b: MeasurementDomain | str) -> dict[str, Any]:
    return compare_domains(str(a), str(b))
