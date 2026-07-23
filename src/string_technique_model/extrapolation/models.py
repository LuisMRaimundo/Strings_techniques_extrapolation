"""Schemas for narrow extrapolation inputs/outputs."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ValueKind = Literal[
    "measured",
    "derived_from_measured",
    "literature_bounded",
    "extrapolated",
    "qualitative_only",
    "unavailable",
]

EvidenceStatus = Literal[
    "measured_baseline",
    "literature_supported",
    "literature_insufficient",
    "mapping_unavailable",
    "out_of_scope",
    "secondary_synthesis_qualitative",
]


def _coerce_mute_state(value: Any) -> str | None:
    """YAML may parse bare off/on as bool; normalize to mute vocabulary."""
    if value is None:
        return None
    if value is False:
        return "off"
    if value is True:
        return "on"
    return str(value)


class LiteratureEvidenceEntry(BaseModel):
    model_config = ConfigDict(extra="allow")

    evidence_id: str
    source_id: str | None = None
    source_page: str | None = None
    instrument: str | None = None
    technique: str | None = None
    mute_state: str | None = None
    measurement_domain: str | None = None
    conditions: str | None = None
    target_quantity: str
    supported_relation: str | None = None
    value_kind: ValueKind
    unit: str | None = None
    qualitative_value: str | None = None
    numerical_value: float | None = None
    lower_bound: float | None = None
    upper_bound: float | None = None
    amplitude_or_power: str | None = None
    density_mapping_status: str | None = None
    transferability: str | None = None
    assumptions: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    @field_validator("mute_state", mode="before")
    @classmethod
    def _mute_state(cls, v: Any) -> str | None:
        return _coerce_mute_state(v)


class TargetSpec(BaseModel):
    model_config = ConfigDict(extra="allow")

    instrument: str
    technique: str
    dynamic: str
    mute_state: str | None = None
    transformation: str | None = None
    target_quantity: str

    @field_validator("mute_state", mode="before")
    @classmethod
    def _mute_state(cls, v: Any) -> str | None:
        return _coerce_mute_state(v)


class ExtrapolationCell(BaseModel):
    """One auditable output cell."""

    model_config = ConfigDict(extra="allow")

    instrument: str
    technique: str
    dynamic: str
    target_quantity: str
    value: Any = None
    lower_bound: float | None = None
    upper_bound: float | None = None
    unit: str | None = None
    value_kind: ValueKind
    evidence_status: EvidenceStatus
    source: str | None = None
    source_page: str | None = None
    measurement_domain: str | None = None
    extrapolation_method: str
    baseline_record_ids: list[str] = Field(default_factory=list)
    uncertainty: str | None = None
    measured_or_extrapolated: Literal["measured", "extrapolated", "unavailable"]
    assumptions_used: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    mute_state: str | None = None
    evidence_id: str | None = None
    baseline_ewsd_mean: float | None = None
    na_reason: str | None = None

    def to_row(self) -> dict[str, Any]:
        d = self.model_dump()
        d["baseline_record_ids"] = ";".join(self.baseline_record_ids)
        d["assumptions_used"] = ";".join(self.assumptions_used)
        d["warnings"] = ";".join(self.warnings)
        return d
