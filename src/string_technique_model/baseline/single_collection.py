"""Within-collection aggregation for single-collection baselines."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

WITHIN_METHODS = {
    "no_aggregation",
    "arithmetic_mean",
    "median",
    "inverse_variance_mean",
    "hierarchical_replicate_model",
}


def aggregate_within_collection(
    values: np.ndarray,
    *,
    method: str = "no_aggregation",
    variances: np.ndarray | None = None,
) -> dict[str, Any]:
    if method not in WITHIN_METHODS:
        raise ValueError(f"Unknown within-collection aggregation: {method}")
    arr = np.asarray(values, dtype=float)
    arr = arr[np.isfinite(arr)]
    if arr.size == 0:
        return {
            "value": None,
            "mean": None,
            "median": None,
            "sd": None,
            "n": 0,
            "method": method,
            "status": "empty",
        }

    mean = float(np.mean(arr))
    median = float(np.median(arr))
    sd = float(np.std(arr, ddof=1)) if arr.size > 1 else None

    if method == "no_aggregation":
        # Preserve observations: representative value is the mean for table cells,
        # but n remains the full observation count (caller retains rows for provenance).
        value = mean
        status = "no_aggregation"
    elif method == "arithmetic_mean":
        value = mean
        status = "aggregated"
    elif method == "median":
        value = median
        status = "aggregated"
    elif method == "inverse_variance_mean":
        if variances is None or not np.all(np.isfinite(variances)) or np.any(np.asarray(variances) <= 0):
            return {
                "value": None,
                "mean": mean,
                "median": median,
                "sd": sd,
                "n": int(arr.size),
                "method": method,
                "status": "insufficient_variance_information",
            }
        w = 1.0 / np.asarray(variances, dtype=float)
        value = float(np.sum(w * arr) / np.sum(w))
        status = "aggregated"
    else:  # hierarchical_replicate_model approximation: mean with replicate sd
        value = mean
        status = "hierarchical_replicate_approx" if arr.size > 1 else "single_replicate"

    return {
        "value": value,
        "mean": mean,
        "median": median,
        "sd": sd,
        "n": int(arr.size),
        "method": method,
        "status": status,
    }


def collection_cell_summary(
    group: pd.DataFrame,
    *,
    within_method: str = "no_aggregation",
) -> dict[str, Any]:
    values = group["density_value"].astype(float).to_numpy()
    var_col = "density_variance" if "density_variance" in group.columns else None
    variances = group[var_col].astype(float).to_numpy() if var_col else None
    summary = aggregate_within_collection(values, method=within_method, variances=variances)
    summary["collection_id"] = str(group["collection_id"].iloc[0])
    return summary
