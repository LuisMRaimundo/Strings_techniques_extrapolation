"""Legacy JSON baseline/holdout helpers for GUI browsing only.

Phase-1 collection ingestion must use configs/collections.yaml + CollectionAdapter.
Do not add IOWA/ORCHIDEA branches here.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from string_technique_model.config import load_yaml, resolve_path

# Legacy fixed filenames — not used by the generic collection import path.
INSTRUMENT_FILE_MAP = {
    "vln": "violin_ordinary_cdm.json",
    "violin": "violin_ordinary_cdm.json",
    "vla": "viola_ordinary_cdm.json",
    "viola": "viola_ordinary_cdm.json",
    "vlc": "cello_ordinary_cdm.json",
    "cello": "cello_ordinary_cdm.json",
    "violoncello": "cello_ordinary_cdm.json",
    "cb": "double_bass_ordinary_cdm.json",
    "double_bass": "double_bass_ordinary_cdm.json",
    "contrabass": "double_bass_ordinary_cdm.json",
    "bass": "double_bass_ordinary_cdm.json",
}

INSTRUMENT_CODE = {
    "violin": "vln",
    "vln": "vln",
    "viola": "vla",
    "vla": "vla",
    "cello": "vlc",
    "violoncello": "vlc",
    "vlc": "vlc",
    "double_bass": "cb",
    "contrabass": "cb",
    "bass": "cb",
    "cb": "cb",
}

INSTRUMENT_DISPLAY = {
    "vln": "Violin",
    "vla": "Viola",
    "vlc": "Cello",
    "cb": "Double bass",
}

TECHNIQUE_DISPLAY = {
    "artificial_harmonic": "Artificial harmonic",
    "sul_ponticello": "Sul ponticello",
    "sul_tasto": "Sul tasto",
    "con_sordino": "Con sordino",
    "ordinary_arco": "Ordinary arco",
}

HOLDOUT_FILE_MAP = {
    ("vln", "artificial_harmonic"): "violin_artificial_harmonic.json",
    ("vln", "sul_ponticello"): "violin_sul_ponticello.json",
    ("vln", "con_sordino"): "violin_con_sordino.json",
}


def normalize_instrument(instrument: str) -> str:
    key = instrument.strip().lower().replace(" ", "_")
    if key not in INSTRUMENT_CODE:
        raise KeyError(f"Unknown instrument: {instrument!r}")
    return INSTRUMENT_CODE[key]


def load_baseline(instrument: str, baselines_dir: Path | str) -> dict[str, Any]:
    code = normalize_instrument(instrument)
    path = Path(baselines_dir) / INSTRUMENT_FILE_MAP[code]
    if not path.exists():
        raise FileNotFoundError(f"Baseline not found: {path}")
    data = json.loads(path.read_text(encoding="utf-8"))
    data["_path"] = str(path)
    data["_instrument_code"] = code
    return data


def load_all_baselines(baselines_dir: Path | str) -> dict[str, dict[str, Any]]:
    out = {}
    for code in ("vln", "vla", "vlc", "cb"):
        out[code] = load_baseline(code, baselines_dir)
    return out


def get_density(baseline: dict[str, Any], note: str, dynamic: str) -> float | None:
    spectral = baseline.get("spectral_data") or {}
    cell = spectral.get(note)
    if cell is None:
        return None
    value = cell.get(dynamic)
    if value is None:
        return None
    return float(value)


def list_notes(baseline: dict[str, Any]) -> list[str]:
    return list((baseline.get("spectral_data") or {}).keys())


def list_dynamics(baseline: dict[str, Any], note: str | None = None) -> list[str]:
    spectral = baseline.get("spectral_data") or {}
    if note is None:
        dyns: set[str] = set()
        for cell in spectral.values():
            dyns.update(cell.keys())
        return sorted(dyns)
    cell = spectral.get(note) or {}
    return list(cell.keys())


def load_holdout(
    instrument: str,
    technique: str,
    holdout_dir: Path | str,
) -> dict[str, Any] | None:
    code = normalize_instrument(instrument)
    filename = HOLDOUT_FILE_MAP.get((code, technique))
    if filename is None:
        return None
    path = Path(holdout_dir) / filename
    if not path.exists():
        return None
    data = json.loads(path.read_text(encoding="utf-8"))
    data["_path"] = str(path)
    data["_instrument_code"] = code
    return data


def load_instruments_config(path: Path | str) -> dict[str, Any]:
    return load_yaml(resolve_path(path))


def flatten_spectral_table(
    spectral_data: dict[str, dict[str, float]],
    *,
    instrument: str,
    technique: str,
    source: str,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for note, dyn_map in spectral_data.items():
        for dynamic, value in dyn_map.items():
            rows.append(
                {
                    "instrument": instrument,
                    "technique": technique,
                    "note": note,
                    "dynamic": dynamic,
                    "density": None if value is None else float(value),
                    "source": source,
                }
            )
    return rows
