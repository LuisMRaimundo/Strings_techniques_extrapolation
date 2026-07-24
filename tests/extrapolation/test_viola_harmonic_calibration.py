"""Viola harmonic calibration acceptance tests."""

from __future__ import annotations

from string_technique_model.extrapolation.nonlinear.harmonic_source_resolver import (
    clear_harmonic_calibration_cache,
    coverage_counts,
    has_calibrated_harmonic_coverage,
    resolve_harmonic_value,
)
from string_technique_model.extrapolation.nonlinear.harmonic_support import HarmonicSupportClass
from string_technique_model.extrapolation.nonlinear.prediction import predict_register
from string_technique_model.extrapolation.register_builder import build_register_from_notes


def setup_function() -> None:
    clear_harmonic_calibration_cache()


def test_viola_artificial_mf_coverage_from_tables() -> None:
    assert has_calibrated_harmonic_coverage("vla", "artificial_harmonic")
    assert coverage_counts("vla", "artificial_harmonic", "mf") == 35


def test_viola_natural_uncalibrated() -> None:
    assert not has_calibrated_harmonic_coverage("vla", "natural_harmonic")
    assert coverage_counts("vla", "natural_harmonic") == 0


def test_viola_artificial_mf_measured_at_supported_note() -> None:
    res = resolve_harmonic_value(
        instrument="vla",
        technique="artificial_harmonic",
        note="C5",
        dynamic="mf",
    )
    assert res.mean is not None and res.mean > 0
    assert res.measured_or_extrapolated == "measured"
    assert res.source_instrument == "vla"
    assert res.source_dynamic == "mf"


def test_viola_artificial_pp_without_ordinary_rows_is_unsupported() -> None:
    """Pooled GUI ordinary mean is forbidden; without same-note ordinary → NA."""
    res = resolve_harmonic_value(
        instrument="vla",
        technique="artificial_harmonic",
        note="C5",
        dynamic="pp",
    )
    assert res.mean is None
    assert res.support_class == HarmonicSupportClass.UNSUPPORTED


def test_viola_natural_predict_register_all_unavailable_numeric() -> None:
    reg = build_register_from_notes("C3", "C7", "vla", "mf")
    ordinary = [
        {
            "note": r["note"],
            "midi": r["midi"],
            "value": 25.0,
            "instrument": "vla",
            "dynamic": "mf",
            "technique": "ordinary",
            "quantity": "EWSD_score_acoustic_balanced",
            "source_path": "synthetic://viola",
            "data_status": "synthetic_integration_test",
        }
        for r in reg
    ]
    out = predict_register(
        ordinary,
        technique="natural_harmonic",
        instrument="vla",
        dynamic="mf",
        harmonic_selection_mode="configured_physically_plausible_harmonics",
        harmonic_sounding_max="C8",
        include_low_harmonics=True,
    )
    assert out
    assert all(r.estimate_mean is None for r in out)
    assert all(
        (r.support_class == "unsupported") or (r.selected_model_id == "harmonic_modal_acoustic_model_unavailable")
        for r in out
    )
