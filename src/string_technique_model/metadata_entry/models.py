"""Metadata entry records — extend canonical fields without a second incompatible model."""

from __future__ import annotations

import json
import uuid
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from string_technique_model.collections.canonical import CanonicalRecord
from string_technique_model.pitch.modes import PITCH_MODES, migrate_legacy_pitch_fields

SCHEMA_VERSION = "metadata_entry_v1"


class MetadataEntryRecord(BaseModel):
    """One row = one recording / file / excerpt / note / analysis unit.

    Compatible with CanonicalRecord; extra metadata-entry fields are allowed.
    Missing values remain explicitly null / unknown — never silently filled.
    """

    model_config = ConfigDict(extra="allow", str_strip_whitespace=True)

    # --- core visible fields ---
    record_id: str | None = None
    collection_id: str | None = None
    source_file: str | None = None
    audio_file: str | None = None
    instrument: str | None = None
    technique: str | None = None
    technique_display: str | None = None
    left_hand_regime: str | None = None
    bow_contact_regime: str | None = None
    mute_state: str | None = None
    articulation: str | None = None
    additional_technique: str | None = None
    dynamic: str | None = None
    pitch_mode: str | None = "unknown"
    pitch_representation: str | None = "unresolved"
    pitch_name: str | None = None
    pitch_letter: str | None = None
    pitch_accidental: str | None = None
    pitch_octave: int | None = None
    pitch_midi: float | None = None
    pitch_name_written: str | None = None
    pitch_midi_written: float | None = None
    pitch_name_sounding: str | None = None
    pitch_midi_sounding: float | None = None
    pitch_lowest_name: str | None = None
    pitch_lowest_midi: float | None = None
    pitch_highest_name: str | None = None
    pitch_highest_midi: float | None = None
    pitch_names: list[str] | None = None
    pitch_midis: list[float] | None = None
    pitch_sequence_ordered: bool | None = None
    open_string_name: str | None = None
    open_string_tuning: str | None = None
    open_string_written: str | None = None
    open_string_sounding: str | None = None
    string_name: str | None = None
    performer_id: str | None = None
    take: str | None = None
    notes: str | None = None
    # --- harmonic (optional panel) ---
    harmonic_type: str | None = None
    harmonic_order: float | None = None
    touched_interval: str | None = None
    stopped_pitch_name: str | None = None
    stopped_pitch_midi: float | None = None
    touched_pitch_name: str | None = None
    touched_pitch_midi: float | None = None
    sounding_pitch_name: str | None = None
    sounding_pitch_midi: float | None = None
    notation_represents: str | None = None
    # --- bow contact ---
    bow_contact_category: str | None = None
    relative_bow_bridge_distance_beta: float | None = None
    bow_bridge_distance_m: float | None = None
    speaking_length_m: float | None = None
    bow_force_n: float | None = None
    bow_velocity_m_s: float | None = None
    excitation_region: str | None = None
    # --- mute ---
    mute_type: str | None = None
    mute_category: str | None = None
    mute_material: str | None = None
    mute_mass: float | None = None
    mute_model: str | None = None
    mute_geometry: str | None = None
    # --- multiphonic ---
    multiphonic_config_id: str | None = None
    touching_position_ratio: float | None = None
    component_pitches: list[str] | None = None
    observed_partials: list[str] | None = None
    multiphonic_stability: str | None = None
    establishment_time_s: float | None = None
    # --- recording ---
    sample_rate_hz: float | None = None
    bit_depth: int | None = None
    channel_count: int | None = None
    microphone: str | None = None
    mic_distance_m: float | None = None
    room: str | None = None
    gain_db: float | None = None
    recording_date: str | None = None
    # --- bookkeeping ---
    validation_status: str | None = None
    derived_fields: list[str] = Field(default_factory=list)
    migration_provenance: list[str] = Field(default_factory=list)
    schema_version: str = SCHEMA_VERSION
    # keep canonical density fields optional (not required for metadata entry)
    density_value: float | None = None
    metric_definition_id: str | None = None
    missingness_status: str | None = "unknown"
    provenance: str | None = None

    @field_validator("pitch_names", "pitch_midis", "component_pitches", "observed_partials", "derived_fields", "migration_provenance", mode="before")
    @classmethod
    def _parse_listish(cls, value: Any) -> Any:
        if value is None or value == "":
            return None if value is None or value == "" else value
        if isinstance(value, str):
            text = value.strip()
            if not text:
                return None
            if text.startswith("["):
                try:
                    return json.loads(text)
                except json.JSONDecodeError:
                    return [p.strip() for p in text.split(",") if p.strip()]
            return [p.strip() for p in text.split(",") if p.strip()]
        return value

    @classmethod
    def new_empty(cls, *, collection_id: str | None = None) -> MetadataEntryRecord:
        return cls(
            record_id=f"rec_{uuid.uuid4().hex[:10]}",
            collection_id=collection_id,
            pitch_mode="unknown",
            pitch_representation="unresolved",
            dynamic="unknown",
            missingness_status="unknown",
        )

    @classmethod
    def from_mapping(cls, data: dict[str, Any]) -> MetadataEntryRecord:
        migrated = migrate_legacy_pitch_fields(dict(data))
        if migrated.get("audio_file") and not migrated.get("source_file"):
            migrated["source_file"] = migrated["audio_file"]
        if migrated.get("source_file") and not migrated.get("audio_file"):
            migrated["audio_file"] = migrated["source_file"]
        if migrated.get("comments") and not migrated.get("notes"):
            migrated["notes"] = migrated.get("comments")
        if migrated.get("pitch_mode") not in PITCH_MODES:
            migrated["pitch_mode"] = "unknown"
        return cls.model_validate(migrated)

    def to_canonical_dict(self) -> dict[str, Any]:
        """Project onto CanonicalRecord fields (+ extras preserved)."""
        data = self.model_dump()
        if data.get("audio_file") and not data.get("source_file"):
            data["source_file"] = data["audio_file"]
        # Serialize list fields for parquet/csv friendliness
        for key in ("pitch_names", "pitch_midis", "component_pitches", "observed_partials", "derived_fields", "migration_provenance"):
            val = data.get(key)
            if isinstance(val, list):
                data[key] = json.dumps(val, ensure_ascii=False)
        # Ensure collection_id for CanonicalRecord
        if not data.get("collection_id"):
            data["collection_id"] = "untitled_collection"
        # Validate projection against canonical schema (extras allowed on CanonicalRecord)
        CanonicalRecord.model_validate(
            {k: data.get(k) for k in CanonicalRecord.model_fields if k in data or k == "collection_id"}
        )
        return data

    def display_pitch(self) -> str:
        mode = self.pitch_mode or "unknown"
        if mode == "single_note":
            return self.pitch_name_sounding or self.pitch_name or self.pitch_name_written or ""
        if mode == "pitch_range":
            lo = self.pitch_lowest_name or ""
            hi = self.pitch_highest_name or ""
            return f"{lo}–{hi}" if lo or hi else ""
        if mode == "multiple_notes":
            names = self.pitch_names or []
            return ", ".join(names)
        if mode == "open_string":
            return self.open_string_sounding or self.open_string_name or ""
        if mode == "unpitched_or_noise":
            return "unpitched"
        return ""
