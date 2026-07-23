"""Parameter evidence ledger construction."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from string_technique_model.config import PACKAGE_ROOT, load_yaml, resolve_path
from string_technique_model.literature.domain import ACTIVE_PARAMETER_STATUSES, PARAMETER_STATUSES

REQUIRED_ACTIVE_FIELDS = [
    "parameter_id",
    "parameter_name",
    "operation_type",
    "numerical_scale",
    "unit",
    "evidence_ids",
    "density_mapping_status",
    "parameter_status",
]


def load_parameter_config(path: Path | str | None = None) -> dict[str, Any]:
    path = resolve_path(path or PACKAGE_ROOT / "configs" / "literature_parameters.yaml")
    return load_yaml(path)


def active_parameters(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    return list(cfg.get("parameters") or [])


def inactive_candidates(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    return list(cfg.get("inactive_parameter_candidates") or [])


def build_parameter_ledger_rows(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for param in active_parameters(cfg):
        row = dict(param)
        row["ledger_role"] = "active_candidate"
        rows.append(_normalise_row(row))
    for param in inactive_candidates(cfg):
        instruments = param.get("instruments") or (
            [param["instrument"]] if param.get("instrument") else [None]
        )
        techniques = param.get("techniques") or (
            [param["technique"]] if param.get("technique") else [None]
        )
        for inst in instruments:
            for tech in techniques:
                row = dict(param)
                row["instrument"] = inst
                row["technique"] = tech
                row["ledger_role"] = "inactive"
                rows.append(_normalise_row(row))
    return rows


def _normalise_row(param: dict[str, Any]) -> dict[str, Any]:
    import json

    from string_technique_model.provenance import normalize_evidence_ids, normalize_source_ids

    evidence_ids = normalize_evidence_ids(param)
    source_ids = normalize_source_ids(param)
    # Flat CSV: JSON arrays (canonical plural lists)
    evidence_ids_s = json.dumps(evidence_ids, ensure_ascii=False)
    source_ids_s = json.dumps(source_ids, ensure_ascii=False)
    return {
        "parameter_id": param.get("parameter_id"),
        "parameter_name": param.get("parameter_name"),
        "instrument": param.get("instrument"),
        "technique": param.get("technique"),
        "model_component": param.get("model_component"),
        "parameter_role": param.get("parameter_role"),
        "operation_type": param.get("operation_type"),
        "numerical_scale": param.get("numerical_scale"),
        "reported_value": param.get("reported_value"),
        "proposed_distribution": param.get("proposed_distribution"),
        "distribution_parameters": param.get("distribution_parameters"),
        "unit": param.get("unit"),
        "applicable_pitch_min": param.get("applicable_pitch_min"),
        "applicable_pitch_max": param.get("applicable_pitch_max"),
        "applicable_frequency_min_hz": param.get("applicable_frequency_min_hz"),
        "applicable_frequency_max_hz": param.get("applicable_frequency_max_hz"),
        "applicable_register": param.get("applicable_register"),
        "applicable_dynamic": param.get("applicable_dynamic"),
        "applicable_string": param.get("applicable_string"),
        "applicable_temporal_region": param.get("applicable_temporal_region"),
        "source_ids": source_ids_s,
        "evidence_ids": evidence_ids_s,
        "page_reference": param.get("page_reference"),
        "direct_or_transferred": param.get("direct_or_transferred"),
        "transfer_source_instrument": param.get("transfer_source_instrument"),
        "transfer_equation": param.get("transfer_equation"),
        "transfer_uncertainty": param.get("transfer_uncertainty"),
        "evidence_grade": param.get("evidence_grade"),
        "parameter_status": param.get("parameter_status"),
        "confidence_level": param.get("confidence_level"),
        "density_mapping_status": param.get("density_mapping_status"),
        "notes": param.get("notes"),
        "ledger_role": param.get("ledger_role"),
        # Bibliographically constrained ≠ density-active.
        "active_for_density_prediction": bool(param.get("active_for_density_prediction")),
        "is_active": bool(param.get("active_for_density_prediction"))
        and param.get("parameter_status") in ACTIVE_PARAMETER_STATUSES
        and param.get("density_mapping_status")
        in {"direct_same_metric", "directly_computable_from_reported_spectrum"},
    }


def assert_no_active_without_evidence(rows: list[dict[str, Any]]) -> list[str]:
    errors: list[str] = []
    for row in rows:
        status = row.get("parameter_status")
        if status not in PARAMETER_STATUSES and status is not None:
            errors.append(f"Invalid parameter_status: {status}")
        if not row.get("is_active"):
            continue
        if not row.get("evidence_ids"):
            errors.append(f"Active parameter {row.get('parameter_id')} lacks evidence_ids")
        for field in ("operation_type", "numerical_scale", "density_mapping_status"):
            if not row.get(field):
                errors.append(f"Active parameter {row.get('parameter_id')} missing {field}")
        if row.get("evidence_grade") == "NA":
            errors.append(f"Active parameter {row.get('parameter_id')} has evidence_grade NA")
    return errors
