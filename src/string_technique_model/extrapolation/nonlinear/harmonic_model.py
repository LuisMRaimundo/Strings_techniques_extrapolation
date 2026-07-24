"""Harmonic technique predictor (calibrated descriptor lookup + Phase-2 stub)."""

from __future__ import annotations

from typing import Any

from string_technique_model.extrapolation.nonlinear.domain import EvidenceTier, ValueKind
from string_technique_model.extrapolation.nonlinear.harmonic_calibration_table import (
    has_calibrated_harmonic_coverage,
    lookup_calibrated_harmonic,
)


def validate_touch_interval(touch: str, sounding: str) -> bool:
    """Validate allowed touch→sounding interval mappings (pure functions)."""
    key = (str(touch).strip().upper(), str(sounding).strip().upper())
    allowed = {
        ("P4", "4"),
        ("M3", "5"),
        ("M3", "5TH"),
        ("m3", "6"),
        ("M3", "6"),
        ("P5", "3"),
    }
    return key in allowed or (key[0].lower(), key[1]) in {("m3", "6"), ("p4", "4"), ("p5", "3")}


def harmonic_interval_map() -> dict[str, str]:
    return {"P4": "4", "M3": "5", "m3": "6", "P5": "3"}


def predict_harmonic_register(
    *,
    technique: str,
    instrument: str,
    dynamic: str,
    pitch: str,
    midi: int | None,
    baseline_semantics: str,
    target_quantity: str,
    ordinary_by_dynamic: dict[str, float] | None = None,
) -> dict[str, Any]:
    """Predict harmonic EWSD from calibrated measured tables when available."""
    hit = lookup_calibrated_harmonic(
        instrument=instrument,
        technique=technique,
        note=pitch,
        dynamic=dynamic,
        ordinary_by_dynamic=ordinary_by_dynamic,
    )
    if hit is not None:
        measured = hit["measured_or_extrapolated"] == "measured"
        return {
            "mean": hit["mean"],
            "sd": hit.get("sd"),
            "baseline_mean": None,
            "value_kind": ValueKind.MEASURED if measured else ValueKind.ASSUMPTION_BASED_EXTRAPOLATION,
            "evidence_tier": (
                EvidenceTier.LEVEL_3_PARTIAL_EMPIRICAL
                if measured
                else EvidenceTier.LEVEL_1_ASSUMPTION_ONLY
            ),
            "measured_or_extrapolated": hit["measured_or_extrapolated"],
            "na_reason": None,
            "baseline_semantics": baseline_semantics,
            "warnings": [
                f"calibrated_harmonic_transfer={hit['transfer']}",
                f"source_dynamic={hit['source_dynamic']}",
                f"collection={hit.get('collection')}",
                "no_constant_factor_applied_to_ordinary_baseline",
            ],
            "assumption_ids": (
                ["ASSUMP_HARMONIC_CALIBRATED_LOOKUP"]
                if measured
                else ["ASSUMP_HARMONIC_DYNAMIC_RATIO_TRANSFER"]
            ),
            "assumptions_used": (
                ["ASSUMP_HARMONIC_CALIBRATED_LOOKUP"]
                if measured
                else ["ASSUMP_HARMONIC_DYNAMIC_RATIO_TRANSFER"]
            ),
            "assumptions_trace": [
                f"baseline_semantics={baseline_semantics}",
                f"transfer={hit['transfer']}",
                f"source_dynamic={hit['source_dynamic']}",
            ],
            "model_id": "harmonic_modal_frequency_with_descriptor_priors",
            "submodel_id": "calibrated_harmonic_descriptor_lookup",
            "register_shape_identified": True,
            "shape_source": "calibrated_measured_table",
            "g_t_active": False,
            "prior_dominated": not measured,
            "sigma_estimated_from_data": measured,
            "instrument": instrument,
            "technique": technique,
            "dynamic": dynamic,
            "pitch": pitch,
            "midi": midi,
            "target_quantity": target_quantity,
        }

    covered = has_calibrated_harmonic_coverage(instrument, technique)
    return {
        "value_kind": ValueKind.UNAVAILABLE,
        "evidence_tier": EvidenceTier.LEVEL_0_UNSUPPORTED,
        "measured_or_extrapolated": "unavailable",
        "na_reason": (
            "no_calibrated_harmonic_value_for_target"
            if covered
            else "harmonic_model_phase2"
        ),
        "baseline_semantics": baseline_semantics,
        "warnings": [
            "Harmonic descriptor unavailable for this sounding pitch/dynamic.",
            "No constant factor applied to ordinary baseline.",
        ],
        "assumption_ids": ["ASSUMP_HARMONIC_REQUIRES_MODAL_METADATA"],
        "assumptions_used": ["ASSUMP_HARMONIC_REQUIRES_MODAL_METADATA"],
        "assumptions_trace": [
            f"baseline_semantics={baseline_semantics}",
            "no_constant_factor_applied_to_ordinary_baseline",
            f"calibration_table_present_for_technique={covered}",
        ],
        "model_id": "M2_harmonic_stub",
        "submodel_id": "harmonic_phase2",
        "instrument": instrument,
        "technique": technique,
        "dynamic": dynamic,
        "pitch": pitch,
        "midi": midi,
        "target_quantity": target_quantity,
    }
