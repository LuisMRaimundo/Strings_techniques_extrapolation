"""Calibrated harmonic descriptor lookup (Orchidea measured table)."""

from __future__ import annotations

from string_technique_model.extrapolation.nonlinear.harmonic_calibration_table import (
    clear_calibrated_harmonic_table_cache,
    has_calibrated_harmonic_coverage,
    lookup_calibrated_harmonic,
)
from string_technique_model.extrapolation.nonlinear.harmonic_model import predict_harmonic_register
from string_technique_model.extrapolation.nonlinear.prediction import predict_register
from string_technique_model.extrapolation.register_builder import build_register_from_notes


def setup_function() -> None:
    clear_calibrated_harmonic_table_cache()


def test_orchidea_artificial_coverage_detected() -> None:
    assert has_calibrated_harmonic_coverage("vln", "artificial_harmonic")
    assert has_calibrated_harmonic_coverage("vln", "natural_harmonic")


def test_exact_mf_lookup() -> None:
    hit = lookup_calibrated_harmonic(
        instrument="vln",
        technique="artificial_harmonic",
        note="G5",
        dynamic="mf",
    )
    assert hit is not None
    assert hit["transfer"] == "exact_measured"
    assert hit["mean"] > 0


def test_ff_via_ordinary_ratio() -> None:
    base = lookup_calibrated_harmonic(
        instrument="vln",
        technique="artificial_harmonic",
        note="G5",
        dynamic="mf",
    )
    assert base is not None
    hit = lookup_calibrated_harmonic(
        instrument="vln",
        technique="artificial_harmonic",
        note="G5",
        dynamic="ff",
        ordinary_by_dynamic={"mf": 50.0, "ff": 55.0},
    )
    assert hit is not None
    assert hit["transfer"] == "ordinary_dynamic_ratio"
    assert abs(hit["mean"] - base["mean"] * (55.0 / 50.0)) < 1e-6


def test_pp_proxy_when_ordinary_lacks_mf() -> None:
    """GUI often fills only pp ordinary; still return calibrated mf note as proxy."""
    base = lookup_calibrated_harmonic(
        instrument="vln",
        technique="artificial_harmonic",
        note="G5",
        dynamic="mf",
    )
    assert base is not None
    hit = lookup_calibrated_harmonic(
        instrument="vln",
        technique="artificial_harmonic",
        note="G5",
        dynamic="pp",
        ordinary_by_dynamic={"pp": 20.0},
    )
    assert hit is not None
    assert hit["transfer"] == "calibrated_source_dynamic_proxy"
    assert abs(hit["mean"] - base["mean"]) < 1e-9


def test_nearest_note_fills_unmeasured_pitch() -> None:
    hit = lookup_calibrated_harmonic(
        instrument="vln",
        technique="artificial_harmonic",
        note="C8",
        dynamic="pp",
        ordinary_by_dynamic={"pp": 20.0},
    )
    assert hit is not None
    assert "nearest_note" in hit["transfer"]
    assert hit["nearest_semitones"] is not None
    assert hit["nearest_semitones"] <= 3


def test_predict_register_numeric_for_calibrated_artificial() -> None:
    reg = build_register_from_notes("G3", "G7", "vln", "mf")
    ordinary = [
        {
            "note": r["note"],
            "midi": r["midi"],
            "value": 40.0,
            "instrument": "vln",
            "dynamic": "mf",
            "technique": "ordinary",
            "quantity": "EWSD_score_acoustic_balanced",
            "source_path": f"synthetic://{r['note']}",
            "data_status": "synthetic_integration_test",
        }
        for r in reg
    ]
    out = predict_register(
        ordinary,
        technique="artificial_harmonic",
        instrument="vln",
        dynamic="mf",
        harmonic_selection_mode="configured_physically_plausible_harmonics",
        harmonic_sounding_max="C8",
        include_low_harmonics=True,
    )
    numeric = [r for r in out if r.estimate_mean is not None and r.value_kind.value != "unavailable"]
    assert numeric
    assert any(r.selected_model_id == "harmonic_modal_frequency_with_descriptor_priors" for r in numeric)
    assert any(r.model_status == "calibrated_descriptor_lookup" for r in numeric)


def test_predict_harmonic_register_direct() -> None:
    pred = predict_harmonic_register(
        technique="artificial_harmonic",
        instrument="vln",
        dynamic="mf",
        pitch="A5",
        midi=81,
        baseline_semantics="ordinary_arco_open_string_baseline",
        target_quantity="EWSD_score_acoustic_balanced",
    )
    assert pred["mean"] is not None
    assert pred["na_reason"] is None
