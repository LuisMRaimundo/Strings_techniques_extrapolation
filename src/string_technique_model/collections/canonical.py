"""Canonical imported-record schema (Pydantic) and column inventory."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, field_validator


class MissingnessStatus(str, Enum):
    observed = "observed"
    missing_by_design = "missing_by_design"
    missing_in_source = "missing_in_source"
    not_applicable = "not_applicable"
    unknown = "unknown"


PHASE1_REQUIRED_COLUMNS: list[str] = [
    "record_id",
    "collection_id",
    "collection_display_name",
    "collection_type",
    "source_file",
    "source_sheet",
    "source_table",
    "source_row",
    "instrument",
    "technique",
    "pitch_name_written",
    "pitch_midi_written",
    "pitch_name_sounding",
    "pitch_midi_sounding",
    "fundamental_hz",
    "string_name",
    "dynamic",
    "articulation",
    "performer_id",
    "instrument_id",
    "mute_type",
    "mute_material",
    "mute_mass",
    "harmonic_type",
    "harmonic_order",
    "stopped_pitch_name",
    "stopped_pitch_midi",
    "touched_pitch_name",
    "touched_pitch_midi",
    "density_value",
    "density_unit",
    "metric_definition_id",
    "metric_version",
    "analysis_window_id",
    "normalisation_id",
    "frequency_range_id",
    "measured_or_estimated",
    "missingness_status",
    "provenance",
    "import_timestamp_utc",
    "schema_mapping_version",
    "transformations_applied",
    "conversions_applied",
    "validation_warnings",
]

CANONICAL_COLUMNS: list[str] = [
    *PHASE1_REQUIRED_COLUMNS,
    # Quality / usability annotations (filled after validation)
    "schema_validity_status",
    "metric_compatibility_status",
    "metadata_completeness_score",
    "provenance_completeness_score",
    "collection_quality_grade",
    "usable_as_baseline",
    "usable_for_pooling",
    "usable_for_calibration",
    "usable_for_validation",
    "usable_for_prediction",
    "missing_by_design_fields",
    "comparability_grade",
    "instrument_mapping_status",
    "technique_mapping_status",
    "original_instrument_label",
    "exclusion_reason",
]

REQUIRED_FOR_MINIMAL_USER_TABLE = [
    "collection_id",
    "instrument",
    "technique",
    "pitch_name_sounding",
    "dynamic",
    "density_value",
    "metric_definition_id",
]

POOLING_KEY_DEFAULT = [
    "metric_definition_id",
    "instrument",
    "technique",
    "pitch_name_sounding",
    "dynamic",
    "articulation",
    "string_name",
    "analysis_window_id",
    "normalisation_id",
]


class CanonicalRecord(BaseModel):
    """Explicit canonical row model. Unavailable fields remain null."""

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    record_id: str | None = None
    collection_id: str
    collection_display_name: str | None = None
    collection_type: str | None = None
    source_file: str | None = None
    source_sheet: str | None = None
    source_table: str | None = None
    source_row: int | None = None
    instrument: str | None = None
    technique: str | None = None
    pitch_name_written: str | None = None
    pitch_midi_written: float | None = None
    pitch_name_sounding: str | None = None
    pitch_midi_sounding: float | None = None
    fundamental_hz: float | None = None
    string_name: str | None = None
    dynamic: str | None = None
    articulation: str | None = None
    performer_id: str | None = None
    instrument_id: str | None = None
    mute_type: str | None = None
    mute_material: str | None = None
    mute_mass: float | None = None
    harmonic_type: str | None = None
    harmonic_order: float | None = None
    stopped_pitch_name: str | None = None
    stopped_pitch_midi: float | None = None
    touched_pitch_name: str | None = None
    touched_pitch_midi: float | None = None
    density_value: float | None = None
    density_unit: str | None = None
    metric_definition_id: str | None = None
    metric_version: str | None = None
    analysis_window_id: str | None = None
    normalisation_id: str | None = None
    frequency_range_id: str | None = None
    measured_or_estimated: str | None = None
    missingness_status: str | None = MissingnessStatus.unknown.value
    provenance: str | None = None
    import_timestamp_utc: str | None = None
    schema_mapping_version: str | None = None
    transformations_applied: str | None = None
    conversions_applied: str | None = None
    validation_warnings: str | None = None

    @field_validator("density_value", "mute_mass", "fundamental_hz", mode="before")
    @classmethod
    def _empty_to_none(cls, value: Any) -> Any:
        if value is None:
            return None
        if isinstance(value, str) and value.strip() == "":
            return None
        return value

    @field_validator("density_value")
    @classmethod
    def _forbid_silent_zero_for_missing(cls, value: float | None) -> float | None:
        # Missing must stay null. Zero is allowed only if truly observed as 0.0.
        return value


def validate_canonical_frame(rows: list[dict[str, Any]]) -> list[CanonicalRecord]:
    return [CanonicalRecord.model_validate(row) for row in rows]
