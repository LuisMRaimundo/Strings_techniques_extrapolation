"""Model selection engine tests."""

from __future__ import annotations

import pandas as pd

from string_technique_model.extrapolation.nonlinear.model_selection import (
    DataAvailability,
    assess_data_availability,
    family_for_technique,
    select_model,
    select_register_model,
)
from string_technique_model.extrapolation.nonlinear.prediction import predict_register


def test_family_mapping() -> None:
    assert family_for_technique("sul_ponticello") == "bow_contact_model"
    assert family_for_technique("con_sordino") == "mute_transfer_model"
    assert family_for_technique("artificial_harmonic") == "harmonic_modal_model"
    assert family_for_technique("flautando") == "execution_target_model"
    assert family_for_technique("flautando") != family_for_technique("sul_tasto")


def test_zero_obs_selects_constant_bow() -> None:
    data = DataAvailability(
        technique="sul_ponticello",
        instrument="vln",
        dynamic="mf",
        target_quantity="EWSD_score_acoustic_balanced",
        n_target_observations=0,
        missing_covariates=["beta", "bow_force", "bow_velocity"],
    )
    d = select_model(data)
    assert d.selected_model_id == "constant_technique_effect_over_smoothed_baseline"
    assert d.selection_reason == "no_target_technique_observations"
    assert d.fallback_level == "constant_assumption"
    assert "physical_informed_bow_contact" in d.rejected_model_ids
    assert d.rejection_reasons["physical_informed_bow_contact"].startswith("missing_covariates")


def test_partial_coverage_selects_linear() -> None:
    data = DataAvailability(
        technique="sul_tasto",
        instrument="vln",
        dynamic="pp",
        target_quantity="spectral_centroid",
        n_target_observations=4,
        distinct_pitch_count=4,
        pitch_span_semitones=8.0,
        spline_design_is_identifiable=False,
        missing_covariates=["beta", "bow_force", "bow_velocity"],
    )
    d = select_model(data)
    assert d.selected_model_id == "regularized_linear_register_trend"
    assert d.register_shape_identified is True
    assert select_register_model(data) == "regularized_linear_trend"


def test_full_coverage_selects_spline() -> None:
    data = DataAvailability(
        technique="sul_ponticello",
        instrument="vln",
        dynamic="pp",
        target_quantity="spectral_centroid",
        n_target_observations=12,
        distinct_pitch_count=12,
        pitch_span_semitones=24.0,
        spline_design_is_identifiable=True,
        missing_covariates=["beta", "bow_force", "bow_velocity"],
    )
    d = select_model(data)
    assert d.selected_model_id == "penalized_register_spline"


def test_mute_marks_constant_assumption() -> None:
    data = DataAvailability(
        technique="con_sordino",
        instrument="vln",
        dynamic="mf",
        target_quantity="EWSD_score_acoustic_balanced",
        n_target_observations=0,
        authorize_numeric_assumption=True,
        has_spectra_or_ltas=False,
    )
    d = select_model(data)
    assert d.selected_model_id == "constant_assumption_fallback"
    assert "constant_assumption_fallback" in d.marks or d.fallback_level == "constant_assumption"


def test_harmonic_never_constant_factor() -> None:
    data = DataAvailability(
        technique="natural_harmonic",
        instrument="vln",
        dynamic="pp",
        target_quantity="EWSD_score_acoustic_balanced",
        n_target_observations=0,
        has_harmonic_order=False,
    )
    d = select_model(data)
    assert d.selected_model_id == "harmonic_modal_metadata_gate"
    assert d.modal_metadata_status == "incomplete"
    assert d.acoustic_calibration_status == "unavailable"
    assert d.value_kind_hint == "unavailable"
    assert "constant" not in d.selected_model_id


def test_predict_exports_selection_fields() -> None:
    rows = [
        {
            "note": "A4",
            "midi": 69,
            "value": 20.0,
            "instrument": "vln",
            "dynamic": "mf",
            "technique": "ordinary",
            "quantity": "EWSD_score_acoustic_balanced",
            "source_path": "synthetic://x",
        },
        {
            "note": "B4",
            "midi": 71,
            "value": 18.0,
            "instrument": "vln",
            "dynamic": "mf",
            "technique": "ordinary",
            "quantity": "EWSD_score_acoustic_balanced",
            "source_path": "synthetic://x",
        },
    ]
    results = predict_register(
        rows,
        technique="sul_ponticello",
        instrument="vln",
        dynamic="mf",
        pitches=["A4"],
        method="hierarchical_spline",
    )
    r = results[0]
    assert r.model_family == "bow_contact_model"
    assert r.selected_model_id == "constant_technique_effect_over_smoothed_baseline"
    assert r.selection_reason == "no_target_technique_observations"
    assert r.missing_covariates
    assert "beta" in r.missing_covariates
    assert r.value_kind.value == "assumption_based_extrapolation"


def test_assess_from_dataframe() -> None:
    tech = pd.DataFrame(
        [
            {"technique": "sul_ponticello", "instrument": "vln", "dynamic": "pp", "midi": 60, "value": 10.0},
            {"technique": "sul_ponticello", "instrument": "vln", "dynamic": "pp", "midi": 64, "value": 11.0},
            {"technique": "sul_ponticello", "instrument": "vln", "dynamic": "pp", "midi": 67, "value": 12.0},
            {"technique": "sul_ponticello", "instrument": "vln", "dynamic": "pp", "midi": 70, "value": 13.0},
        ]
    )
    data = assess_data_availability(
        technique="sul_ponticello",
        instrument="vln",
        dynamic="pp",
        target_quantity="spectral_centroid",
        technique_observations=tech,
    )
    assert data.n_target_observations == 4
    assert data.distinct_pitch_count == 4
    d = select_model(data)
    assert d.selected_model_id == "regularized_linear_register_trend"
