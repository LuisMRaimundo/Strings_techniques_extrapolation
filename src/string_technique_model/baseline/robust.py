"""Robust pooling estimators."""

from __future__ import annotations

from typing import Any

import numpy as np

from string_technique_model.baseline.single_collection import aggregate_within_collection


def robust_median(
    collection_values: dict[str, np.ndarray],
    *,
    within_method: str = "arithmetic_mean",
) -> dict[str, Any]:
    means: dict[str, float] = {}
    sizes: dict[str, int] = {}
    for cid, values in collection_values.items():
        summary = aggregate_within_collection(values, method=within_method)
        if summary["value"] is None:
            continue
        means[cid] = float(summary["value"])
        sizes[cid] = int(summary["n"])
    if not means:
        return {
            "baseline_value": None,
            "collection_level_values": {},
            "collection_weights": {},
            "within_collection_sample_sizes": {},
            "number_of_contributing_collections": 0,
            "status": "empty",
        }
    vals = np.array(list(means.values()), dtype=float)
    baseline = float(np.median(vals))
    # Equal diagnostic weights (median is not a linear weighted mean).
    weights = {cid: 1.0 / len(means) for cid in means}
    hetero = float(np.std(vals, ddof=1)) if len(vals) > 1 else None
    return {
        "baseline_value": baseline,
        "collection_level_values": means,
        "collection_weights": weights,
        "within_collection_sample_sizes": sizes,
        "number_of_contributing_collections": len(means),
        "between_collection_variance": float(np.var(vals, ddof=1)) if len(vals) > 1 else None,
        "heterogeneity_statistic": hetero,
        "status": "pooled",
    }
