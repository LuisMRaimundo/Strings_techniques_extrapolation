"""Apply registered metric conversions with full provenance fields."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from string_technique_model.collections.metrics import MetricRegistry


def apply_registered_conversion(
    frame: pd.DataFrame,
    *,
    target_metric_definition_id: str,
    metric_registry: MetricRegistry,
) -> pd.DataFrame:
    """Convert density values through the registered conversion system.

    Never applies z-scoring, min-max, centring, or undeclared normalisation.
    """
    if frame.empty:
        return frame.copy()

    out_parts: list[pd.DataFrame] = []
    for mid, part in frame.groupby("metric_definition_id", dropna=False):
        part = part.copy()
        source_mid = str(mid or "")
        part["original_metric_definition_id"] = source_mid
        part["target_metric_definition_id"] = target_metric_definition_id
        part["original_density_value"] = part["density_value"]
        if source_mid == target_metric_definition_id:
            part["converted_density_value"] = part["density_value"]
            part["conversion_id"] = None
            part["conversion_uncertainty"] = np.nan
            part["conversion_provenance"] = "identical_metric_definition"
            part["metric_conversion_applied"] = False
            out_parts.append(part)
            continue

        values, cmp = metric_registry.apply_conversion(
            part["density_value"], source_mid, target_metric_definition_id
        )
        part["converted_density_value"] = values
        part["density_value"] = values
        part["metric_definition_id"] = target_metric_definition_id
        part["conversion_id"] = cmp.conversion_id
        part["conversion_uncertainty"] = np.nan
        part["conversion_provenance"] = cmp.reason
        part["metric_conversion_applied"] = True
        out_parts.append(part)

    return pd.concat(out_parts, ignore_index=True) if out_parts else frame.copy()


def conversion_record_fields(row: pd.Series) -> dict[str, Any]:
    return {
        "original_metric_definition_id": row.get("original_metric_definition_id"),
        "target_metric_definition_id": row.get("target_metric_definition_id"),
        "conversion_id": row.get("conversion_id"),
        "original_density_value": row.get("original_density_value"),
        "converted_density_value": row.get("converted_density_value"),
        "conversion_uncertainty": row.get("conversion_uncertainty"),
        "conversion_provenance": row.get("conversion_provenance"),
    }
