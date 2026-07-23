"""Hierarchical collection model (offline random-effects approximation)."""

from __future__ import annotations

from typing import Any

import numpy as np

from string_technique_model.baseline.meta_analysis import random_effects_meta_analysis
from string_technique_model.baseline.single_collection import aggregate_within_collection


def hierarchical_collection(
    collection_values: dict[str, np.ndarray],
    *,
    within_method: str = "no_aggregation",
) -> dict[str, Any]:
    """Approximate y_ijk = mu + collection_j + replicate_k + error.

    Uses a DerSimonian–Laird random-effects estimator over collection means when
    within-collection replication supports variance estimates. When only one
    collection contributes, returns that collection's aggregate without claiming
    between-collection precision.
    """
    if not collection_values:
        return {
            "baseline_value": None,
            "collection_level_values": {},
            "collection_weights": {},
            "within_collection_sample_sizes": {},
            "number_of_contributing_collections": 0,
            "status": "empty",
        }

    # Prefer arithmetic means at collection level for the hierarchical stage.
    means: dict[str, float] = {}
    sizes: dict[str, int] = {}
    for cid, values in collection_values.items():
        method = "arithmetic_mean" if within_method == "no_aggregation" else within_method
        summary = aggregate_within_collection(values, method=method)
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

    if len(means) == 1:
        cid = next(iter(means))
        arr = np.asarray(collection_values[cid], dtype=float)
        arr = arr[np.isfinite(arr)]
        sd = float(np.std(arr, ddof=1)) if arr.size > 1 else None
        se = float(sd / np.sqrt(arr.size)) if sd is not None else None
        return {
            "baseline_value": means[cid],
            "baseline_mean": means[cid],
            "baseline_median": float(np.median(arr)) if arr.size else means[cid],
            "baseline_sd": sd,
            "baseline_se": se,
            "baseline_q025": None,
            "baseline_q500": float(np.median(arr)) if arr.size else means[cid],
            "baseline_q975": None,
            "collection_level_values": means,
            "collection_weights": {cid: 1.0},
            "within_collection_sample_sizes": sizes,
            "number_of_contributing_collections": 1,
            "between_collection_variance": None,
            "heterogeneity_statistic": None,
            "status": "single_collection",
            "uncertainty_status": "within_collection_only",
        }

    # If any collection lacks replication, fall back to equal-collection mean
    # without inventing variances.
    if any(sizes[cid] < 2 for cid in means):
        k = len(means)
        weights = {cid: 1.0 / k for cid in means}
        pooled = float(sum(means.values()) / k)
        vals = np.array(list(means.values()), dtype=float)
        return {
            "baseline_value": pooled,
            "baseline_mean": pooled,
            "baseline_median": float(np.median(vals)),
            "baseline_sd": float(np.std(vals, ddof=1)) if len(vals) > 1 else None,
            "baseline_se": None,
            "baseline_q025": None,
            "baseline_q500": float(np.median(vals)),
            "baseline_q975": None,
            "collection_level_values": means,
            "collection_weights": weights,
            "within_collection_sample_sizes": sizes,
            "number_of_contributing_collections": k,
            "between_collection_variance": float(np.var(vals, ddof=1)) if len(vals) > 1 else None,
            "heterogeneity_statistic": None,
            "status": "pooled_equal_fallback",
            "uncertainty_status": "insufficient_variance_information",
            "pooling_status": "insufficient_variance_information_used_equal_collection_mean",
        }

    result = random_effects_meta_analysis(collection_values, within_method="arithmetic_mean")
    result["baseline_mean"] = result.get("baseline_value")
    vals = np.array(list(result.get("collection_level_values", {}).values()), dtype=float)
    result["baseline_median"] = float(np.median(vals)) if vals.size else result.get("baseline_value")
    result["baseline_q500"] = result["baseline_median"]
    result["baseline_sd"] = float(np.std(vals, ddof=1)) if vals.size > 1 else None
    if "uncertainty_status" not in result:
        result["uncertainty_status"] = "random_effects"
    return result
