from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from string_technique_model.collections.canonical import POOLING_KEY_DEFAULT
from string_technique_model.collections.metrics import MetricRegistry

POOLING_METHODS = {
    "no_pooling",
    "equal_mean",
    "user_weighted_mean",
    "inverse_variance_weighting",
    "sample_size_weighting",
    "robust_median",
    "hierarchical_collection",
    "random_effects_meta_analytic_pooling",
}


@dataclass
class PooledCell:
    pooling_key: dict[str, Any]
    pooled_density: float | None
    pooling_method: str
    baseline_collection_ids: list[str]
    n_contributing_collections: int
    n_observations_per_collection: dict[str, int]
    collection_weights: dict[str, float]
    excluded_collections: dict[str, str]
    collection_heterogeneity: float | None
    collection_effect_estimates: dict[str, float]
    metric_compatibility_status: str
    status: str
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class PoolingResult:
    cells: list[PooledCell] = field(default_factory=list)

    def to_frame(self) -> pd.DataFrame:
        if not self.cells:
            return pd.DataFrame()
        rows = []
        for cell in self.cells:
            row = cell.to_dict()
            row.update(cell.pooling_key)
            rows.append(row)
        return pd.DataFrame(rows)


def pool_collections(
    frame: pd.DataFrame,
    *,
    method: str,
    target_metric_definition_id: str,
    metric_registry: MetricRegistry,
    user_weights: dict[str, float] | None = None,
    pooling_key: list[str] | None = None,
) -> PoolingResult:
    if method not in POOLING_METHODS:
        raise ValueError(f"Unknown pooling method: {method}")
    if frame.empty:
        return PoolingResult([])

    key_cols = pooling_key or POOLING_KEY_DEFAULT
    work = frame.copy()

    # Convert compatible metrics explicitly; exclude incompatible.
    converted_parts = []
    excluded_global: dict[str, str] = {}
    for collection_id, part in work.groupby("collection_id", dropna=False):
        mid = str(part["metric_definition_id"].dropna().iloc[0]) if part["metric_definition_id"].notna().any() else ""
        cmp = metric_registry.compare(mid, target_metric_definition_id)
        if cmp.status == "identical":
            converted_parts.append(part)
            continue
        if cmp.status in {
            "compatible_after_unit_conversion",
            "compatible_after_declared_transformation",
        }:
            try:
                values, _ = metric_registry.apply_conversion(
                    part["density_value"], mid, target_metric_definition_id
                )
                part = part.copy()
                part["density_value"] = values
                part["metric_definition_id"] = target_metric_definition_id
                part["metric_compatibility_status"] = cmp.status
                converted_parts.append(part)
            except Exception as exc:  # noqa: BLE001
                excluded_global[str(collection_id)] = f"conversion_failed: {exc}"
        else:
            excluded_global[str(collection_id)] = (
                f"metric_compatibility_status={cmp.status}: {cmp.reason}"
            )

    if not converted_parts:
        return PoolingResult(
            [
                PooledCell(
                    pooling_key={},
                    pooled_density=None,
                    pooling_method=method,
                    baseline_collection_ids=[],
                    n_contributing_collections=0,
                    n_observations_per_collection={},
                    collection_weights={},
                    excluded_collections=excluded_global,
                    collection_heterogeneity=None,
                    collection_effect_estimates={},
                    metric_compatibility_status="incompatible",
                    status="no_compatible_observations",
                    reason="All collections excluded due to metric incompatibility or conversion failure.",
                )
            ]
        )

    work = pd.concat(converted_parts, ignore_index=True)
    if "usable_for_pooling" in work.columns:
        work = work[work["usable_for_pooling"] == True]  # noqa: E712

    cells: list[PooledCell] = []
    grouped = work.groupby([c for c in key_cols if c in work.columns], dropna=False, observed=True)
    for key_vals, group in grouped:
        if not isinstance(key_vals, tuple):
            key_vals = (key_vals,)
        key = {col: key_vals[i] for i, col in enumerate([c for c in key_cols if c in work.columns])}
        cell = _pool_group(
            group,
            method=method,
            key=key,
            user_weights=user_weights or {},
            excluded_global=excluded_global,
        )
        cells.append(cell)
    return PoolingResult(cells)


