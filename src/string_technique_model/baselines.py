"""Compatibility wrappers around the Phase-2 ordinary baseline engine."""

from __future__ import annotations

from typing import Any

import pandas as pd

from string_technique_model.baseline.pipeline import build_ordinary_baseline
from string_technique_model.collections.leakage import assert_role_separation
from string_technique_model.collections.service import load_imported_or_ingest


def resolve_run_collections(cfg: dict[str, Any]) -> dict[str, Any]:
    run = cfg.get("run") or {}
    baseline_ids = list(
        run.get("baseline_collection_ids")
        or run.get("baseline_collections")
        or cfg.get("baseline_collection_ids")
        or []
    )
    calibration_ids = list(
        run.get("calibration_collection_ids") or run.get("calibration_collections") or []
    )
    validation_ids = list(
        run.get("validation_collection_ids") or run.get("validation_collections") or []
    )
    pooling = dict(run.get("pooling") or {})
    baseline = dict(run.get("baseline") or {})
    if not baseline_ids:
        raise ValueError(
            "No baseline_collection_ids configured under run:. "
            "Register collections in configs/collections.yaml and select them in configs/run.yaml."
        )
    role_report = assert_role_separation(baseline_ids, calibration_ids, validation_ids)
    role_report.raise_if_conflict()
    return {
        "baseline_collection_ids": baseline_ids,
        "calibration_collection_ids": calibration_ids,
        "validation_collection_ids": validation_ids,
        "pooling": pooling,
        "baseline": baseline,
        "target_metric_definition_id": str(run.get("target_metric_definition_id") or "ewsd_v1"),
    }


def build_baseline_table(
    cfg: dict[str, Any],
    *,
    baseline_collection_ids: list[str] | None = None,
    run_config_path=None,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Build ordinary baseline via the Phase-2 engine (no special-technique estimation)."""
    resolved = resolve_run_collections(cfg)
    baseline_ids = baseline_collection_ids or resolved["baseline_collection_ids"]
    pooling_cfg = resolved["pooling"]
    bcfg = resolved["baseline"]
    method = str(
        bcfg.get("pooling_method")
        or pooling_cfg.get("method")
        or "hierarchical_collection"
    )
    result = build_ordinary_baseline(
        run_config_path,
        collection_ids=baseline_ids,
        metric_definition_id=resolved["target_metric_definition_id"],
        pooling_method=method,
        dry_run=True,
        overwrite=True,
    )
    meta = {
        "run_id": result.run_id,
        "pooling_method": method,
        "n_cells": int(len(result.baseline_long)),
        "n_excluded": int(len(result.excluded)),
        "warnings": result.warnings,
        "target_metric_definition_id": resolved["target_metric_definition_id"],
    }
    return result.baseline_long, meta


def lookup_pooled_density(
    baseline: pd.DataFrame,
    *,
    instrument: str,
    dynamic: str,
    note: str | None = None,
    pitch_midi_sounding: float | int | None = None,
    pitch_name_sounding: str | None = None,
) -> dict[str, Any] | None:
    """Lookup ordinary baseline density for a cell (legacy estimate/pipeline API)."""
    if baseline is None or baseline.empty:
        return None
    work = baseline[
        (baseline["instrument"].astype(str) == instrument)
        & (baseline["dynamic"].astype(str) == dynamic)
    ]
    pitch_name = pitch_name_sounding or note
    if pitch_midi_sounding is not None and "pitch_midi_sounding" in work.columns:
        work = work[work["pitch_midi_sounding"] == pitch_midi_sounding]
    elif pitch_name is not None and "pitch_name_sounding" in work.columns:
        work = work[work["pitch_name_sounding"].astype(str) == str(pitch_name)]
    if work.empty:
        return None
    row = work.iloc[0]
    val = row.get("baseline_value")
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return None
    return {
        "ordinary_density": float(val),
        "baseline_cell_id": row.get("baseline_cell_id"),
        "pooling_method": row.get("pooling_method"),
        "measured_or_estimated": row.get("measured_or_estimated"),
        "contributing_collection_ids": row.get("contributing_collection_ids"),
        "baseline_status": row.get("baseline_status"),
    }


def load_validation_frame(cfg: dict[str, Any], run_config_path=None) -> pd.DataFrame:
    resolved = resolve_run_collections(cfg)
    ids = resolved["validation_collection_ids"]
    if not ids:
        return pd.DataFrame()
    return load_imported_or_ingest(ids, run_config_path)
