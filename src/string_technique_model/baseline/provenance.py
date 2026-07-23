"""Baseline provenance ledger construction and verification."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def _parse_weights(raw: Any) -> dict[str, float]:
    if isinstance(raw, dict):
        return {str(k): float(v) for k, v in raw.items()}
    if isinstance(raw, str) and raw.strip():
        weights: dict[str, float] = {}
        for part in raw.split(";"):
            if ":" in part:
                k, v = part.split(":", 1)
                weights[k.strip()] = float(v)
        return weights
    return {}


def build_provenance_ledger(
    eligible: pd.DataFrame,
    excluded: pd.DataFrame,
    baseline_long: pd.DataFrame,
) -> pd.DataFrame:
    """One row per baseline cell × contributing (or excluded) record."""
    rows: list[dict[str, Any]] = []

    cell_coll_weights: dict[str, dict[str, float]] = {}
    if not baseline_long.empty:
        for _, brow in baseline_long.iterrows():
            cell_id = str(brow.get("baseline_cell_id") or "")
            cell_coll_weights[cell_id] = _parse_weights(brow.get("collection_weights"))

    within_counts: dict[tuple[str, str], int] = {}
    if not eligible.empty and "baseline_cell_id" in eligible.columns:
        for keys, part in eligible.groupby(["baseline_cell_id", "collection_id"], dropna=False):
            if not isinstance(keys, tuple):
                continue
            cell_id, coll = str(keys[0]), str(keys[1])
            within_counts[(cell_id, coll)] = int(len(part))

    def _emit(frame: pd.DataFrame, *, included: bool) -> None:
        if frame.empty:
            return
        for _, row in frame.iterrows():
            cell_id = str(row.get("baseline_cell_id") or "")
            coll = str(row.get("collection_id") or "")
            coll_w = float(cell_coll_weights.get(cell_id, {}).get(coll, 0.0))
            n_within = max(within_counts.get((cell_id, coll), 1 if included else 0), 1)
            within_w = (1.0 / n_within) if included else 0.0
            effective = within_w * coll_w if included else 0.0
            rows.append(
                {
                    "baseline_cell_id": cell_id,
                    "canonical_record_id": row.get("record_id"),
                    "collection_id": coll,
                    "source_file": row.get("source_file"),
                    "source_sheet": row.get("source_sheet"),
                    "source_row": row.get("source_row"),
                    "original_record_id": row.get("original_record_id") or row.get("record_id"),
                    "original_density_value": row.get("original_density_value", row.get("density_value")),
                    "converted_density_value": row.get("converted_density_value", row.get("density_value")),
                    "metric_definition_id": row.get("metric_definition_id"),
                    "conversion_id": row.get("conversion_id"),
                    "within_collection_weight": within_w,
                    "collection_weight": coll_w,
                    "final_effective_weight": effective,
                    "inclusion_status": "included" if included else "excluded",
                    "exclusion_reason": "" if included else row.get("baseline_exclusion_reason"),
                    "measured_or_estimated": row.get("measured_or_estimated"),
                }
            )

    _emit(eligible, included=True)
    _emit(excluded, included=False)
    return pd.DataFrame(rows)


def verify_weight_sums(
    ledger: pd.DataFrame,
    *,
    atol: float = 1e-6,
) -> dict[str, Any]:
    """Verify that included effective weights sum to ~1 per cell for weighted methods."""
    if ledger.empty:
        return {"ok": True, "cells_checked": 0, "failures": []}
    included = ledger[ledger["inclusion_status"] == "included"]
    failures: list[str] = []
    cells = 0
    for cell_id, part in included.groupby("baseline_cell_id"):
        if not cell_id:
            continue
        if float(part["collection_weight"].fillna(0).abs().sum()) <= 0:
            continue
        total = float(part["final_effective_weight"].fillna(0).sum())
        cells += 1
        if total > 0 and abs(total - 1.0) > atol:
            failures.append(f"{cell_id!s}: effective_weight_sum={total}")
    return {"ok": len(failures) == 0, "cells_checked": cells, "failures": failures}


def reconstruct_cell_value(
    ledger: pd.DataFrame,
    baseline_cell_id: str,
    collection_level_values: dict[str, float],
) -> float | None:
    """Reconstruct pooled value from collection weights in the ledger."""
    part = ledger[
        (ledger["baseline_cell_id"] == baseline_cell_id)
        & (ledger["inclusion_status"] == "included")
    ]
    if part.empty:
        return None
    weights = part.groupby("collection_id")["collection_weight"].first().astype(float).to_dict()
    if not weights:
        vals = list(collection_level_values.values())
        return float(np.mean(vals)) if vals else None
    total = 0.0
    for coll_id, weight in weights.items():
        key = str(coll_id)
        if key in collection_level_values:
            total += float(weight) * float(collection_level_values[key])
    return total
