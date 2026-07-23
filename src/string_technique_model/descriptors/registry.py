"""Acoustic-descriptor registry loaded from YAML."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from string_technique_model.config import PACKAGE_ROOT, load_yaml

DESCRIPTORS_PATH = PACKAGE_ROOT / "configs" / "acoustic_descriptors.yaml"

_EWSD_COMPATIBLE_VALUES = frozenset(
    {
        "compatible",
        "compatible_with_activated_mapping",
        "explicit_activated_mapping",
    }
)


class DescriptorSpec(BaseModel):
    """Single acoustic descriptor entry from the registry."""

    model_config = ConfigDict(extra="allow")

    descriptor_id: str
    name: str
    definition: str
    formula_status: str
    units: str
    amplitude_power_convention: str | None = None
    temporal_aggregation: str | None = None
    required_input_representation: list[str] = Field(default_factory=list)
    valid_domain: str | None = None
    interpretation_limits: str | None = None
    ewsd_compatibility: str
    value_kind: str | None = None
    implemented: bool = False


class DescriptorRegistry(BaseModel):
    """Versioned registry of acoustic descriptors (separate from EWSD metrics)."""

    model_config = ConfigDict(extra="allow")

    version: str | None = None
    schema_version: str | None = None
    ewsd_compatibility_default: str | None = None
    descriptors: list[DescriptorSpec] = Field(default_factory=list)
    analysis_parameters_when_implemented: dict[str, Any] = Field(default_factory=dict)

    def get(self, descriptor_id: str) -> DescriptorSpec | None:
        for spec in self.descriptors:
            if spec.descriptor_id == descriptor_id:
                return spec
        return None

    def all(self) -> list[DescriptorSpec]:
        return list(self.descriptors)

    def implemented_only(self) -> list[DescriptorSpec]:
        return [d for d in self.descriptors if d.implemented]

    def ewsd_compatible_only(self) -> list[DescriptorSpec]:
        return [
            d
            for d in self.descriptors
            if d.ewsd_compatibility in _EWSD_COMPATIBLE_VALUES
        ]


def load_descriptor_registry(path: str | None = None) -> DescriptorRegistry:
    data = load_yaml(path or DESCRIPTORS_PATH)
    descriptors = [DescriptorSpec.model_validate(item) for item in data.get("descriptors", [])]
    return DescriptorRegistry(
        version=data.get("version"),
        schema_version=data.get("schema_version"),
        ewsd_compatibility_default=data.get("ewsd_compatibility_default"),
        descriptors=descriptors,
        analysis_parameters_when_implemented=data.get("analysis_parameters_when_implemented") or {},
    )


@lru_cache(maxsize=1)
def _default_registry() -> DescriptorRegistry:
    return load_descriptor_registry()


def clear_descriptor_registry_cache() -> None:
    _default_registry.cache_clear()


def get_descriptor(descriptor_id: str) -> DescriptorSpec | None:
    return _default_registry().get(descriptor_id)


def list_implemented_descriptors() -> list[DescriptorSpec]:
    return _default_registry().implemented_only()
