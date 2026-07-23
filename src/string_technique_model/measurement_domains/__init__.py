"""Measurement-domain ontology (separate from EWSD and acoustic-descriptor registries)."""

from string_technique_model.measurement_domains.registry import (
    REQUIRED_DOMAIN_IDS,
    MeasurementDomainRegistry,
    MeasurementDomainSpec,
    get_measurement_domain,
    load_measurement_domain_registry,
)

__all__ = [
    "MeasurementDomainRegistry",
    "MeasurementDomainSpec",
    "REQUIRED_DOMAIN_IDS",
    "get_measurement_domain",
    "load_measurement_domain_registry",
]
