"""Strict record eligibility for the ordinary-bowing baseline."""

from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd

from string_technique_model.collections.instruments_domain import ALLOWED_INSTRUMENTS
from string_technique_model.collections.metrics import MetricRegistry
from string_technique_model.metrics.compatibility import filter_accepted_compatibility
from string_technique_model.metrics.conversions import apply_registered_conversion

ORDINARY_TECHNIQUES = frozenset({"ordinary"})

EXCLUSION_REASONS = frozenset(
    {
        "unsupported_instrument",
        "non_ordinary_technique",
        "missing_density_value",
        "non_finite_density_value",
        "unknown_metric_definition",
        "incompatible_metric",
        "missing_sounding_pitch",
        "missing_dynamic",
        "unresolved_duplicate",
        "invalid_schema",
        "excluded_collection_role",
        "estimated_value_not_allowed",
        "missing_provenance",
        "invalid_instrument_mapping",
        "invalid_technique_mapping",
        "excluded_record",
    }
)

VALUE_STATUS_ALIASES = {
    "measured": "measured",
    "derived": "derived",
    "estimated": "estimated",
    "simulated": "simulated",
    "pooled_derived": "pooled_derived",
}


def normalize_value_status(raw: Any, *, collection_type: Any = None) -> str:
    text = str(raw or "").strip().lower()
    ctype = str(collection_type or "").strip().lower()
    if ctype == "pooled_derived" or text in {"pooled", "midpoint", "pooled_midpoint"}:
        return "pooled_derived"
    if text in VALUE_STATUS_ALIASES:
        return VALUE_STATUS_ALIASES[text]
    if text in {"", "nan", "none"}:
        return "unknown"
    return text


def _first_exclusion_reason(row: pd.Series, *, allow_missing_dynamic: bool) -> str | None:
    instrument = str(row.get("instrument") or "").strip().lower()
    if instrument not in ALLOWED_INSTRUMENTS:
        return "unsupported_instrument"

    inst_status = str(row.get("instrument_mapping_status") or "").strip().lower()
    if inst_status and inst_status not in {"valid", "ok", "mapped", ""}:
        if inst_status == "unsupported_instrument":
            return "unsupported_instrument"
        return "invalid_instrument_mapping"

    technique = str(row.get("technique") or "").strip().lower()
    if technique not in ORDINARY_TECHNIQUES:
        return "non_ordinary_technique"

    tech_status = str(row.get("technique_mapping_status") or "").strip().lower()
    if tech_status and tech_status not in {"valid", "ok", "mapped", ""}:
        return "invalid_technique_mapping"

    if bool(row.get("excluded")) is True:
        return "excluded_record"

    schema = str(row.get("schema_validity_status") or "").strip().lower()
    if schema in {"invalid", "failed", "error"}:
        return "invalid_schema"

    dup = str(row.get("duplicate_resolution_status") or "").strip().lower()
    if dup in {"unresolved", "unresolved_duplicate", "conflict"}:
        return "unresolved_duplicate"

    pitch = row.get("pitch_midi_sounding")
    if pitch is None or (isinstance(pitch, float) and np.isnan(pitch)) or pd.isna(pitch):
        # Fallback: try to accept if pitch name exists but prefer MIDI
        pname = row.get("pitch_name_sounding")
        if pname is None or (isinstance(pname, float) and np.isnan(pname)) or pd.isna(pname) or str(pname).strip() == "":
            return "missing_sounding_pitch"

    dynamic = row.get("dynamic")
    if not allow_missing_dynamic:
        if dynamic is None or (isinstance(dynamic, float) and np.isnan(dynamic)) or pd.isna(dynamic):
            return "missing_dynamic"
        if str(dynamic).strip() == "":
            return "missing_dynamic"

    dens = row.get("density_value")
    if dens is None or pd.isna(dens):
        return "missing_density_value"
    try:
        fval = float(dens)
    except (TypeError, ValueError):
        return "non_finite_density_value"
    if not np.isfinite(fval):
        return "non_finite_density_value"

    provenance = row.get("provenance")
    if provenance is None or (isinstance(provenance, float) and np.isnan(provenance)) or str(provenance).strip() == "":
        # Allow empty provenance only if source_file exists (partial provenance)
        if not str(row.get("source_file") or "").strip():
            return "missing_provenance"

    return None


