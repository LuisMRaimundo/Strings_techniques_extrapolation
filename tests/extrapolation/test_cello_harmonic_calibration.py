"""Cello harmonic calibration remains uncalibrated (modal geometry only)."""

from __future__ import annotations

from string_technique_model.extrapolation.nonlinear.harmonic_source_resolver import (
    clear_harmonic_calibration_cache,
    coverage_counts,
    has_calibrated_harmonic_coverage,
    resolve_harmonic_value,
)
from string_technique_model.extrapolation.nonlinear.harmonic_support import HarmonicSupportClass
from string_technique_model.extrapolation.nonlinear.harmonic_register import _open_strings
from string_technique_model.extrapolation.nonlinear.prediction import predict_register
from string_technique_model.extrapolation.register_builder import build_register_from_notes


def setup_function() -> None:
    clear_harmonic_calibration_cache()


def test_cello_open_strings_from_config() -> None:
    assert _open_strings("vlc") == ["C2", "G2", "D3", "A3"]


def test_cello_no_calibration_coverage() -> None:
    assert not has_calibrated_harmonic_coverage("vlc", "artificial_harmonic")
    assert not has_calibrated_harmonic_coverage("vlc", "natural_harmonic")
    assert coverage_counts("vlc", "artificial_harmonic") == 0
    assert coverage_counts("vlc", "natural_harmonic") == 0


def test_cello_resolve_unsupported() -> None:
    for tech in ("artificial_harmonic", "natural_harmonic"):
        res = resolve_harmonic_value(
            instrument="vlc",
            technique=tech,
            note="A3",
            dynamic="mf",
        )
        assert res.support_class == HarmonicSupportClass.UNSUPPORTED
        assert res.mean is None


def test_cello_predict_register_modal_but_na_values() -> None:
    reg = build_register_from_notes("C2", "C5", "vlc", "mf")
    ordinary = [
        {
            "note": r["note"],
            "midi": r["midi"],
            "value": 30.0,
            "instrument": "vlc",
            "dynamic": "mf",
            "technique": "ordinary",
            "quantity": "EWSD_score_acoustic_balanced",
            "source_path": "synthetic://cello",
            "data_status": "synthetic_integration_test",
        }
        for r in reg
    ]
    out = predict_register(
        ordinary,
        technique="artificial_harmonic",
        instrument="vlc",
        dynamic="mf",
        harmonic_selection_mode="configured_physically_plausible_harmonics",
        include_low_harmonics=True,
    )
    assert out  # modal targets generated
    assert all(r.estimate_mean is None for r in out)
    assert all(
        r.model_status == "modal_frequencies_generated_acoustic_values_unavailable"
        or r.support_class == "unsupported"
        for r in out
    )
