"""Pooling method dispatcher for ordinary-bowing baselines."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from string_technique_model.baseline.equal_collection import equal_collection_mean
from string_technique_model.baseline.hierarchical import hierarchical_collection
from string_technique_model.baseline.meta_analysis import (
    fixed_effect_meta_analysis,
    random_effects_meta_analysis,
)
from string_technique_model.baseline.robust import robust_median
from string_technique_model.baseline.single_collection import aggregate_within_collection
from string_technique_model.baseline.weighted import (
    inverse_variance_weighting,
    sample_size_weighting,
    user_weighted_mean,
)

POOLING_METHODS = {
    "no_pooling",
    "equal_collection_mean",
    "equal_mean",  # alias
    "user_weighted_mean",
    "inverse_variance_weighting",
    "sample_size_weighting",
    "robust_median",
    "fixed_effect_meta_analysis",
    "random_effects_meta_analysis",
    "hierarchical_collection",
}


def normalize_pooling_method(method: str) -> str:
    if method == "equal_mean":
        return "equal_collection_mean"
    if method == "random_effects_meta_analytic_pooling":
        return "random_effects_meta_analysis"
    return method


def _collection_value_map(group: pd.DataFrame) -> dict[str, np.ndarray]:
    out: dict[str, np.ndarray] = {}
    if group.empty or "collection_id" not in group.columns or "density_value" not in group.columns:
        return out
    for cid, part in group.groupby("collection_id"):
        arr = part["density_value"].astype(float).to_numpy()
        arr = arr[np.isfinite(arr)]
        if arr.size:
            out[str(cid)] = arr
    return out


def pool_cell(
    group: pd.DataFrame,
    *,
    method: str,
    user_weights: dict[str, float] | None = None,
    within_method: str = "no_aggregation",
) -> dict[str, Any]:
    method = normalize_pooling_method(method)
    if method not in POOLING_METHODS and method != "equal_collection_mean":
        raise ValueError(f"Unknown pooling method: {method}")

    collection_values = _collection_value_map(group)
    all_vals = (
        np.concatenate(list(collection_values.values())) if collection_values else np.asarray([])
    )

    if method == "no_pooling":
        if not collection_values:
            return {
                "baseline_value": None,
                "collection_level_values": {},
                "collection_weights": {},
                "within_collection_sample_sizes": {},
                "number_of_contributing_collections": 0,
                "status": "empty",
            }
        # Deterministic first collection only; do not label as cross-collection pooled.
        cid = sorted(collection_values)[0]
        summary = aggregate_within_collection(
            collection_values[cid],
            method="arithmetic_mean" if within_method == "no_aggregation" else within_method,
        )
        return {
            "baseline_value": summary["value"],
            "baseline_mean": summary["mean"],
            "baseline_median": summary["median"],
            "baseline_sd": summary["sd"],
            "baseline_se": None,
            "baseline_q025": None,
            "baseline_q500": summary["median"],
            "baseline_q975": None,
            "collection_level_values": {cid: float(summary["value"])} if summary["value"] is not None else {},
            "collection_weights": {cid: 1.0},
            "within_collection_sample_sizes": {cid: int(summary["n"])},
            "number_of_contributing_collections": 1,
            "status": "single_collection" if len(collection_values) == 1 else "no_pooling_first_collection",
            "measured_label": "not_pooled_across_collections",
        }

    if method == "equal_collection_mean":
        result = equal_collection_mean(collection_values, within_method="arithmetic_mean")
    elif method == "user_weighted_mean":
        result = user_weighted_mean(
            collection_values,
            user_weights or {},
            within_method="arithmetic_mean",
        )
    elif method == "sample_size_weighting":
        result = sample_size_weighting(collection_values, within_method="arithmetic_mean")
    elif method == "inverse_variance_weighting":
        result = inverse_variance_weighting(collection_values, within_method="arithmetic_mean")
    elif method == "robust_median":
        result = robust_median(collection_values, within_method="arithmetic_mean")
    elif method == "fixed_effect_meta_analysis":
        result = fixed_effect_meta_analysis(collection_values, within_method="arithmetic_mean")
    elif method == "random_effects_meta_analysis":
        result = random_effects_meta_analysis(collection_values, within_method="arithmetic_mean")
    elif method == "hierarchical_collection":
        result = hierarchical_collection(collection_values, within_method=within_method)
    else:
        raise ValueError(f"Unhandled pooling method: {method}")

    # Fill common summary fields when absent.
    result.setdefault("baseline_mean", result.get("baseline_value"))
    if all_vals.size:
        result.setdefault("baseline_median", float(np.median(all_vals)))
        result.setdefault(
            "baseline_sd",
            float(np.std(all_vals, ddof=1)) if all_vals.size > 1 else None,
        )
        result.setdefault("baseline_q500", float(np.median(all_vals)))
    result.setdefault("baseline_se", None)
    result.setdefault("baseline_q025", None)
    result.setdefault("baseline_q975", None)
    result.setdefault("between_collection_variance", None)
    result.setdefault("heterogeneity_statistic", None)
    result["pooling_method"] = method
    result["number_of_observations"] = int(all_vals.size)
    return result
