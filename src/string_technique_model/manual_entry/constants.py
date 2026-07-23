"""Constants for manual metric entry."""

from __future__ import annotations

ALLOWED_INSTRUMENTS = frozenset({"vln", "vla", "vlc", "cb"})

INSTRUMENT_DISPLAY = {
    "vln": "Violin",
    "vla": "Viola",
    "vlc": "Cello",
    "cb": "Double bass",
}

CANONICAL_TECHNIQUES = frozenset(
    {
        "ordinary",
        "artificial_harmonic",
        "sul_ponticello",
        "sul_tasto",
        "con_sordino",
    }
)

CANONICAL_DYNAMICS = frozenset({"ppp", "pp", "p", "mp", "mf", "f", "ff", "fff"})

COLLECTION_TYPES = frozenset(
    {
        "measured",
        "manually_transcribed",
        "derived",
        "estimated",
        "simulated",
        "pooled_derived",
    }
)

COLLECTION_ROLES = frozenset(
    {
        "baseline",
        "model_calibration",
        "external_validation",
        "descriptive_comparison",
        "sensitivity_analysis",
        "excluded",
    }
)

DEFAULT_ROLE = "descriptive_comparison"

MEASURED_OR_ESTIMATED = frozenset(
    {
        "measured",
        "manually_transcribed",
        "derived",
        "estimated",
        "simulated",
        "pooled_derived",
    }
)

WORKFLOW_STATES = frozenset(
    {
        "draft",
        "validation_failed",
        "validation_warning",
        "ready_to_commit",
        "committed",
        "superseded",
        "deleted_logically",
    }
)

INPUT_METHODS = frozenset(
    {
        "single_form",
        "table_entry",
        "grid_entry",
        "clipboard_paste",
        "copied_from_collection",
    }
)

TECHNIQUE_CONDITIONAL_FIELDS = {
    "artificial_harmonic": {"harmonic_order", "harmonic_type", "stopped_pitch", "touched_pitch", "touched_interval"},
    "con_sordino": {"mute_type", "mute_material", "mute_mass"},
    "sul_ponticello": {"bow_position_ratio", "bow_position_description"},
    "sul_tasto": {"bow_position_ratio", "bow_position_description"},
}
