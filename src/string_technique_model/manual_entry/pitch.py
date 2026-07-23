"""Pitch helpers for manual entry (written vs sounding for double bass)."""

from __future__ import annotations

import math
from typing import Any

from string_technique_model.baseline.pitch import pitch_name_to_midi


def midi_to_pitch_name(midi: float | int | None) -> str | None:
    if midi is None:
        return None
    try:
        m = int(round(float(midi)))
    except (TypeError, ValueError):
        return None
    if m < 0 or m > 127:
        return None
    names = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
    octave = (m // 12) - 1
    return f"{names[m % 12]}{octave}"


def hz_to_midi(hz: float | None) -> float | None:
    if hz is None:
        return None
    try:
        f = float(hz)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(f) or f <= 0:
        return None
    return 69.0 + 12.0 * math.log2(f / 440.0)


def midi_to_hz(midi: float | None) -> float | None:
    if midi is None:
        return None
    try:
        m = float(midi)
    except (TypeError, ValueError):
        return None
    if not math.isfinite(m):
        return None
    return 440.0 * (2.0 ** ((m - 69.0) / 12.0))


def resolve_pitch_fields(
    *,
    pitch_name: str | None = None,
    pitch_midi: float | None = None,
    fundamental_hz: float | None = None,
) -> dict[str, Any]:
    """Fill unambiguous pitch representations; report inconsistencies."""
    name = pitch_name.strip() if isinstance(pitch_name, str) and pitch_name.strip() else None
    midi = float(pitch_midi) if pitch_midi is not None and str(pitch_midi) != "" else None
    hz = float(fundamental_hz) if fundamental_hz is not None and str(fundamental_hz) != "" else None

    derived_midi_from_name = pitch_name_to_midi(name) if name else None
    derived_midi_from_hz = hz_to_midi(hz) if hz is not None else None

    errors: list[str] = []
    if midi is None:
        if derived_midi_from_name is not None:
            midi = float(derived_midi_from_name)
        elif derived_midi_from_hz is not None:
            midi = float(derived_midi_from_hz)
    else:
        if derived_midi_from_name is not None and abs(midi - derived_midi_from_name) > 0.51:
            errors.append("pitch_name_midi_inconsistent")
        if derived_midi_from_hz is not None and abs(midi - derived_midi_from_hz) > 0.51:
            errors.append("frequency_midi_inconsistent")

    if name is None and midi is not None:
        name = midi_to_pitch_name(midi)
    if hz is None and midi is not None:
        hz = midi_to_hz(midi)

    return {
        "pitch_name_sounding": name,
        "pitch_midi_sounding": midi,
        "fundamental_hz": hz,
        "errors": errors,
        "ok": not errors and (name is not None or midi is not None),
    }


def apply_cb_transposition(
    *,
    written_name: str | None,
    written_midi: float | None,
    sounding_name: str | None,
    sounding_midi: float | None,
    transposition_semitones: int | None,
    confirmed: bool,
) -> dict[str, Any]:
    """Resolve double-bass written/sounding pitches with explicit transposition."""
    notes: list[str] = []
    errors: list[str] = []
    w_midi = written_midi
    if w_midi is None and written_name:
        w_midi = pitch_name_to_midi(written_name)
    s_midi = sounding_midi
    if s_midi is None and sounding_name:
        s_midi = pitch_name_to_midi(sounding_name)

    if transposition_semitones is not None and w_midi is not None:
        calc = float(w_midi) + float(transposition_semitones)
        if s_midi is None:
            if not confirmed:
                errors.append("cb_sounding_pitch_confirmation_required")
            s_midi = calc
            notes.append(f"sounding_midi_from_written_plus_{transposition_semitones}")
        elif abs(float(s_midi) - calc) > 0.51:
            errors.append("cb_written_sounding_transposition_inconsistent")

    if w_midi is not None and s_midi is not None and float(w_midi) == float(s_midi):
        notes.append("cb_written_equals_sounding_check_octave_transposition")

    return {
        "pitch_name_written": written_name or midi_to_pitch_name(w_midi),
        "pitch_midi_written": w_midi,
        "pitch_name_sounding": sounding_name or midi_to_pitch_name(s_midi),
        "pitch_midi_sounding": s_midi,
        "errors": errors,
        "notes": notes,
        "ok": not errors,
    }
