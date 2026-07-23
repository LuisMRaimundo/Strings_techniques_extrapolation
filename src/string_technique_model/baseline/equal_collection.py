"""Equal-collection mean pooling."""

from __future__ import annotations

from typing import Any

import numpy as np

from string_technique_model.baseline.single_collection import aggregate_within_collection


def equal_collection_mean(
    collection_values: dict[str, np.ndarray],
    *,
    within_method: str = "arithmetic_mean",
) -> dict[str, Any]:
    """Average collection-level means with equal weight 1/K.

    Does not pool all rows directly (which would overweight large collections).
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

    k = len(means)
    weights = {cid: 1.0 / k for cid in means}
    baseline = float(sum(means.values()) / k)
    return {
        "baseline_value": baseline,
        "collection_level_values": means,
        "collection_weights": weights,
        "within_collection_sample_sizes": sizes,
        "number_of_contributing_collections": k,
        "status": "pooled",
    }
