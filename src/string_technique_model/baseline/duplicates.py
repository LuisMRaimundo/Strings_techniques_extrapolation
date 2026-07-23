"""Deterministic observation fingerprints and duplicate handling (SHA-256 only)."""

from __future__ import annotations

import hashlib
from typing import Any

import pandas as pd


def _part(value: Any) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)) or pd.isna(value):
        return ""
    return str(value)


def observation_fingerprint(row: pd.Series | dict[str, Any]) -> str:
    """SHA-256 fingerprint for an observation (do not use salted builtin hashing)."""
    if hasattr(row, "get"):
        get = row.get
    else:

        def get(k: str, d: Any = None) -> Any:
            return row[k] if k in row else d
    parts = [
        _part(get("collection_id")),
        _part(get("source_file")),
        _part(get("source_sheet")),
        _part(get("source_row")),
        _part(get("original_record_id") or get("record_id")),
        _part(get("instrument")),
        _part(get("technique")),
        _part(get("pitch_midi_sounding") if get("pitch_midi_sounding") is not None else get("pitch_name_sounding")),
        _part(get("dynamic")),
        _part(get("metric_definition_id")),
        _part(get("density_value")),
    ]
    payload = "|".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def annotate_fingerprints(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        out = frame.copy()
        out["observation_fingerprint"] = pd.Series(dtype=str)
        return out
    out = frame.copy()
    out["observation_fingerprint"] = [observation_fingerprint(row) for _, row in out.iterrows()]
    return out


def collapse_exact_import_duplicates(frame: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Collapse exact duplicate fingerprints within the same collection.

    Exact duplicate imports must not increase sample size. Rows that share a
    fingerprint but differ in legitimate provenance fields across different
    collections are retained separately (different collection_id in fingerprint).
    """
    if frame.empty:
        empty = frame.copy()
        return empty, empty

    work = annotate_fingerprints(frame)
    work = work.sort_values(
        [c for c in ("collection_id", "source_row", "record_id") if c in work.columns],
        kind="mergesort",
    )
    duplicated_mask = work.duplicated(subset=["observation_fingerprint"], keep="first")
    kept = work[~duplicated_mask].copy()
    dropped = work[duplicated_mask].copy()
    if not dropped.empty:
        dropped["eligible_for_baseline"] = False
        dropped["baseline_exclusion_reason"] = "exact_duplicate_import"
        dropped["baseline_validation_status"] = "duplicate_collapsed"
        dropped["duplicate_class"] = "exact_duplicate_import"
    kept["duplicate_class"] = "unique_or_primary"
    return kept, dropped


def classify_repeat_observations(frame: pd.DataFrame, alignment_key: list[str]) -> pd.DataFrame:
    """Mark legitimate repeated measurements that share an analytical cell."""
    if frame.empty:
        return frame.copy()
    out = frame.copy()
    key_cols = [c for c in alignment_key if c in out.columns]
    if not key_cols:
        out["repeat_observation"] = False
        return out
    counts = out.groupby(key_cols, dropna=False)["observation_fingerprint"].transform("count")
    out["repeat_observation"] = counts > 1
    return out
