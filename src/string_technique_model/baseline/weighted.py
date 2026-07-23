"""User-weighted and sample-size / inverse-variance weighting."""

from __future__ import annotations

from typing import Any

import numpy as np

from string_technique_model.baseline.single_collection import aggregate_within_collection


class WeightValidationError(ValueError):
    """Raised when user-declared collection weights are invalid."""


def validate_user_weights(
    collection_ids: list[str],
    weights: dict[str, float],
    *,
    atol: float = 1e-8,
) -> dict[str, float]:
    missing = [cid for cid in collection_ids if cid not in weights]
    if missing:
        raise WeightValidationError(
            f"Missing collection_weights for: {missing}. "
            "Do not silently normalise undeclared weights."
        )
    extras = [cid for cid in weights if cid not in collection_ids]
    # Extra keys for non-contributing collections are allowed only if non-negative;
    # contributing set must be complete.
    cleaned: dict[str, float] = {}
    for cid in collection_ids:
        w = float(weights[cid])
        if w < 0:
            raise WeightValidationError(f"Negative weight for {cid}: {w}")
        cleaned[cid] = w
    total = sum(cleaned.values())
    if abs(total - 1.0) > atol:
        raise WeightValidationError(
            f"collection_weights must sum to 1.0 (±{atol}); got {total}. "
            "Do not silently renormalise."
        )
    if extras:
        for cid in extras:
            if float(weights[cid]) < 0:
                raise WeightValidationError(f"Negative weight for {cid}: {weights[cid]}")
    return cleaned


def user_weighted_mean(
    collection_values: dict[str, np.ndarray],
    user_weights: dict[str, float],
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
    weights = validate_user_weights(sorted(means), user_weights)
    baseline = float(sum(weights[cid] * means[cid] for cid in means))
    return {
        "baseline_value": baseline,
        "collection_level_values": means,
        "collection_weights": weights,
        "within_collection_sample_sizes": sizes,
        "number_of_contributing_collections": len(means),
        "status": "pooled",
    }


def sample_size_weighting(
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
    total_n = sum(sizes.values())
    weights = {cid: sizes[cid] / total_n for cid in means}
    baseline = float(sum(weights[cid] * means[cid] for cid in means))
    return {
        "baseline_value": baseline,
        "collection_level_values": means,
        "collection_weights": weights,
        "within_collection_sample_sizes": sizes,
        "number_of_contributing_collections": len(means),
        "status": "pooled",
    }


def inverse_variance_weighting(
    collection_values: dict[str, np.ndarray],
    collection_variances: dict[str, float] | None = None,
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

    variances: dict[str, float] = {}
    for cid, values in collection_values.items():
        if cid not in means:
            continue
        if collection_variances and cid in collection_variances and np.isfinite(collection_variances[cid]):
            variances[cid] = float(collection_variances[cid])
        elif len(values) > 1:
            variances[cid] = float(np.var(values, ddof=1))
        else:
            return {
                "baseline_value": None,
                "collection_level_values": means,
                "collection_weights": {},
                "within_collection_sample_sizes": sizes,
                "number_of_contributing_collections": len(means),
                "status": "insufficient_variance_information",
                "pooling_status": "insufficient_variance_information",
            }

    inv = {cid: 1.0 / v for cid, v in variances.items() if v > 0}
    if len(inv) != len(means):
        return {
            "baseline_value": None,
            "collection_level_values": means,
            "collection_weights": {},
            "within_collection_sample_sizes": sizes,
            "number_of_contributing_collections": len(means),
            "status": "insufficient_variance_information",
            "pooling_status": "insufficient_variance_information",
        }
    total = sum(inv.values())
    weights = {cid: inv[cid] / total for cid in inv}
    baseline = float(sum(weights[cid] * means[cid] for cid in means))
    return {
        "baseline_value": baseline,
        "collection_level_values": means,
        "collection_weights": weights,
        "within_collection_sample_sizes": sizes,
        "number_of_contributing_collections": len(means),
        "status": "pooled",
    }
