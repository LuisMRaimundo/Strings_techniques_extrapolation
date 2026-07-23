"""Acoustic-descriptor registry and numerical backend (separate from EWSD)."""

from string_technique_model.descriptors.attenuation import (
    AttenuationResult,
    amplitude_ratio_to_db,
    db_to_amplitude_ratio,
    db_to_power_ratio,
    power_ratio_to_db,
    refuse_bridge_mobility_as_spl,
    refuse_sones_as_db,
)
from string_technique_model.descriptors.engine import (
    compute_descriptor,
    domains_comparable,
    implemented_descriptor_ids,
)
from string_technique_model.descriptors.models import (
    AnalysisProfile,
    DescriptorResult,
    centroid_tolerance_hz,
    load_analysis_profile,
)
from string_technique_model.descriptors.registry import (
    DescriptorRegistry,
    DescriptorSpec,
    clear_descriptor_registry_cache,
    get_descriptor,
    list_implemented_descriptors,
    load_descriptor_registry,
)

__all__ = [
    "AnalysisProfile",
    "AttenuationResult",
    "DescriptorRegistry",
    "DescriptorResult",
    "DescriptorSpec",
    "amplitude_ratio_to_db",
    "centroid_tolerance_hz",
    "clear_descriptor_registry_cache",
    "compute_descriptor",
    "db_to_amplitude_ratio",
    "db_to_power_ratio",
    "domains_comparable",
    "get_descriptor",
    "implemented_descriptor_ids",
    "list_implemented_descriptors",
    "load_analysis_profile",
    "load_descriptor_registry",
    "power_ratio_to_db",
    "refuse_bridge_mobility_as_spl",
    "refuse_sones_as_db",
]
