"""Prediction reliability classification (cannot exceed evidence grade)."""

from __future__ import annotations

from typing import Any

GRADE_RANK = {"A": 4, "B": 3, "C": 2, "D": 1, "NA": 0}


def evidence_grade_for_cell(
    matrix_rows: list[dict[str, Any]],
    instrument: str,
    technique: str,
) -> str:
    for row in matrix_rows:
        if row.get("instrument") == instrument and row.get("technique") == technique:
            return str(row.get("evidence_grade") or "NA")
    return "NA"


def assign_reliability(
    *,
    evidence_grade: str,
    prediction_status: str,
    transfer_used: bool,
    n_active: int,
) -> str:
    if prediction_status in {
        "insufficient_active_parameters",
        "qualitative_constraints_only",
        "not_estimable_from_current_evidence",
        "insufficient_context_metadata",
        "unsupported_instrument_technique_cell",
        "missing_ordinary_baseline",
        "incompatible_metric",
        "outside_parameter_validity_range",
    }:
        return "NA"
    if n_active <= 0:
        return "NA"

    grade = evidence_grade if evidence_grade in GRADE_RANK else "NA"
    # Prediction reliability may not exceed underlying evidence grade.
    if transfer_used and GRADE_RANK[grade] > GRADE_RANK["C"]:
        grade = "C"
    if prediction_status == "predicted_with_transfer":
        if GRADE_RANK[grade] > GRADE_RANK["C"]:
            grade = "C"
    if prediction_status == "predicted_direct_evidence":
        return grade if grade != "NA" else "D"
    if prediction_status == "predicted_with_explicit_mapping":
        if GRADE_RANK[grade] > GRADE_RANK["B"]:
            return "B"
        return grade
    return grade
