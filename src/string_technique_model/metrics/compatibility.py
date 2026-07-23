"""Metric compatibility assessment before baseline alignment."""

from __future__ import annotations

from typing import Any

import pandas as pd

from string_technique_model.collections.metrics import CompatibilityResult, MetricRegistry

DEFAULT_ACCEPTED = ("identical",)


def assess_metric_compatibility(
    source_metric_definition_id: str,
    target_metric_definition_id: str,
    metric_registry: MetricRegistry,
) -> CompatibilityResult:
    return metric_registry.compare(source_metric_definition_id, target_metric_definition_id)


def filter_accepted_compatibility(
    frame: pd.DataFrame,
    *,
    target_metric_definition_id: str,
    metric_registry: MetricRegistry,
    accepted_statuses: list[str] | tuple[str, ...] | None = None,
    allow_declared_metric_conversion: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Split rows into metric-compatible vs incompatible for the target definition.

    Returns (accepted_frame, rejected_frame). Rejected rows gain
    ``baseline_exclusion_reason`` and ``baseline_validation_status``.
    """
    accepted = list(accepted_statuses or DEFAULT_ACCEPTED)
    if allow_declared_metric_conversion:
        for status in (
            "compatible_after_unit_conversion",
            "compatible_after_declared_transformation",
        ):
            if status not in accepted:
                accepted.append(status)

    if frame.empty:
        empty = frame.copy()
        return empty, empty

    work = frame.copy()
    reasons: list[str] = []
    statuses: list[str] = []
    conversion_ids: list[str | None] = []
    keep_mask: list[bool] = []

    for _, row in work.iterrows():
        mid = str(row.get("metric_definition_id") or "").strip()
        if not mid:
            reasons.append("unknown_metric_definition")
            statuses.append("invalid")
            conversion_ids.append(None)
            keep_mask.append(False)
            continue
        if mid not in metric_registry.definitions:
            reasons.append("unknown_metric_definition")
            statuses.append("invalid")
            conversion_ids.append(None)
            keep_mask.append(False)
            continue
        cmp = assess_metric_compatibility(mid, target_metric_definition_id, metric_registry)
        if cmp.status not in accepted:
            if cmp.status in {"conditionally_comparable", "incompatible", "unknown"}:
                reasons.append("incompatible_metric")
            else:
                reasons.append("incompatible_metric")
            statuses.append("invalid")
            conversion_ids.append(cmp.conversion_id)
            keep_mask.append(False)
            continue
        reasons.append("")
        statuses.append("valid")
        conversion_ids.append(cmp.conversion_id)
        keep_mask.append(True)

    work["metric_compatibility_status"] = [
        assess_metric_compatibility(
            str(r.get("metric_definition_id") or ""),
            target_metric_definition_id,
            metric_registry,
        ).status
        for _, r in work.iterrows()
    ]
    work["_keep_metric"] = keep_mask
    work["baseline_exclusion_reason"] = reasons
    work["baseline_validation_status"] = statuses
    work["pending_conversion_id"] = conversion_ids

    ok = work[work["_keep_metric"]].drop(columns=["_keep_metric"]).copy()
    bad = work[~work["_keep_metric"]].drop(columns=["_keep_metric"]).copy()
    return ok, bad


def compatibility_summary(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty or "metric_compatibility_status" not in frame.columns:
        return {"counts": {}}
    return {
        "counts": frame["metric_compatibility_status"].astype(str).value_counts().to_dict(),
    }
