"""Explicit evidence-package models (scientific authority = curated files)."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from string_technique_model.literature.domain import (
    ALLOWED_INSTRUMENTS,
    ALLOWED_TECHNIQUES,
    DIRECTNESS_VALUES,
    EXTRACT_VERIFICATION_STATUSES,
    PARAMETER_STATUSES,
)


class LiteratureSourceModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    source_id: str
    source_type: str
    full_citation: str
    evidence_status: str
    local_file_path: str | None = None
    instruments_covered: list[str] = Field(default_factory=list)
    techniques_covered: list[str] = Field(default_factory=list)

    def is_verified(self) -> bool:
        return self.evidence_status == "verified_local_source"

    def is_usable_bibliography(self) -> bool:
        return self.evidence_status not in {"excluded", "incomplete_reference"}


class EvidenceExtractModel(BaseModel):
    model_config = ConfigDict(extra="allow", populate_by_name=True)

    evidence_id: str
    source_id: str
    instrument: str | None = None
    technique: str | None = None
    page_start: int | str | None = None
    page_end: int | str | None = None
    table_number: str | None = None
    figure_number: str | None = None
    equation_number: str | None = None
    section_title: str | None = None
    canonical_variable_name: str | None = Field(default=None, alias="canonical_variable")
    original_variable_name: str | None = None
    paraphrased_claim: str
    quantitative_or_qualitative: str
    reported_value: float | None = None
    reported_lower_bound: float | None = None
    reported_upper_bound: float | None = None
    original_unit: str | None = None
    canonical_unit: str | None = None
    operation_type: str | None = None
    numerical_scale: str | None = None
    directness: str
    density_mapping_status: str | None = None
    curator_verification_status: str = "unverified"
    mute_type: str | None = None
    harmonic_type: str | None = None

    @field_validator("directness")
    @classmethod
    def _d(cls, v: str) -> str:
        if v not in DIRECTNESS_VALUES:
            raise ValueError(f"Invalid directness: {v}")
        return v

    @field_validator("curator_verification_status")
    @classmethod
    def _c(cls, v: str) -> str:
        s = str(v).lower()
        if s not in EXTRACT_VERIFICATION_STATUSES:
            raise ValueError(f"Invalid curator_verification_status: {v}")
        return s

    def has_location(self) -> bool:
        return any(
            [
                self.page_start is not None,
                self.table_number,
                self.figure_number,
                self.equation_number,
                self.section_title,
            ]
        )

    def is_quantitative(self) -> bool:
        return str(self.quantitative_or_qualitative).lower().startswith("quant")

    def is_curator_verified(self) -> bool:
        return self.curator_verification_status == "validated"

    def unit(self) -> str | None:
        return self.canonical_unit or self.original_unit


class PhysicalMechanismModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    instrument: str
    technique: str
    mechanism_name: str
    supported: bool | str
    status: str
    evidence_ids: list[str] = Field(default_factory=list)
    reason: str | None = None
    numerical_parameter_status: str | None = None


class LiteratureParameterModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    parameter_id: str
    parameter_name: str | None = None
    instrument: str | None = None
    technique: str | None = None
    model_component: str | None = None
    operation_type: str | None = None
    numerical_scale: str | None = None
    reported_value: float | None = None
    reported_lower_bound: float | None = None
    reported_upper_bound: float | None = None
    unit: str | None = None
    source_ids: list[str] = Field(default_factory=list)
    evidence_ids: list[str] = Field(default_factory=list)
    density_mapping_status: str | None = None
    parameter_status: str | None = None
    active_for_density_prediction: bool = False
    applicable_pitch_min: float | None = None
    applicable_pitch_max: float | None = None
    applicable_frequency_min_hz: float | None = None
    applicable_frequency_max_hz: float | None = None
    applicable_register: str | None = None
    applicable_dynamic: str | None = None
    applicable_string: str | None = None
    applicable_temporal_region: str | None = None
    applicable_mute_type: str | None = None
    applicable_harmonic_type: str | None = None
    direct_or_transferred: str | None = None
    transfer_source_instrument: str | None = None
    transfer_equation: str | None = None
    notes: str | None = None

    @field_validator("parameter_status")
    @classmethod
    def _ps(cls, v: str | None) -> str | None:
        if v is None:
            return v
        if v not in PARAMETER_STATUSES:
            raise ValueError(f"Invalid parameter_status: {v}")
        return v

    def normalize_lists(self) -> None:
        if isinstance(self.source_ids, str):
            self.source_ids = [x for x in str(self.source_ids).split(";") if x]
        if isinstance(self.evidence_ids, str):
            self.evidence_ids = [x for x in str(self.evidence_ids).split(";") if x]


class DensityMappingModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    source_variable: str
    canonical_variable_name: str | None = None
    mapping_status: str
    notes: str | None = None


class EvidenceMatrixCellModel(BaseModel):
    model_config = ConfigDict(extra="allow")

    instrument: str
    technique: str
    source_count: int = 0
    evidence_extract_count: int = 0
    quantitative_extract_count: int = 0
    qualitative_extract_count: int = 0
    direct_same_instrument_count: int = 0
    cross_instrument_count: int = 0
    active_parameter_count: int = 0
    inactive_parameter_count: int = 0
    supported_mechanisms: list[str] = Field(default_factory=list)
    unsupported_components: list[str] = Field(default_factory=list)
    density_mapping_status: str | None = None
    evidence_grade: str = "NA"
    estimation_status: str = "not_estimable_from_current_local_evidence"
    evidence_state: str | None = None

    @field_validator("instrument")
    @classmethod
    def _inst(cls, v: str) -> str:
        if v not in ALLOWED_INSTRUMENTS:
            raise ValueError(v)
        return v

    @field_validator("technique")
    @classmethod
    def _tech(cls, v: str) -> str:
        if v not in ALLOWED_TECHNIQUES:
            raise ValueError(v)
        return v


def as_dict(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(by_alias=True)
