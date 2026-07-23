"""Instrument-specific metadata helpers."""

from string_technique_model.instruments.cello import CELLO
from string_technique_model.instruments.double_bass import DOUBLE_BASS
from string_technique_model.instruments.viola import VIOLA
from string_technique_model.instruments.violin import VIOLIN

INSTRUMENTS = {
    "vln": VIOLIN,
    "vla": VIOLA,
    "vlc": CELLO,
    "cb": DOUBLE_BASS,
}

__all__ = ["INSTRUMENTS", "VIOLIN", "VIOLA", "CELLO", "DOUBLE_BASS"]
