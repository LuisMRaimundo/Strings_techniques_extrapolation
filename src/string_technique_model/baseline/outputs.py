"""Baseline output writers (long tables, wide exports, exclusions)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

BASELINE_LONG_COLUMNS = [
    "baseline_cell_id",
    "target_metric_definition_id",
    "instrument",
    "technique",
    "pitch_name_sounding",
    "pitch_midi_sounding",
    "pitch_name_written",
    "pitch_midi_written",
    "dynamic",
    "articulation",
    "string_name",
    "baseline_value",
    "baseline_mean",
    "baseline_median",
    "baseline_sd",
    "baseline_se",
    "baseline_q025",
    "baseline_q500",
    "baseline_q975",
    "number_of_observations",
    "number_of_collections",
    "contributing_collection_ids",
    "collection_values",
    "collection_weights",
    "pooling_method",
    "between_collection_variance",
    "heterogeneity_statistic",
    "metric_conversion_applied",
    "conversion_ids",
    "baseline_reliability_grade",
    "baseline_status",
    "measured_or_estimated",
    "provenance",
    "run_id",
    "created_at_utc",
]


def _serialize_mapping(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, dict):
        return ";".join(f"{k}:{v}" for k, v in sorted(value.items(), key=lambda kv: str(kv[0])))
    return str(value)


def normalize_baseline_long(frame: pd.DataFrame) -> pd.DataFrame:
    out = frame.copy()
    for col in BASELINE_LONG_COLUMNS:
        if col not in out.columns:
            out[col] = np.nan if col.startswith("baseline_") or col.endswith("_variance") else None
    # Ensure uncertainty fields stay null when unavailable (never invent zeros).
    for col in ("baseline_sd", "baseline_se", "baseline_q025", "baseline_q975", "between_collection_variance"):
        if col in out.columns:
            out[col] = out[col].where(out[col].notna(), other=np.nan)
    return out[BASELINE_LONG_COLUMNS]


def write_baseline_outputs(
    baseline_long: pd.DataFrame,
    *,
    output_dir: Path,
    excluded: pd.DataFrame,
    alignment_table: pd.DataFrame,
    provenance_ledger: pd.DataFrame,
    write_wide: bool = True,
) -> dict[str, str]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, str] = {}

    long_norm = normalize_baseline_long(baseline_long)
    # Human-readable serialisations for CSV
    csv_frame = long_norm.copy()
    for col in ("collection_values", "collection_weights", "contributing_collection_ids", "conversion_ids"):
        if col in csv_frame.columns:
            csv_frame[col] = csv_frame[col].map(
                lambda v: _serialize_mapping(v)
                if isinstance(v, dict)
                else (";".join(v) if isinstance(v, list) else v)
            )

    parquet_path = output_dir / "ordinary_baseline_long.parquet"
    csv_path = output_dir / "ordinary_baseline_long.csv"
    long_norm.to_parquet(parquet_path, index=False)
    csv_frame.to_csv(csv_path, index=False)
    paths["ordinary_baseline_long.parquet"] = str(parquet_path)
    paths["ordinary_baseline_long.csv"] = str(csv_path)

    excl_path = output_dir / "excluded_baseline_records.csv"
    excluded.to_csv(excl_path, index=False)
    paths["excluded_baseline_records.csv"] = str(excl_path)

    align_path = output_dir / "alignment_table.parquet"
    alignment_table.to_parquet(align_path, index=False)
    paths["alignment_table.parquet"] = str(align_path)

    led_path = output_dir / "baseline_provenance_ledger.csv"
    provenance_ledger.to_csv(led_path, index=False)
    paths["baseline_provenance_ledger.csv"] = str(led_path)

    if write_wide and not long_norm.empty:
        by_dir = output_dir / "by_instrument"
        by_dir.mkdir(parents=True, exist_ok=True)
        for instrument, part in long_norm.groupby("instrument"):
            inst = str(instrument)
            if inst not in {"vln", "vla", "vlc", "cb"}:
                continue
            wide = part.pivot_table(
                index="pitch_midi_sounding",
                columns="dynamic",
                values="baseline_value",
                aggfunc="first",
            )
            out_xlsx = by_dir / f"{inst}_baseline.xlsx"
            wide.to_excel(out_xlsx)
            paths[f"by_instrument/{inst}_baseline.xlsx"] = str(out_xlsx)

    return paths


def scientific_frames_equivalent(a: pd.DataFrame, b: pd.DataFrame, value_cols: list[str]) -> bool:
    """Compare scientific columns between CSV/Parquet loads."""
    if len(a) != len(b):
        return False
    cols = [c for c in value_cols if c in a.columns and c in b.columns]
    aa = a.sort_values("baseline_cell_id").reset_index(drop=True) if "baseline_cell_id" in a.columns else a
    bb = b.sort_values("baseline_cell_id").reset_index(drop=True) if "baseline_cell_id" in b.columns else b
    for col in cols:
        av = aa[col]
        bv = bb[col]
        if pd.api.types.is_numeric_dtype(av) or pd.api.types.is_numeric_dtype(bv):
            if not np.allclose(
                pd.to_numeric(av, errors="coerce").fillna(np.nan),
                pd.to_numeric(bv, errors="coerce").fillna(np.nan),
                equal_nan=True,
                rtol=1e-9,
                atol=1e-9,
            ):
                return False
        else:
            if not (av.astype(str).fillna("") == bv.astype(str).fillna("")).all():
                return False
    return True


def dump_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str), encoding="utf-8")
