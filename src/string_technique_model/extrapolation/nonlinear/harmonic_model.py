"""Harmonic technique predictor (calibrated descriptor resolver + uncalibrated modal gate)."""

from __future__ import annotations

from typing import Any

from string_technique_model.extrapolation.nonlinear.domain import EvidenceTier, ValueKind
from string_technique_model.extrapolation.nonlinear.harmonic_source_resolver import (
    OrdinaryAnchor,
    has_calibrated_harmonic_coverage,
    resolve_harmonic_value,
)
from string_technique_model.extrapolation.nonlinear.harmonic_support import (
    DEFAULT_ALLOW_CROSS_INSTRUMENT,
    DEFAULT_ALLOW_INTERPOLATION,
    HarmonicSupportClass,
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
    ordinary_rows: list[OrdinaryAnchor] | None = None,
    allow_interpolation: bool = DEFAULT_ALLOW_INTERPOLATION,
    allow_cross_instrument: bool = DEFAULT_ALLOW_CROSS_INSTRUMENT,
) -> dict[str, Any]:
    """Predict harmonic EWSD via priority resolver (instrument-isolated)."""
    del ordinary_by_dynamic  # pooled GUI mean is not an admissible ordinary baseline
    resolution = resolve_harmonic_value(
        instrument=instrument,
        technique=technique,
        note=pitch,
        dynamic=dynamic,
        ordinary_rows=ordinary_rows,
        allow_interpolation=allow_interpolation,
        allow_cross_instrument=allow_cross_instrument,
        quantity=target_quantity,
    )

    common_prov = {
        "support_class": resolution.support_class.value,
        "source_instrument": resolution.source_instrument,
        "source_collection": resolution.source_collection,
        "source_technique": resolution.source_technique,
        "source_dynamic": resolution.source_dynamic,
        "target_instrument": resolution.target_instrument,
        "target_dynamic": resolution.target_dynamic,
        "source_record_ids": list(resolution.source_record_ids),
        "ordinary_baseline_record_ids": list(resolution.ordinary_baseline_record_ids),
        "transfer_method": resolution.transfer_method,
        "transfer_formula": resolution.transfer_formula,
        "transfer_gate_status": resolution.transfer_gate_status,
        "cross_instrument_transfer_enabled": resolution.cross_instrument_transfer_enabled,
        "selection_reason": resolution.selection_reason,
        "rejection_reason": resolution.rejection_reason,
        "harmonic_candidates": [c.__dict__ for c in resolution.candidates],
        "calibration_processing_version": resolution.processing_version,
    }

    if resolution.mean is not None and resolution.support_class != HarmonicSupportClass.UNSUPPORTED:
        measured = resolution.measured_or_extrapolated == "measured"
        return {
            "mean": resolution.mean,
            "sd": resolution.sd,
            "baseline_mean": None,
            "value_kind": ValueKind.MEASURED if measured else ValueKind.ASSUMPTION_BASED_EXTRAPOLATION,
            "evidence_tier": (
                EvidenceTier.LEVEL_3_PARTIAL_EMPIRICAL
                if measured
                else EvidenceTier.LEVEL_1_ASSUMPTION_ONLY
            ),
            "measured_or_extrapolated": resolution.measured_or_extrapolated,
            "na_reason": None,
            "baseline_semantics": baseline_semantics,
            "warnings": [
                f"support_class={resolution.support_class.value}",
                f"transfer_method={resolution.transfer_method}",
                f"source_collection={resolution.source_collection}",
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
                f"selection_reason={resolution.selection_reason}",
                f"support_class={resolution.support_class.value}",
            ],
            "model_id": "harmonic_modal_frequency_with_descriptor_priors",
            "submodel_id": "calibrated_harmonic_descriptor_resolver",
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
            **common_prov,
        }

    covered = has_calibrated_harmonic_coverage(instrument, technique)
    return {
        "value_kind": ValueKind.UNAVAILABLE,
        "evidence_tier": EvidenceTier.LEVEL_0_UNSUPPORTED,
        "measured_or_extrapolated": "unavailable",
        "na_reason": resolution.na_reason
        or (
            "no_calibrated_harmonic_value_for_target"
            if covered
            else "no_harmonic_acoustic_calibration_data"
        ),
        "baseline_semantics": baseline_semantics,
        "warnings": [
            "Harmonic descriptor unavailable under priority/gate rules.",
            "No constant factor applied to ordinary baseline.",
            f"support_class={HarmonicSupportClass.UNSUPPORTED.value}",
        ],
        "assumption_ids": ["ASSUMP_HARMONIC_REQUIRES_MODAL_METADATA"],
        "assumptions_used": ["ASSUMP_HARMONIC_REQUIRES_MODAL_METADATA"],
        "assumptions_trace": [
            f"baseline_semantics={baseline_semantics}",
            f"selection_reason={resolution.selection_reason}",
        ],
        # Keep calibrated model id when technique has tables but this note fails gates.
        "model_id": (
            "harmonic_modal_frequency_with_descriptor_priors"
            if covered
            else "harmonic_modal_acoustic_model_unavailable"
        ),
        "submodel_id": "modal_geometry_only" if not covered else "calibrated_resolver_unsupported_target",
        "register_shape_identified": None,
        "shape_source": "not_applicable",
        "g_t_active": None,
        "prior_dominated": None,
        "sigma_estimated_from_data": None,
        "instrument": instrument,
        "technique": technique,
        "dynamic": dynamic,
        "pitch": pitch,
        "midi": midi,
        "target_quantity": target_quantity,
        **common_prov,
    }
