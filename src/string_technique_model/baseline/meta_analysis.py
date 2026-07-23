"""Fixed- and random-effects meta-analytic pooling over collections."""

from __future__ import annotations

from typing import Any

import numpy as np

from string_technique_model.baseline.single_collection import aggregate_within_collection


def _collection_means_and_ses(
    collection_values: dict[str, np.ndarray],
    *,
    within_method: str,
) -> tuple[dict[str, float], dict[str, float], dict[str, int], str | None]:
    means: dict[str, float] = {}
    ses: dict[str, float] = {}
    sizes: dict[str, int] = {}
    for cid, values in collection_values.items():
        arr = np.asarray(values, dtype=float)
        arr = arr[np.isfinite(arr)]
        summary = aggregate_within_collection(arr, method=within_method)
        if summary["value"] is None:
            continue
        means[cid] = float(summary["value"])
        sizes[cid] = int(summary["n"])
        if arr.size < 2:
            return means, ses, sizes, "insufficient_variance_information"
        se = float(np.std(arr, ddof=1) / np.sqrt(arr.size))
        if not np.isfinite(se) or se <= 0:
            return means, ses, sizes, "insufficient_variance_information"
        ses[cid] = se
    if not means:
        return {}, {}, {}, "empty"
    if len(ses) != len(means):
        return means, ses, sizes, "insufficient_variance_information"
    return means, ses, sizes, None


def fixed_effect_meta_analysis(
    collection_values: dict[str, np.ndarray],
    *,
    within_method: str = "arithmetic_mean",
) -> dict[str, Any]:
    means, ses, sizes, err = _collection_means_and_ses(collection_values, within_method=within_method)
    if err == "empty":
        return {
            "baseline_value": None,
            "collection_level_values": {},
            "collection_weights": {},
            "within_collection_sample_sizes": {},
            "number_of_contributing_collections": 0,
            "status": "empty",
        }
    if err:
        return {
            "baseline_value": None,
            "collection_level_values": means,
            "collection_weights": {},
            "within_collection_sample_sizes": sizes,
            "number_of_contributing_collections": len(means),
            "status": err,
            "pooling_status": err,
        }
    inv_var = {cid: 1.0 / (ses[cid] ** 2) for cid in means}
    total = sum(inv_var.values())
    weights = {cid: inv_var[cid] / total for cid in means}
    pooled = float(sum(weights[cid] * means[cid] for cid in means))
    se = float(np.sqrt(1.0 / total))
    return {
        "baseline_value": pooled,
        "baseline_se": se,
        "baseline_q025": pooled - 1.96 * se,
        "baseline_q975": pooled + 1.96 * se,
        "collection_level_values": means,
        "collection_weights": weights,
        "within_collection_sample_sizes": sizes,
        "number_of_contributing_collections": len(means),
        "between_collection_variance": 0.0,
        "heterogeneity_statistic": None,
        "status": "pooled",
    }


def random_effects_meta_analysis(
    collection_values: dict[str, np.ndarray],
    *,
    within_method: str = "arithmetic_mean",
) -> dict[str, Any]:
    """DerSimonian–Laird random-effects over collection means."""
    means, ses, sizes, err = _collection_means_and_ses(collection_values, within_method=within_method)
    if err == "empty":
        return {
            "baseline_value": None,
            "collection_level_values": {},
            "collection_weights": {},
            "within_collection_sample_sizes": {},
            "number_of_contributing_collections": 0,
            "status": "empty",
        }
    if err:
        return {
            "baseline_value": None,
            "collection_level_values": means,
            "collection_weights": {},
            "within_collection_sample_sizes": sizes,
            "number_of_contributing_collections": len(means),
            "status": err,
            "pooling_status": err,
        }
    if len(means) == 1:
        cid = next(iter(means))
        return {
            "baseline_value": means[cid],
            "baseline_se": ses[cid],
            "baseline_q025": means[cid] - 1.96 * ses[cid],
            "baseline_q975": means[cid] + 1.96 * ses[cid],
            "collection_level_values": means,
            "collection_weights": {cid: 1.0},
            "within_collection_sample_sizes": sizes,
            "number_of_contributing_collections": 1,
            "between_collection_variance": None,
            "heterogeneity_statistic": None,
            "status": "single_collection",
            "uncertainty_status": "within_collection_only",
        }

    coll_ids = sorted(means)
    y = np.array([means[c] for c in coll_ids], dtype=float)
    within_var = np.array([ses[c] ** 2 for c in coll_ids], dtype=float)
    fixed_w = 1.0 / np.maximum(within_var, 1e-12)
    fixed_mean = float(np.sum(fixed_w * y) / np.sum(fixed_w))
    q = float(np.sum(fixed_w * (y - fixed_mean) ** 2))
    c = float(np.sum(fixed_w) - (np.sum(fixed_w**2) / np.sum(fixed_w)))
    tau2 = max(0.0, (q - (len(y) - 1)) / c) if c > 0 else 0.0
    re_w = 1.0 / (within_var + tau2)
    weights = {cid: float(re_w[i] / np.sum(re_w)) for i, cid in enumerate(coll_ids)}
    pooled = float(sum(weights[cid] * means[cid] for cid in coll_ids))
    se = float(np.sqrt(1.0 / np.sum(re_w)))
    return {
        "baseline_value": pooled,
        "baseline_se": se,
        "baseline_q025": pooled - 1.96 * se,
        "baseline_q975": pooled + 1.96 * se,
        "collection_level_values": means,
        "collection_weights": weights,
        "within_collection_sample_sizes": sizes,
        "number_of_contributing_collections": len(means),
        "between_collection_variance": float(tau2),
        "heterogeneity_statistic": float(q),
        "status": "pooled",
    }
