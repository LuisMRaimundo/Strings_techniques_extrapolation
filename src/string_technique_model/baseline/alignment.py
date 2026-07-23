"""Analytical alignment keys and alignment reporting."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from string_technique_model.stable_seed import stable_hex

DEFAULT_ALIGNMENT_KEY = [
    "metric_definition_id",
    "instrument",
    "technique",
    "pitch_midi_sounding",
    "dynamic",
    "articulation",
    "string_name",
]


def normalize_alignment_key(key: list[str] | None) -> list[str]:
    cols = list(key or DEFAULT_ALIGNMENT_KEY)
    if "pitch_midi_sounding" not in cols and "pitch_name_sounding" in cols:
        # Prefer sounding MIDI when only name was configured historically.
        cols = ["pitch_midi_sounding" if c == "pitch_name_sounding" else c for c in cols]
    if "pitch_midi_sounding" not in cols:
        cols.insert(0, "pitch_midi_sounding")
    return cols


def cell_id_from_key(key_values: dict[str, Any]) -> str:
    ordered = sorted((str(k), "" if v is None or (isinstance(v, float) and np.isnan(v)) else str(v)) for k, v in key_values.items())
    payload = "|".join(f"{k}={v}" for k, v in ordered)
    return f"cell_{stable_hex(payload, n_chars=16)}"


def _key_dict(key_cols: list[str], key_vals: Any) -> dict[str, Any]:
    if not isinstance(key_vals, tuple):
        key_vals = (key_vals,)
    return {col: key_vals[i] for i, col in enumerate(key_cols)}


def build_alignment_table(
    eligible: pd.DataFrame,
    *,
    alignment_key: list[str] | None = None,
) -> pd.DataFrame:
    key_cols = normalize_alignment_key(alignment_key)
    key_cols = [c for c in key_cols if c in eligible.columns]
    if eligible.empty or not key_cols:
        return pd.DataFrame(
            columns=[
                *key_cols,
                "baseline_cell_id",
                "n_observations",
                "n_collections",
                "contributing_collection_ids",
                "alignment_status",
            ]
        )

    rows: list[dict[str, Any]] = []
    for key_vals, group in eligible.groupby(key_cols, dropna=False, observed=True):
        key = _key_dict(key_cols, key_vals)
        collections = sorted(group["collection_id"].astype(str).unique().tolist())
        status = "multi_collection" if len(collections) > 1 else "single_collection"
        rows.append(
            {
                **key,
                "baseline_cell_id": cell_id_from_key(key),
                "n_observations": int(len(group)),
                "n_collections": len(collections),
                "contributing_collection_ids": ";".join(collections),
                "alignment_status": status,
            }
        )
    return pd.DataFrame(rows)


def attach_cell_ids(eligible: pd.DataFrame, *, alignment_key: list[str] | None = None) -> pd.DataFrame:
    key_cols = [c for c in normalize_alignment_key(alignment_key) if c in eligible.columns]
    if eligible.empty:
        out = eligible.copy()
        out["baseline_cell_id"] = pd.Series(dtype=str)
        return out
    out = eligible.copy()

    def _cid(row: pd.Series) -> str:
        key = {c: row.get(c) for c in key_cols}
        return cell_id_from_key(key)

    out["baseline_cell_id"] = [_cid(row) for _, row in out.iterrows()]
    return out


def validate_pitch_transposition(frame: pd.DataFrame) -> list[str]:
    """Validate sounding = written + semitones when rule fields exist."""
    warnings: list[str] = []
    if frame.empty:
        return warnings
    needed = {"pitch_midi_written", "pitch_midi_sounding", "written_to_sounding_semitones"}
    if not needed.issubset(frame.columns):
        return warnings
    for idx, row in frame.iterrows():
        w = row.get("pitch_midi_written")
        s = row.get("pitch_midi_sounding")
        t = row.get("written_to_sounding_semitones")
        if pd.isna(w) or pd.isna(s) or pd.isna(t):
            continue
        expected = float(w) + float(t)
        if abs(float(s) - expected) > 1e-6:
            warnings.append(
                f"pitch_transposition_mismatch row={idx} instrument={row.get('instrument')} "
                f"written={w} sounding={s} semitones={t}"
            )
    return warnings


def write_alignment_report(
    path: Path,
    *,
    n_before: int,
    n_eligible: int,
    n_excluded: int,
    alignment_table: pd.DataFrame,
    eligible: pd.DataFrame,
    excluded: pd.DataFrame,
    conflicting_metadata: list[str] | None = None,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    n_cells = int(len(alignment_table))
    single = int((alignment_table["n_collections"] == 1).sum()) if n_cells else 0
    multi = int((alignment_table["n_collections"] > 1).sum()) if n_cells else 0
    dup_cells = int((alignment_table["n_observations"] > 1).sum()) if n_cells else 0
    missing_dyn = 0
    missing_pitch = 0
    if not excluded.empty:
        missing_dyn = int((excluded["baseline_exclusion_reason"] == "missing_dynamic").sum())
        missing_pitch = int((excluded["baseline_exclusion_reason"] == "missing_sounding_pitch").sum())

    lines = [
        "# Baseline alignment report",
        "",
        f"- records before filtering: {n_before}",
        f"- eligible records: {n_eligible}",
        f"- excluded records: {n_excluded}",
        f"- unique analytical cells: {n_cells}",
        f"- cells represented by one collection: {single}",
        f"- cells represented by multiple collections: {multi}",
        "- unmatched cells: 0 (no expected grid fill in this phase)",
        f"- duplicate cells (n_observations > 1): {dup_cells}",
        f"- missing dynamics (excluded): {missing_dyn}",
        f"- missing pitches (excluded): {missing_pitch}",
        f"- conflicting metadata: {len(conflicting_metadata or [])}",
        "",
    ]
    if conflicting_metadata:
        lines.append("## Conflicting metadata")
        lines.extend(f"- {item}" for item in conflicting_metadata)
        lines.append("")
    if not eligible.empty and "instrument" in eligible.columns:
        lines.append("## Eligible instruments")
        for inst, n in eligible["instrument"].astype(str).value_counts().sort_index().items():
            lines.append(f"- {inst}: {n}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
