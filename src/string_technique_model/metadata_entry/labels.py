"""Human-readable labels for metadata fields (internal names unchanged)."""

from __future__ import annotations

FIELD_LABELS: dict[str, str] = {
    "record_id": "Record ID",
    "audio_file": "Audio / source file",
    "source_file": "Audio / source file",
    "instrument": "Instrument",
    "technique": "Technique (legacy label)",
    "technique_display": "Technique summary",
    "left_hand_regime": "Left-hand regime",
    "bow_contact_regime": "Bow-contact regime",
    "mute_state": "Mute state",
    "articulation": "Articulation",
    "additional_technique": "Additional technique",
    "dynamic": "Dynamic",
    "pitch_mode": "Pitch mode",
    "pitch_representation": "Written / sounding",
    "pitch_name": "Pitch",
    "pitch_midi": "MIDI",
    "pitch_name_written": "Written pitch",
    "pitch_midi_written": "Written MIDI",
    "pitch_name_sounding": "Sounding pitch",
    "pitch_midi_sounding": "Sounding MIDI",
    "pitch_lowest_name": "Lowest pitch",
    "pitch_highest_name": "Highest pitch",
    "pitch_names": "Pitch list",
    "string_name": "String",
    "performer_id": "Performer",
    "take": "Take",
    "notes": "Notes / comments",
    "comments": "Notes / comments",
    "validation_status": "Validation",
}

DEFAULT_TABLE_COLUMNS: list[str] = [
    "record_id",
    "source_file",
    "instrument",
    "technique_display",
    "dynamic",
    "pitch_mode",
    "pitch_name_sounding",
    "string_name",
    "performer_id",
    "take",
    "notes",
    "validation_status",
]

DYNAMICS_ORDERED: list[str] = [
    "ppp",
    "pp",
    "p",
    "mp",
    "mf",
    "f",
    "ff",
    "fff",
    "variable",
    "unknown",
]


def label_for(field: str) -> str:
    return FIELD_LABELS.get(field, field.replace("_", " ").title())
