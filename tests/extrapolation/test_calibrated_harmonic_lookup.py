"""Calibrated harmonic descriptor resolver (compatibility facade)."""

from __future__ import annotations

from string_technique_model.extrapolation.nonlinear.harmonic_calibration_table import (
    clear_calibrated_harmonic_table_cache,
    has_calibrated_harmonic_coverage,
    lookup_calibrated_harmonic,
)
from string_technique_model.extrapolation.nonlinear.harmonic_model import predict_harmonic_register
from string_technique_model.extrapolation.nonlinear.harmonic_source_resolver import OrdinaryAnchor
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
    assert hit["transfer"] in {"exact_measured", "multi_collection_mean"}
    assert hit["mean"] > 0
    assert hit["support_class"] in {
        "same_instrument_same_collection_measured",
        "same_instrument_cross_collection_measured",
    }


def test_pp_without_ordinary_rows_returns_none() -> None:
    hit = lookup_calibrated_harmonic(
        instrument="vln",
        technique="artificial_harmonic",
        note="G5",
        dynamic="pp",
        ordinary_by_dynamic={"pp": 20.0},  # ignored by design
    )
    assert hit is None


def test_pp_with_collection_ordinary_rows_transfers() -> None:
    from string_technique_model.extrapolation.nonlinear.harmonic_source_resolver import (
        load_raw_harmonic_calibration_table,
    )

    raw = load_raw_harmonic_calibration_table()
    row = raw[
        (raw.instrument == "vla")
        & (raw.technique == "artificial_harmonic")
        & (raw.note == "A5")
        & (raw.dynamic == "mf")
        & (raw.collection == "mcgill")
    ].iloc[0]
    h_mf = float(row["value"])
    hit = lookup_calibrated_harmonic(
        instrument="vla",
        technique="artificial_harmonic",
        note="A5",
        dynamic="pp",
        ordinary_rows=[
            OrdinaryAnchor(instrument="vla", collection="mcgill", note="A5", dynamic="mf", value=40.0),
            OrdinaryAnchor(instrument="vla", collection="mcgill", note="A5", dynamic="pp", value=20.0),
        ],
    )
    assert hit is not None
    assert hit["support_class"] == "same_instrument_dynamic_transfer"
    assert hit["collection"] == "mcgill"
    assert abs(hit["mean"] - h_mf * 0.5) < 1e-6


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
    assert pred.get("mean") is not None
    assert pred.get("na_reason") is None
    assert pred.get("support_class") != "unsupported"
