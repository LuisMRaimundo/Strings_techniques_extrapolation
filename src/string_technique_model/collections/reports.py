from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class CollectionInventory:
    collection_id: str
    display_name: str
    enabled: bool
    format: str
    data_paths: list[str]
    n_files_found: int
    n_raw_rows: int | None = None
    columns: list[str] = field(default_factory=list)
    notes: str | None = None
    default_role: str | None = None
    default_roles: list[str] = field(default_factory=list)
    metric_definition_id: str | None = None
    collection_type: str | None = None
    measured_or_estimated: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationReport:
    collection_id: str
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    n_records: int = 0
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class CompatibilityReport:
    collection_id: str
    target_metric_definition_id: str
    status: str
    reason: str
    n_records: int = 0
    per_metric_status: dict[str, str] = field(default_factory=dict)
    required_conversion: str | None = None
    uncertainty_introduced: str | None = None
    allowed_operations: list[str] = field(default_factory=list)
    prohibited_operations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
