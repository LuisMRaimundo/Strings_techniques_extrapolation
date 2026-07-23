"""Harmonic technique stub (Phase 2)."""

from __future__ import annotations

from typing import Any

from string_technique_model.extrapolation.nonlinear.domain import EvidenceTier, ValueKind


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
) -> dict[str, Any]:
    """Return unavailable numeric prediction; harmonic model deferred to Phase 2."""
    return {
        "value_kind": ValueKind.UNAVAILABLE,
        "evidence_tier": EvidenceTier.LEVEL_0_UNSUPPORTED,
        "measured_or_extrapolated": "unavailable",
        "na_reason": "harmonic_model_phase2",
        "baseline_semantics": baseline_semantics,
        "warnings": [
            "Harmonic extrapolation is not active in Phase 1.",
            "No constant factor applied to ordinary baseline.",
        ],
        "assumption_ids": ["ASSUMP_HARMONIC_REQUIRES_MODAL_METADATA"],
        "assumptions_used": ["ASSUMP_HARMONIC_REQUIRES_MODAL_METADATA"],
        "assumptions_trace": [
            f"baseline_semantics={baseline_semantics}",
            "no_constant_factor_applied_to_ordinary_baseline",
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
