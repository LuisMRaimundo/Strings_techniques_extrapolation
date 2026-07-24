"""Harmonic stub scientific guards."""

from __future__ import annotations

from string_technique_model.extrapolation.nonlinear.harmonic_model import (
    harmonic_interval_map,
    predict_harmonic_register,
    validate_touch_interval,
)
from string_technique_model.extrapolation.nonlinear.prediction import predict_register


def test_interval_map() -> None:
    m = harmonic_interval_map()
    assert m["P4"] == "4"
    assert m["P5"] == "3"
    assert validate_touch_interval("P4", "4")


def test_harmonic_not_constant_factor_by_default() -> None:
    rows = [
        {
            "note": "A4",
            "midi": 69,
            "value": 20.0,
            "instrument": "vln",
            "dynamic": "pp",
            "technique": "ordinary",
            "quantity": "EWSD_score_acoustic_balanced",
        },
        {
            "note": "B4",
            "midi": 71,
            "value": 18.0,
            "instrument": "vln",
            "dynamic": "pp",
            "technique": "ordinary",
            "quantity": "EWSD_score_acoustic_balanced",
        },
    ]
    results = predict_register(
        rows,
        technique="artificial_harmonic",
        instrument="vln",
        dynamic="pp",
        method="hierarchical_spline",
        harmonic_selection_mode="configured_physically_plausible_harmonics",
        harmonic_sounding_max="C8",
    )
    assert results
    assert results[0].estimate_mean is None
    assert results[0].posterior_mean is None
    # Violin art has mf tables; pp without collection-matched ordinary anchors is NA
    # (not a silent proxy, not "no calibration for technique").
    assert results[0].na_reason in {
        "no_calibrated_harmonic_value_for_target",
        "no_harmonic_acoustic_calibration_data",
    }
    assert results[0].model_family == "harmonic_modal_model"
    assert results[0].selected_model_id in {
        "harmonic_modal_frequency_with_descriptor_priors",
        "harmonic_modal_acoustic_model_unavailable",
    }
    assert results[0].value_kind.value == "unavailable"
    assert results[0].selection_mode
    assert results[0].configuration_policy == "canonical_single_string_assignment"
    assert results[0].support_class in {None, "unsupported"} or str(
        results[0].support_class
    ) == "unsupported"


def test_stub_dict_keys() -> None:
    stub = predict_harmonic_register(
        technique="natural_harmonic",
        instrument="vln",
        dynamic="pp",
        pitch="A4",
        midi=69,
        baseline_semantics="unresolved",
        target_quantity="EWSD_score_acoustic_balanced",
    )
    assert stub["measured_or_extrapolated"] == "unavailable"
