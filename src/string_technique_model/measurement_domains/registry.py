"""Measurement-domain registry loaded from YAML."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from string_technique_model.config import PACKAGE_ROOT, load_yaml, resolve_path

DEFAULT_PATH = PACKAGE_ROOT / "configs" / "measurement_domains.yaml"

REQUIRED_DOMAIN_IDS = frozenset(
    {
        "radiated_audio",
        "bridge_force",
        "string_velocity_at_bow",
        "bridge_mobility",
        "body_acceleration",
        "unresolved",
    }
)


class MeasurementDomainSpec(BaseModel):
    """Single measurement-domain entry."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    id: str
    label: str
    description: str
    notes: str


class MeasurementDomainRegistry(BaseModel):
    """Versioned registry of observation domains for acoustic/mechanical quantities."""

    model_config = ConfigDict(extra="allow")

    version: str | None = None
    schema_version: str | None = None
    domains: list[MeasurementDomainSpec] = Field(default_factory=list)

    def get(self, domain_id: str) -> MeasurementDomainSpec | None:
        for domain in self.domains:
            if domain.id == domain_id:
                return domain
        return None

    def ids(self) -> frozenset[str]:
        return frozenset(d.id for d in self.domains)


def load_measurement_domain_registry(
    path: Path | str | None = None,
) -> MeasurementDomainRegistry:
    data = load_yaml(resolve_path(path or DEFAULT_PATH))
    domains = [MeasurementDomainSpec.model_validate(item) for item in data.get("domains", [])]
    registry = MeasurementDomainRegistry(
        version=data.get("version"),
        schema_version=data.get("schema_version"),
        domains=domains,
    )
    missing = REQUIRED_DOMAIN_IDS - registry.ids()
    if missing:
        raise ValueError(f"measurement_domains.yaml missing required ids: {sorted(missing)}")
    return registry


@lru_cache(maxsize=1)
def _default_registry() -> MeasurementDomainRegistry:
    return load_measurement_domain_registry()


def get_measurement_domain(domain_id: str) -> MeasurementDomainSpec | None:
    return _default_registry().get(domain_id)