def annotate_eligibility(
    frame: pd.DataFrame,
    *,
    target_metric_definition_id: str,
    metric_registry: MetricRegistry,
    accepted_metric_compatibility: list[str] | None = None,
    allow_declared_metric_conversion: bool = False,
    allow_missing_dynamic: bool = False,
    allowed_value_statuses: list[str] | None = None,
    apply_conversions: bool = True,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return (eligible, excluded) with explicit baseline eligibility fields."""
    if frame.empty:
        empty = frame.copy()
        for col in ("eligible_for_baseline", "baseline_exclusion_reason", "baseline_validation_status"):
            if col not in empty.columns:
                empty[col] = pd.Series(dtype=object if col != "eligible_for_baseline" else bool)
        return empty, empty

    work = frame.copy()
    work["measured_or_estimated"] = [
        normalize_value_status(v, collection_type=c)
        for v, c in zip(
            work.get("measured_or_estimated", pd.Series([None] * len(work))),
            work.get("collection_type", pd.Series([None] * len(work))),
            strict=False,
        )
    ]

    # Metric compatibility gate
    ok_metric, bad_metric = filter_accepted_compatibility(
        work,
        target_metric_definition_id=target_metric_definition_id,
        metric_registry=metric_registry,
        accepted_statuses=accepted_metric_compatibility,
        allow_declared_metric_conversion=allow_declared_metric_conversion,
    )
    excluded_parts = [bad_metric] if not bad_metric.empty else []

    candidate = ok_metric
    if apply_conversions and not candidate.empty:
        candidate = apply_registered_conversion(
            candidate,
            target_metric_definition_id=target_metric_definition_id,
            metric_registry=metric_registry,
        )

    allowed_statuses = {
        normalize_value_status(s) for s in (allowed_value_statuses or ["measured"])
    }

    reasons: list[str] = []
    eligible_flags: list[bool] = []
    validation: list[str] = []

    for _, row in candidate.iterrows():
        reason = _first_exclusion_reason(row, allow_missing_dynamic=allow_missing_dynamic)
        status_val = normalize_value_status(
            row.get("measured_or_estimated"),
            collection_type=row.get("collection_type"),
        )
        if reason is None and status_val not in allowed_statuses:
            reason = "estimated_value_not_allowed"
        if reason is None:
            eligible_flags.append(True)
            reasons.append("")
            validation.append("valid")
        else:
            eligible_flags.append(False)
            reasons.append(reason)
            validation.append("invalid")

    candidate = candidate.copy()
    candidate["eligible_for_baseline"] = eligible_flags
    candidate["baseline_exclusion_reason"] = reasons
    candidate["baseline_validation_status"] = validation
    candidate["measured_or_estimated"] = [
        normalize_value_status(v, collection_type=c)
        for v, c in zip(
            candidate["measured_or_estimated"],
            candidate.get("collection_type", pd.Series([None] * len(candidate))),
            strict=False,
        )
    ]

    eligible = candidate[candidate["eligible_for_baseline"]].copy()
    newly_excluded = candidate[~candidate["eligible_for_baseline"]].copy()
    if not newly_excluded.empty:
        excluded_parts.append(newly_excluded)

    excluded = (
        pd.concat(excluded_parts, ignore_index=True) if excluded_parts else candidate.iloc[0:0].copy()
    )
    if not excluded.empty:
        excluded["eligible_for_baseline"] = False
        if "baseline_validation_status" not in excluded.columns:
            excluded["baseline_validation_status"] = "invalid"
        excluded["baseline_validation_status"] = excluded["baseline_validation_status"].fillna("invalid")
        excluded.loc[
            excluded["baseline_exclusion_reason"].isna()
            | (excluded["baseline_exclusion_reason"].astype(str) == ""),
            "baseline_exclusion_reason",
        ] = "invalid_schema"

    return eligible, excluded