def _pool_group(
    group: pd.DataFrame,
    *,
    method: str,
    key: dict[str, Any],
    user_weights: dict[str, float],
    excluded_global: dict[str, str],
) -> PooledCell:
    excluded = dict(excluded_global)
    by_coll = {
        str(cid): g["density_value"].astype(float).dropna()
        for cid, g in group.groupby("collection_id")
    }
    by_coll = {cid: s for cid, s in by_coll.items() if len(s)}
    if not by_coll:
        return PooledCell(
            pooling_key=key,
            pooled_density=None,
            pooling_method=method,
            baseline_collection_ids=[],
            n_contributing_collections=0,
            n_observations_per_collection={},
            collection_weights={},
            excluded_collections=excluded,
            collection_heterogeneity=None,
            collection_effect_estimates={},
            metric_compatibility_status="unknown",
            status="empty_group",
        )

    if method == "no_pooling":
        # Keep first collection only in deterministic sorted order.
        cid = sorted(by_coll)[0]
        for other in by_coll:
            if other != cid:
                excluded[other] = "no_pooling_selected_first_collection_only"
        values = by_coll[cid]
        weights = {cid: 1.0}
        pooled = float(values.mean())
        effects = {cid: 0.0}
        hetero = None
    else:
        means = {cid: float(s.mean()) for cid, s in by_coll.items()}
        counts = {cid: int(len(s)) for cid, s in by_coll.items()}
        variances = {
            cid: float(s.var(ddof=1)) if len(s) > 1 else np.nan for cid, s in by_coll.items()
        }

        if method == "equal_mean":
            weights = {cid: 1.0 / len(means) for cid in means}
        elif method == "user_weighted_mean":
            raw = {cid: float(user_weights.get(cid, 0.0)) for cid in means}
            total = sum(raw.values())
            if total <= 0:
                weights = {cid: 1.0 / len(means) for cid in means}
            else:
                weights = {cid: w / total for cid, w in raw.items()}
        elif method == "sample_size_weighting":
            total = sum(counts.values())
            weights = {cid: counts[cid] / total for cid in counts}
        elif method == "inverse_variance_weighting":
            inv: dict[str, float] = {}
            for cid, var in variances.items():
                if np.isnan(var) or var <= 0:
                    inv[cid] = float(counts[cid])
                else:
                    inv[cid] = 1.0 / var
            total = sum(inv.values())
            weights = {cid: inv[cid] / total for cid in inv}
        elif method == "robust_median":
            weights = {cid: 1.0 / len(means) for cid in means}
            pooled = float(np.median(list(means.values())))
            effects = {cid: means[cid] - pooled for cid in means}
            hetero = float(np.std(list(means.values()), ddof=1)) if len(means) > 1 else 0.0
            return PooledCell(
                pooling_key=key,
                pooled_density=pooled,
                pooling_method=method,
                baseline_collection_ids=sorted(means),
                n_contributing_collections=len(means),
                n_observations_per_collection=counts,
                collection_weights=weights,
                excluded_collections=excluded,
                collection_heterogeneity=hetero,
                collection_effect_estimates=effects,
                metric_compatibility_status="identical",
                status="pooled",
            )
        elif method in {"hierarchical_collection", "random_effects_meta_analytic_pooling"}:
            # DerSimonian-Laird style random-effects over collection means.
            y = np.array(list(means.values()), dtype=float)
            coll_ids = list(means.keys())
            n = np.array([counts[c] for c in coll_ids], dtype=float)
            within = []
            for cid in coll_ids:
                var = variances[cid]
                if np.isnan(var) or var <= 0:
                    within.append(1.0 / max(n[coll_ids.index(cid)], 1.0))
                else:
                    within.append(var / max(n[coll_ids.index(cid)], 1.0))
            within_var = np.asarray(within, dtype=float)
            fixed_w = 1.0 / np.maximum(within_var, 1e-12)
            fixed_mean = float(np.sum(fixed_w * y) / np.sum(fixed_w))
            q = float(np.sum(fixed_w * (y - fixed_mean) ** 2))
            c = float(np.sum(fixed_w) - (np.sum(fixed_w**2) / np.sum(fixed_w)))
            tau2 = max(0.0, (q - (len(y) - 1)) / c) if c > 0 else 0.0
            re_w = 1.0 / (within_var + tau2)
            weights = {cid: float(re_w[i] / np.sum(re_w)) for i, cid in enumerate(coll_ids)}
            pooled = float(np.sum([weights[cid] * means[cid] for cid in coll_ids]))
            effects = {cid: means[cid] - pooled for cid in coll_ids}
            hetero = float(np.sqrt(tau2))
            return PooledCell(
                pooling_key=key,
                pooled_density=pooled,
                pooling_method=method,
                baseline_collection_ids=sorted(means),
                n_contributing_collections=len(means),
                n_observations_per_collection=counts,
                collection_weights=weights,
                excluded_collections=excluded,
                collection_heterogeneity=hetero,
                collection_effect_estimates=effects,
                metric_compatibility_status="identical",
                status="pooled",
            )
        else:
            weights = {cid: 1.0 / len(means) for cid in means}

        pooled = float(sum(weights[cid] * means[cid] for cid in means))
        effects = {cid: means[cid] - pooled for cid in means}
        hetero = float(np.std(list(means.values()), ddof=1)) if len(means) > 1 else 0.0
        counts = {cid: int(len(by_coll[cid])) for cid in means}

    return PooledCell(
        pooling_key=key,
        pooled_density=pooled,
        pooling_method=method,
        baseline_collection_ids=sorted(by_coll),
        n_contributing_collections=len(by_coll),
        n_observations_per_collection={cid: int(len(s)) for cid, s in by_coll.items()},
        collection_weights=weights,
        excluded_collections=excluded,
        collection_heterogeneity=hetero,
        collection_effect_estimates=effects,
        metric_compatibility_status="identical",
        status="pooled",
    )
