"""Pitch-mode models and deterministic legacy migration."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

PitchMode = Literal[
    "single_note",
    "pitch_range",
    "multiple_notes",
    "open_string",
    "unpitched_or_noise",
    "unknown",
]

PITCH_MODES: tuple[PitchMode, ...] = (
    "single_note",
    "pitch_range",
    "multiple_notes",
    "open_string",
    "unpitched_or_noise",
    "unknown",
)

PitchRepresentation = Literal["written", "sounding", "both", "unresolved"]


class PitchModeState(BaseModel):
    """GUI/domain pitch payload — stored on MetadataEntryRecord."""

    model_config = ConfigDict(extra="allow")

    pitch_mode: PitchMode = "unknown"
    pitch_representation: PitchRepresentation = "unresolved"
    # single_note
    pitch_name: str | None = None
    pitch_letter: str | None = None
    pitch_accidental: str | None = None
    pitch_octave: int | None = None
    pitch_midi: float | None = None
    # range
    pitch_lowest_name: str | None = None
    pitch_lowest_midi: float | None = None
    pitch_highest_name: str | None = None
    pitch_highest_midi: float | None = None
    # multiple
    pitch_names: list[str] = Field(default_factory=list)
    pitch_midis: list[float] = Field(default_factory=list)
    pitch_sequence_ordered: bool = False
    # open string
    open_string_name: str | None = None
    open_string_tuning: str | None = None
    open_string_written: str | None = None
    open_string_sounding: str | None = None
    # written / sounding (never overwrite silently)
    pitch_name_written: str | None = None
    pitch_midi_written: float | None = None
    pitch_name_sounding: str | None = None
    pitch_midi_sounding: float | None = None
    derived_fields: list[str] = Field(default_factory=list)
    original_inputs: dict[str, Any] = Field(default_factory=dict)


def pitch_fields_for_mode(mode: PitchMode) -> list[str]:
    """Which editor fields are relevant for a pitch mode."""
    common = ["pitch_mode", "pitch_representation"]
    mapping: dict[PitchMode, list[str]] = {
        "single_note": common
        + [
            "pitch_name",
            "pitch_letter",
            "pitch_accidental",
            "pitch_octave",
            "pitch_midi",
            "pitch_name_written",
            "pitch_name_sounding",
            "pitch_midi_written",
            "pitch_midi_sounding",
        ],
        "pitch_range": common
        + [
            "pitch_lowest_name",
            "pitch_highest_name",
            "pitch_lowest_midi",
            "pitch_highest_midi",
            "pitch_name_written",
            "pitch_name_sounding",
        ],
        "multiple_notes": common
        + ["pitch_names", "pitch_midis", "pitch_sequence_ordered"],
        "open_string": common
        + [
            "open_string_name",
            "open_string_tuning",
            "open_string_written",
            "open_string_sounding",
            "string_name",
        ],
        "unpitched_or_noise": common,
        "unknown": common,
    }
    return mapping[mode]


def migrate_legacy_pitch_fields(row: dict[str, Any]) -> dict[str, Any]:
    """Deterministically migrate legacy single-pitch rows.

    - Existing pitch → pitch_mode = single_note
    - Null pitch → pitch_mode = unknown (unless explicitly unpitched)
    - Never infer ranges from isolated notes
    """
    out = dict(row)
    if out.get("pitch_mode") in PITCH_MODES:
        return out

    explicit_unpitched = str(out.get("pitch_class") or out.get("sound_class") or "").lower() in {
        "unpitched",
        "noise",
        "unpitched_or_noise",
    }
    has_pitch = any(
        out.get(k) not in (None, "", [])
        for k in (
            "pitch_name_sounding",
            "pitch_midi_sounding",
            "pitch_name_written",
            "pitch_midi_written",
            "pitch_name",
            "pitch_midi",
        )
    )

    provenance = list(out.get("migration_provenance") or [])
    if not isinstance(provenance, list):
        provenance = [str(provenance)]

    if explicit_unpitched:
        out["pitch_mode"] = "unpitched_or_noise"
        provenance.append("legacy_explicit_unpitched→unpitched_or_noise")
    elif has_pitch:
        out["pitch_mode"] = "single_note"
        # Prefer sounding as primary display name when present
        if out.get("pitch_name") in (None, "") and out.get("pitch_name_sounding"):
            out["pitch_name"] = out.get("pitch_name_sounding")
            provenance.append("legacy_pitch_name←pitch_name_sounding")
        if out.get("pitch_midi") in (None, "") and out.get("pitch_midi_sounding") is not None:
            out["pitch_midi"] = out.get("pitch_midi_sounding")
            provenance.append("legacy_pitch_midi←pitch_midi_sounding")
        provenance.append("legacy_single_pitch→pitch_mode=single_note")
    else:
        out["pitch_mode"] = "unknown"
        provenance.append("legacy_null_pitch→pitch_mode=unknown")

    if out.get("pitch_representation") in (None, ""):
        written = out.get("pitch_name_written") or out.get("pitch_midi_written")
        sounding = out.get("pitch_name_sounding") or out.get("pitch_midi_sounding")
        if written and sounding:
            out["pitch_representation"] = "both"
        elif written:
            out["pitch_representation"] = "written"
        elif sounding:
            out["pitch_representation"] = "sounding"
        else:
            out["pitch_representation"] = "unresolved"
        provenance.append(f"legacy_pitch_representation={out['pitch_representation']}")

    out["migration_provenance"] = provenance
    return out
