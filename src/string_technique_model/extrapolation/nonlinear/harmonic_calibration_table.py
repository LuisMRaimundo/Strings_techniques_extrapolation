"""Measured EWSD lookup for calibrated harmonic descriptor predictions."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any

import pandas as pd

from string_technique_model.baseline.pitch import pitch_name_to_midi

_REPO_ROOT = Path(__file__).resolve().parents[4]
_DEFAULT_MEASURED_DIR = _REPO_ROOT / "data" / "harmonic_calibration" / "measured"
_MAX_NEAREST_SEMITONES = 3

_INSTRUMENT_ALIASES = {
    "violin": "vln",
    "vln": "vln",
    "viola": "vla",
    "vla": "vla",
    "cello": "vlc",
    "violoncello": "vlc",
    "vlc": "vlc",
    "double_bass": "cb",
    "contrabass": "cb",
    "cb": "cb",
}


def _norm_inst(instrument: str) -> str:
    return _INSTRUMENT_ALIASES.get(str(instrument).strip().lower(), str(instrument).strip().lower())


def _norm_tech(technique: str) -> str:
    t = str(technique).strip().lower()
    if t in {"arco_artificial_harmonic", "art_harm", "artificial"}:
        return "artificial_harmonic"
    if t in {"arco_natural_harmonic", "nat_harm", "natural"}:
        return "natural_harmonic"
    return t


@lru_cache(maxsize=4)
def load_calibrated_harmonic_table(measured_dir: str | None = None) -> pd.DataFrame:
    """Load and merge measured harmonic EWSD CSVs (excludes *_smoke)."""
    root = Path(measured_dir) if measured_dir else _DEFAULT_MEASURED_DIR
    if not root.is_dir():
        return pd.DataFrame(
            columns=["instrument", "technique", "dynamic", "note", "value", "collection"]
        )
    frames: list[pd.DataFrame] = []
    for path in sorted(root.glob("*.csv")):
        if path.stem.endswith("_smoke"):
            continue
        df = pd.read_csv(path)
        if "value" not in df.columns or "note" not in df.columns:
            continue
        df = df.copy()
        df["instrument"] = df.get("instrument", "vln").map(_norm_inst)
        df["technique"] = df["technique"].map(_norm_tech)
        df["dynamic"] = df["dynamic"].astype(str).str.strip().str.lower()
        df["note"] = df["note"].astype(str).str.strip()
        df["value"] = pd.to_numeric(df["value"], errors="coerce")
        df = df[df["value"].notna()]
        if "collection" not in df.columns:
            df["collection"] = path.stem
        frames.append(df)
    if not frames:
        return pd.DataFrame(
            columns=["instrument", "technique", "dynamic", "note", "value", "collection"]
        )
    out = pd.concat(frames, ignore_index=True)
    # Prefer later collections only for identical keys by averaging duplicates
    out = (
        out.groupby(["instrument", "technique", "dynamic", "note"], as_index=False)
        .agg(value=("value", "mean"), collection=("collection", lambda s: "+".join(sorted(set(s)))))
    )
    return out


def clear_calibrated_harmonic_table_cache() -> None:
    load_calibrated_harmonic_table.cache_clear()


def has_calibrated_harmonic_coverage(
    instrument: str,
    technique: str,
    *,
    measured_dir: str | None = None,
) -> bool:
    table = load_calibrated_harmonic_table(measured_dir)
    if table.empty:
        return False
    inst = _norm_inst(instrument)
    tech = _norm_tech(technique)
    return bool(((table["instrument"] == inst) & (table["technique"] == tech)).any())


def lookup_calibrated_harmonic(
    *,
    instrument: str,
    technique: str,
    note: str,
    dynamic: str,
    ordinary_by_dynamic: dict[str, float] | None = None,
    measured_dir: str | None = None,
) -> dict[str, Any] | None:
    """Return measured or dynamic-transferred EWSD for one harmonic target.

    Preference: exact (note, dynamic) hit; else same note at another dynamic with
    ordinary ratio transfer when ``ordinary_by_dynamic`` provides both dynamics.
    """
    table = load_calibrated_harmonic_table(measured_dir)
    if table.empty:
        return None
    inst = _norm_inst(instrument)
    tech = _norm_tech(technique)
    requested_note = str(note).strip()
    note_s = requested_note
    dyn = str(dynamic).strip().lower()
    sub = table[(table["instrument"] == inst) & (table["technique"] == tech)]
    if sub.empty:
        return None

    nearest_semitones: int | None = None
    exact = sub[(sub["note"] == note_s) & (sub["dynamic"] == dyn)]
    if not exact.empty:
        row = exact.iloc[0]
        return {
            "mean": float(row["value"]),
            "sd": None,
            "source_dynamic": dyn,
            "source_note": note_s,
            "transfer": "exact_measured",
            "collection": str(row.get("collection") or ""),
            "measured_or_extrapolated": "measured",
        }

    note_rows = sub[sub["note"] == note_s]
    if note_rows.empty:
        target_midi = pitch_name_to_midi(note_s)
        if target_midi is None:
            return None
        best_note = None
        best_dist: float | None = None
        for cand in sub["note"].astype(str).unique():
            cand_midi = pitch_name_to_midi(cand)
            if cand_midi is None:
                continue
            dist = abs(float(cand_midi) - float(target_midi))
            if best_dist is None or dist < best_dist:
                best_dist = dist
                best_note = str(cand)
        if best_note is None or best_dist is None or best_dist > _MAX_NEAREST_SEMITONES:
            return None
        note_s = best_note
        nearest_semitones = int(round(best_dist))
        note_rows = sub[sub["note"] == note_s]
        if note_rows.empty:
            return None

    # Prefer mf, then p, then any available dynamic for ratio transfer
    preferred = ["mf", "p", "mp", "pp", "f", "ff"]
    src_dyn = None
    src_val = None
    src_collection = ""
    for d in preferred:
        hit = note_rows[note_rows["dynamic"] == d]
        if not hit.empty:
            src_dyn = d
            src_val = float(hit.iloc[0]["value"])
            src_collection = str(hit.iloc[0].get("collection") or "")
            break
    if src_dyn is None:
        src_dyn = str(note_rows.iloc[0]["dynamic"])
        src_val = float(note_rows.iloc[0]["value"])
        src_collection = str(note_rows.iloc[0].get("collection") or "")

    def _pack(
        *,
        mean: float,
        sd: float | None,
        transfer: str,
        measured_or_extrapolated: str,
    ) -> dict[str, Any]:
        if nearest_semitones is not None:
            transfer = f"{transfer}+nearest_note"
            measured_or_extrapolated = "extrapolated"
            if sd is None:
                sd = abs(mean) * 0.2
            else:
                sd = max(float(sd), abs(mean) * 0.2)
        return {
            "mean": float(mean),
            "sd": sd,
            "source_dynamic": src_dyn,
            "source_note": note_s,
            "requested_note": requested_note,
            "nearest_semitones": nearest_semitones,
            "transfer": transfer,
            "collection": src_collection,
            "measured_or_extrapolated": measured_or_extrapolated,
        }

    if src_dyn == dyn and nearest_semitones is None:
        return _pack(
            mean=src_val,
            sd=None,
            transfer="exact_measured",
            measured_or_extrapolated="measured",
        )

    ord_map = {str(k).lower(): float(v) for k, v in (ordinary_by_dynamic or {}).items() if v}
    if src_dyn in ord_map and dyn in ord_map and ord_map[src_dyn] > 0:
        transferred = src_val * (ord_map[dyn] / ord_map[src_dyn])
        return _pack(
            mean=float(transferred),
            sd=abs(transferred) * 0.15,
            transfer="ordinary_dynamic_ratio",
            measured_or_extrapolated="extrapolated",
        )

    # No ordinary ratio available: soft-family passthrough (p↔pp↔mp), else use the
    # calibrated source-dynamic value as an explicit proxy (GUI often has only one
    # ordinary dynamic filled — previously this returned None and looked "broken").
    if {src_dyn, dyn} <= {"p", "pp", "mp"}:
        return _pack(
            mean=src_val,
            sd=abs(src_val) * 0.2,
            transfer="nearby_dynamic_passthrough",
            measured_or_extrapolated="extrapolated",
        )
    return _pack(
        mean=src_val,
        sd=abs(src_val) * 0.25,
        transfer="calibrated_source_dynamic_proxy",
        measured_or_extrapolated="extrapolated",
    )
