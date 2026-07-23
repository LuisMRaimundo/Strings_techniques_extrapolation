"""Honest capability reporting for technique models (no prediction imports)."""

from __future__ import annotations

from enum import Enum


class CapabilityState(str, Enum):
    unavailable = "unavailable"
    schema_only = "schema_only"
    descriptor_extraction_available = "descriptor_extraction_available"
    qualitative_constraints_available = "qualitative_constraints_available"
    numerical_transform_available = "numerical_transform_available"


def default_capabilities(*, metric_numerical: bool = False) -> dict[str, str]:
    """Honest capability map. Spectrum numerical transform is unavailable."""
    return {
        "metric_only": (
            CapabilityState.numerical_transform_available.value
            if metric_numerical
            else CapabilityState.qualitative_constraints_available.value
        ),
        "spectrum_aware": CapabilityState.schema_only.value,
        "descriptor_extraction": CapabilityState.unavailable.value,
        "qualitative_constraints": CapabilityState.qualitative_constraints_available.value,
        "numerical_spectrum_transform": CapabilityState.unavailable.value,
    }
