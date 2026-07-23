"""Complete chromatic pitch registry (MIDI 0–127 by default)."""

from __future__ import annotations

from functools import lru_cache
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from string_technique_model.baseline.pitch import pitch_name_to_midi
from string_technique_model.config import PACKAGE_ROOT, load_yaml

Accidental = Literal["", "#", "b"]

_LETTER_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}
_SHARP_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_FLAT_NAMES = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
_ENHARMONIC: dict[str, list[str]] = {
    "C#": ["Db"],
    "Db": ["C#"],
    "D#": ["Eb"],
    "Eb": ["D#"],
    "F#": ["Gb"],
    "Gb": ["F#"],
    "G#": ["Ab"],
    "Ab": ["G#"],
    "A#": ["Bb"],
    "Bb": ["A#"],
    "E#": ["F"],
    "Fb": ["E"],
    "B#": ["C"],
    "Cb": ["B"],
}


class PitchRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    pitch_id: str
    letter: str
    accidental: str
    octave: int
    scientific_pitch: str
    midi: int
    frequency_hz: float
    enharmonic_equivalents: list[str] = Field(default_factory=list)
    written_pitch: str | None = None
    sounding_pitch: str | None = None


class PitchRegistry:
    """Systematic registry covering a configured MIDI range."""

    def __init__(
        self,
        *,
        midi_min: int = 0,
        midi_max: int = 127,
        a4_hz: float = 440.0,
        prefer_sharps: bool = True,
    ) -> None:
        if midi_min < 0 or midi_max > 127 or midi_min > midi_max:
            raise ValueError("MIDI range must be within 0–127 and ordered")
        self.midi_min = midi_min
        self.midi_max = midi_max
        self.a4_hz = float(a4_hz)
        self.prefer_sharps = prefer_sharps
        self._by_midi: dict[int, PitchRecord] = {}
        self._by_spn: dict[str, PitchRecord] = {}
        self._build()

    def _midi_to_hz(self, midi: int) -> float:
        return self.a4_hz * (2.0 ** ((midi - 69) / 12.0))

    def _build(self) -> None:
        names = _SHARP_NAMES if self.prefer_sharps else _FLAT_NAMES
        for midi in range(self.midi_min, self.midi_max + 1):
            pc = midi % 12
            octave = (midi // 12) - 1
            spn = f"{names[pc]}{octave}"
            letter = names[pc][0]
            accidental = names[pc][1:] if len(names[pc]) > 1 else ""
            enh: list[str] = []
            for alt in _ENHARMONIC.get(names[pc], []):
                enh.append(f"{alt}{octave}")
            # Also store the alternate spelling name for the same MIDI.
            alt_names = _FLAT_NAMES if self.prefer_sharps else _SHARP_NAMES
            alt_spn = f"{alt_names[pc]}{octave}"
            if alt_spn != spn and alt_spn not in enh:
                enh.append(alt_spn)
            rec = PitchRecord(
                pitch_id=f"MIDI_{midi:03d}_{spn}",
                letter=letter,
                accidental=accidental,
                octave=octave,
                scientific_pitch=spn,
                midi=midi,
                frequency_hz=self._midi_to_hz(midi),
                enharmonic_equivalents=enh,
                written_pitch=spn,
                sounding_pitch=spn,
            )
            self._by_midi[midi] = rec
            self._by_spn[spn.upper()] = rec
            self._by_spn[alt_spn.upper()] = rec
            for e in enh:
                self._by_spn[e.upper()] = rec

    def all_pitches(self) -> list[PitchRecord]:
        return [self._by_midi[m] for m in sorted(self._by_midi)]

    def get_by_midi(self, midi: int | float) -> PitchRecord | None:
        try:
            m = int(round(float(midi)))
        except (TypeError, ValueError):
            return None
        return self._by_midi.get(m)

    def get_by_spelling(self, name: str | None) -> PitchRecord | None:
        if not name or not str(name).strip():
            return None
        key = str(name).strip().replace("♯", "#").replace("♭", "b").upper()
        if key in self._by_spn:
            return self._by_spn[key]
        midi = pitch_name_to_midi(name)
        if midi is None:
            return None
        return self.get_by_midi(midi)

    def search(
        self,
        query: str,
        *,
        instrument: str | None = None,
        show_all: bool = False,
        instrument_ranges: dict[str, tuple[int, int]] | None = None,
    ) -> list[PitchRecord]:
        q = (query or "").strip().replace("♯", "#").replace("♭", "b")
        pitches = self.all_pitches()
        if not show_all and instrument and instrument_ranges and instrument in instrument_ranges:
            lo, hi = instrument_ranges[instrument]
            pitches = [p for p in pitches if lo <= p.midi <= hi]
        if not q:
            return pitches
        if q.isdigit() or (q.startswith("-") and q[1:].isdigit()):
            try:
                m = int(q)
            except ValueError:
                m = None
            if m is not None:
                return [p for p in pitches if p.midi == m]
        qu = q.upper()
        return [
            p
            for p in pitches
            if qu in p.scientific_pitch.upper()
            or qu in p.pitch_id.upper()
            or any(qu in e.upper() for e in p.enharmonic_equivalents)
            or qu == str(p.midi)
        ]

    def filter_instrument_range(
        self,
        instrument: str,
        *,
        show_all: bool = False,
        instrument_ranges: dict[str, tuple[int, int]] | None = None,
    ) -> list[PitchRecord]:
        return self.search("", instrument=instrument, show_all=show_all, instrument_ranges=instrument_ranges)

    def to_dicts(self) -> list[dict[str, Any]]:
        return [p.model_dump() for p in self.all_pitches()]


def load_instrument_midi_ranges(path: str | None = None) -> dict[str, tuple[int, int]]:
    data = load_yaml(path or (PACKAGE_ROOT / "configs" / "instruments.yaml"))
    out: dict[str, tuple[int, int]] = {}
    for key, spec in (data.get("instruments") or {}).items():
        rng = spec.get("sounding_range_midi") or spec.get("written_range_midi")
        if isinstance(rng, list) and len(rng) == 2:
            out[str(key)] = (int(rng[0]), int(rng[1]))
    return out


@lru_cache(maxsize=1)
def get_default_pitch_registry() -> PitchRegistry:
    return PitchRegistry(midi_min=0, midi_max=127, a4_hz=440.0, prefer_sharps=True)


def midi_to_pitch_record(midi: int | float, registry: PitchRegistry | None = None) -> PitchRecord | None:
    reg = registry or get_default_pitch_registry()
    return reg.get_by_midi(midi)
