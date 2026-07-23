"""Baseline reliability grades and evidence status."""

from __future__ import annotations

from typing import Any


def assign_reliability(
    *,
    number_of_collections: int,
    number_of_observations: int,
    measured_or_estimated: str,
    metric_conversion_applied: bool,
    metadata_completeness: float,
    provenance_completeness: float,
    collection_heterogeneity: float | None,
    pooling_status: str,
) -> dict[str, Any]:
    status = str(measured_or_estimated or "").lower()
    hetero = collection_heterogeneity
    major_hetero = False

    if pooling_status in {"empty", "missing"}:
        return {
            "baseline_reliability_grade": "NA",
            "baseline_evidence_status": "missing",
            "metadata_completeness": metadata_completeness,
            "provenance_completeness": provenance_completeness,
            "collection_heterogeneity": hetero,
            "uncertainty_status": "unavailable",
        }

    if status in {"estimated", "simulated"}:
        grade = "D"
        evidence = "weak_estimated"
    elif status in {"derived", "pooled_derived"} or metric_conversion_applied:
        grade = "C"
        evidence = "derived_or_converted"
    elif number_of_collections >= 2 and number_of_observations >= 2 and metadata_completeness >= 0.8:
        # Grade A requires consistency: moderate heterogeneity only.
        if hetero is not None and number_of_collections > 1:
            # Relative check using coefficient-like scale when possible handled by caller scale;
            # treat large absolute hetero relative to typical density (~ tens) as moderate/major.
            if hetero > 20:
                grade = "D"
                evidence = "major_heterogeneity"
                major_hetero = True
            elif hetero > 8:
                grade = "B"
                evidence = "moderate_heterogeneity"
            else:
                grade = "A"
                evidence = "multi_collection_measured"
        else:
            grade = "A"
            evidence = "multi_collection_measured"
    elif number_of_collections == 1 and number_of_observations >= 3 and metadata_completeness >= 0.8:
        grade = "A"
        evidence = "well_replicated_single_collection"
    elif status == "measured":
        grade = "B"
        evidence = "limited_replication"
    else:
        grade = "D"
        evidence = "weak_metadata_or_source"

    if metadata_completeness < 0.5 or provenance_completeness < 0.5:
        if grade in {"A", "B"}:
            grade = "D"
            evidence = "weak_metadata"

    return {
        "baseline_reliability_grade": grade,
        "baseline_evidence_status": evidence,
        "metadata_completeness": metadata_completeness,
        "provenance_completeness": provenance_completeness,
        "collection_heterogeneity": hetero,
        "uncertainty_status": "unavailable" if major_hetero else "reported_or_null",
    }


def completeness_score(row_like: dict[str, Any], fields: list[str]) -> float:
    if not fields:
        return 0.0
    present = 0
    for field in fields:
        val = row_like.get(field)
        if val is None:
            continue
        text = str(val).strip()
        if text and text.lower() not in {"nan", "none", ""}:
            present += 1
    return present / len(fields)
