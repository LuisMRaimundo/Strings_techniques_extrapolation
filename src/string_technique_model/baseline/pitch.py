"""Sounding-pitch helpers for baseline alignment."""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

_NOTE_RE = re.compile(
    r"^\s*([A-Ga-g])([#♯b♭]?)(-?\d+)\s*$"
)

_PC = {
    "C": 0,
    "D": 2,
    "E": 4,
    "F": 5,
    "G": 7,
    "A": 9,
    "B": 11,
}


def pitch_name_to_midi(name: Any) -> float | None:
    """Convert scientific pitch names (e.g. A4, G#3, Bb2) to MIDI numbers."""
    if name is None or (isinstance(name, float) and pd.isna(name)) or pd.isna(name):
        return None
    text = str(name).strip().replace("♯", "#").replace("♭", "b")
    if not text:
        return None
    # Already numeric?
    try:
        val = float(text)
        if 0 <= val <= 127:
            return val
    except ValueError:
        pass
    m = _NOTE_RE.match(text)
    if not m:
        return None
    letter, accidental, octave_s = m.groups()
    pc = _PC[letter.upper()]
    if accidental in {"#"}:
        pc += 1
    elif accidental in {"b"}:
        pc -= 1
    midi = (int(octave_s) + 1) * 12 + pc
    if midi < 0 or midi > 127:
        return None
    return float(midi)


def ensure_sounding_midi(frame: pd.DataFrame) -> pd.DataFrame:
    """Fill pitch_midi_sounding from pitch_name_sounding when MIDI is missing."""
    if frame.empty:
        return frame.copy()
    out = frame.copy()
    if "pitch_midi_sounding" not in out.columns:
        out["pitch_midi_sounding"] = pd.NA
    out["pitch_midi_sounding"] = pd.to_numeric(out["pitch_midi_sounding"], errors="coerce")
    missing = out["pitch_midi_sounding"].isna()
    if missing.any() and "pitch_name_sounding" in out.columns:
        derived = out.loc[missing, "pitch_name_sounding"].map(pitch_name_to_midi)
        out.loc[missing, "pitch_midi_sounding"] = derived
        # Track derivation without inventing measurements of density
        if "pitch_midi_source" not in out.columns:
            out["pitch_midi_source"] = "source"
        out.loc[missing & out["pitch_midi_sounding"].notna(), "pitch_midi_source"] = "derived_from_pitch_name"
    return out
