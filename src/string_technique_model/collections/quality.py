from __future__ import annotations

from typing import Any

import pandas as pd

from string_technique_model.collections.canonical import REQUIRED_FOR_MINIMAL_USER_TABLE
from string_technique_model.collections.instruments_domain import (
    EXCLUSION_REASON_UNSUPPORTED,
    UNSUPPORTED_STATUS,
    is_allowed_instrument,
)
from string_technique_model.collections.metrics import MetricRegistry

CORE_METADATA = [
    "instrument",
    "technique",
    "pitch_name_sounding",
    "dynamic",
    "density_value",
    "metric_definition_id",
    "measured_or_estimated",
]

PROVENANCE_FIELDS = [
    "source_file",
    "collection_id",
    "metric_definition_id",
    "analysis_window_id",
    "normalisation_id",
    "frequency_range_id",
    "provenance",
]


def annotate_quality(
    frame: pd.DataFrame,
    *,
    metric_registry: MetricRegistry,
    target_metric_definition_id: str,
    default_role: str | None,
) -> pd.DataFrame:
    out = frame.copy()
    statuses: list[str] = []
    compat: list[str] = []
    meta_scores: list[float] = []
    prov_scores: list[float] = []
    grades: list[str] = []
    usable_baseline: list[bool] = []
    usable_pool: list[bool] = []
    usable_cal: list[bool] = []
    usable_val: list[bool] = []
    usable_pred: list[bool] = []
    comparability: list[str] = []
    exclusions: list[Any] = []

    for _, row in out.iterrows():
        unsupported = (
            row.get("instrument_mapping_status") == UNSUPPORTED_STATUS
            or (
                pd.notna(row.get("instrument"))
                and not is_allowed_instrument(row.get("instrument"))
            )
            or (
                pd.isna(row.get("instrument"))
                and row.get("instrument_mapping_status") == UNSUPPORTED_STATUS
            )
        )

        if unsupported:
            schema_status = "invalid"
            cmp = "unknown"
            reason_grade = "NA"
            statuses.append(schema_status)
            compat.append(cmp)
            comparability.append(reason_grade)
            meta_scores.append(_completeness(row, CORE_METADATA))
            prov_scores.append(_completeness(row, PROVENANCE_FIELDS))
            grades.append(reason_grade)
            usable_baseline.append(False)
            usable_pool.append(False)
            usable_cal.append(False)
            usable_val.append(False)
            usable_pred.append(False)
            exclusions.append(EXCLUSION_REASON_UNSUPPORTED)
            continue

        schema_status = _schema_validity(row)
        statuses.append(schema_status)

        mid = row.get("metric_definition_id")
        if pd.isna(mid) or not mid:
            cmp = "unknown"
            reason_grade = "NA"
        else:
            result = metric_registry.compare(str(mid), target_metric_definition_id)
            cmp = result.status
            reason_grade = _grade_from_status(result.status, schema_status)
        compat.append(cmp)
        comparability.append(reason_grade)

        meta_scores.append(_completeness(row, CORE_METADATA))
        prov_scores.append(_completeness(row, PROVENANCE_FIELDS))
        grades.append(reason_grade)

        can_base = schema_status == "valid" and cmp in {
            "identical",
            "compatible_after_unit_conversion",
            "compatible_after_declared_transformation",
        }
        usable_baseline.append(bool(can_base))
        usable_pool.append(bool(can_base))
        usable_cal.append(bool(can_base))
        usable_val.append(
            bool(
                schema_status in {"valid", "valid_with_missing_metadata"}
                and cmp
                in {
                    "identical",
                    "compatible_after_unit_conversion",
                    "compatible_after_declared_transformation",
                    "conditionally_comparable",
                }
            )
        )
        usable_pred.append(bool(can_base))
        existing = row.get("exclusion_reason")
        exclusions.append(existing if pd.notna(existing) else pd.NA)
        _ = default_role

    out["schema_validity_status"] = statuses
    out["metric_compatibility_status"] = compat
    out["metadata_completeness_score"] = meta_scores
    out["provenance_completeness_score"] = prov_scores
    out["collection_quality_grade"] = grades
    out["comparability_grade"] = comparability
    out["usable_as_baseline"] = usable_baseline
    out["usable_for_pooling"] = usable_pool
    out["usable_for_calibration"] = usable_cal
    out["usable_for_validation"] = usable_val
    out["usable_for_prediction"] = usable_pred
    out["exclusion_reason"] = exclusions
    return out


def _schema_validity(row: pd.Series) -> str:
    if row.get("instrument_mapping_status") == UNSUPPORTED_STATUS:
        return "invalid"
    missing = [
        c
        for c in REQUIRED_FOR_MINIMAL_USER_TABLE
        if c != "collection_id" and (pd.isna(row.get(c)) or row.get(c) == "")
    ]
    if "instrument" in missing or "density_value" in missing:
        # density missing may be missing_by_design; instrument missing is invalid for science
        if "instrument" in missing:
            return "invalid"
    if "density_value" in missing:
        return "valid_with_missing_metadata"
    if missing:
        return "valid_with_missing_metadata"
    return "valid"


def _completeness(row: pd.Series, fields: list[str]) -> float:
    present = sum(1 for f in fields if pd.notna(row.get(f)) and row.get(f) != "")
    return round(present / max(len(fields), 1), 4)


def _grade_from_status(status: str, schema_status: str) -> str:
    if schema_status == "invalid":
        return "NA"
    if status == "identical":
        return "A" if schema_status == "valid" else "B"
    if status == "compatible_after_unit_conversion":
        return "B"
    if status == "compatible_after_declared_transformation":
        return "C"
    if status == "conditionally_comparable":
        return "D"
    if status in {"incompatible", "unknown"}:
        return "NA"
    return "D"


def summarize_quality(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {"n_records": 0}
    summary = {
        "n_records": int(len(frame)),
        "schema_validity_counts": frame["schema_validity_status"].value_counts(dropna=False).to_dict(),
        "metric_compatibility_counts": frame["metric_compatibility_status"].value_counts(
            dropna=False
        ).to_dict(),
        "quality_grade_counts": frame["collection_quality_grade"].value_counts(dropna=False).to_dict(),
        "usable_as_baseline": int(frame["usable_as_baseline"].sum()),
        "usable_for_pooling": int(frame["usable_for_pooling"].sum()),
        "usable_for_validation": int(frame["usable_for_validation"].sum()),
        "mean_metadata_completeness": float(frame["metadata_completeness_score"].mean()),
        "mean_provenance_completeness": float(frame["provenance_completeness_score"].mean()),
    }
    if "usable_for_calibration" in frame.columns:
        summary["usable_for_calibration"] = int(frame["usable_for_calibration"].sum())
    if "usable_for_prediction" in frame.columns:
        summary["usable_for_prediction"] = int(frame["usable_for_prediction"].sum())
    if "instrument_mapping_status" in frame.columns:
        summary["instrument_mapping_counts"] = (
            frame["instrument_mapping_status"].value_counts(dropna=False).to_dict()
        )
    return summary
