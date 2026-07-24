"""Harmonic sounding-register generation (not ordinary chromatic copy)."""

from __future__ import annotations

from string_technique_model.extrapolation.nonlinear.harmonic_register import (
    annotate_baseline_extrapolation,
    generate_artificial_harmonic_targets,
    generate_natural_harmonic_targets,
    physical_sounding_bounds,
)
from string_technique_model.extrapolation.nonlinear.model_selection import (
    DataAvailability,
    select_model,
)
from string_technique_model.extrapolation.nonlinear.prediction import predict_register
from string_technique_model.extrapolation.register_builder import (
    build_register_from_notes,
    generate_requests_for_register,
    resolve_note,
)


def test_natural_harmonics_are_partials_not_chromatic() -> None:
    rows = generate_natural_harmonic_targets(
        "vln",
        selection_mode="configured_physically_plausible_harmonics",
        sounding_max="C8",
    )
    assert rows
    assert all(r["technique"] == "natural_harmonic" for r in rows)
    assert all(r["harmonic_order"] >= 2 for r in rows)
    assert all(r.get("string") for r in rows)
    # Not a dense chromatic fill
    sounding = {r["sounding_pitch"] for r in rows}
    assert len(sounding) < 40
    # Physical range starts from order-2 of open G3 → ~G4, not C6
    assert min(float(r["sounding_midi_float"]) for r in rows) < 84


def test_physical_bounds_violin_below_c6() -> None:
    lo, hi, lo_l, hi_l = physical_sounding_bounds("vln", "natural_harmonic")
    assert lo < 84
    assert hi_l == "C8" or hi >= 108 - 1


def test_artificial_harmonics_map_from_sounding() -> None:
    rows = generate_artificial_harmonic_targets(
        "vln",
        selection_mode="configured_physically_plausible_harmonics",
        sounding_max="C8",
    )
    assert rows
    for r in rows:
        assert r["harmonic_order"] == 4
        assert r["stopped_pitch"]
        stopped = resolve_note(r["stopped_pitch"])
        assert stopped is not None
        assert int(r["sounding_midi"]) - int(stopped[1]) == 24


def test_custom_range_can_still_restrict() -> None:
    rows = generate_natural_harmonic_targets(
        "vln",
        selection_mode="custom_sounding_range",
        sounding_min="C6",
        sounding_max="C8",
        include_low_harmonics=False,
    )
    assert rows
    assert all(float(r["sounding_midi_float"]) >= 84 for r in rows)


def test_requests_do_not_copy_ordinary_for_harmonics() -> None:
    reg = build_register_from_notes("G3", "G7", "vln", "mf")[:10]
    measured = [
        {**r, "value": 40.0, "technique": "ordinary", "quantity": "EWSD_score_acoustic_balanced"}
        for r in reg
    ]
    reqs = generate_requests_for_register(
        measured,
        ["natural_harmonic", "sul_tasto"],
        harmonic_selection_mode="configured_physically_plausible_harmonics",
        harmonic_sounding_max="C8",
        include_low_harmonics=True,
    )
    harm = [r for r in reqs if r["technique"] == "natural_harmonic"]
    tasto = [r for r in reqs if r["technique"] == "sul_tasto"]
    assert len(tasto) == 10
    assert harm
    assert len(harm) != 10  # not 1:1 with ordinary notes


def test_predict_register_harmonic_fields_and_fallback() -> None:
    reg = build_register_from_notes("G3", "G7", "vln", "mf")
    measured = [
        {
            "note": r["note"],
            "midi": r["midi"],
            "value": 35.0,
            "instrument": "vln",
            "dynamic": "mf",
            "technique": "ordinary",
            "quantity": "EWSD_score_acoustic_balanced",
            "source_path": f"synthetic_integration_test://{r['note']}",
            "data_status": "synthetic_integration_test",
        }
        for r in reg
    ]
    out = predict_register(
        measured,
        technique="natural_harmonic",
        instrument="vln",
        dynamic="mf",
        harmonic_selection_mode="configured_physically_plausible_harmonics",
        harmonic_sounding_max="C8",
        include_low_harmonics=True,
    )
    assert out
    assert all(r.harmonic_order is not None for r in out)
    assert all(r.selected_model_id == "harmonic_modal_frequency_with_descriptor_priors" for r in out)
    assert all(r.modal_metadata_status == "complete" for r in out)
    assert all(r.acoustic_calibration_status == "available" for r in out)
    assert all(
        "calibrated_harmonic_descriptor_model" not in (r.missing_model_components or []) for r in out
    )
    numeric = [r for r in out if r.estimate_mean is not None and r.value_kind.value != "unavailable"]
    assert numeric
    assert all(r.model_status == "calibrated_descriptor_lookup" for r in numeric)
    assert out[0].data_status == "synthetic_integration_test"
    assert out[0].scientific_use == "prohibited_for_doctoral_evidence"
    assert out[0].physical_range_min
    assert out[0].included_by_physical_model is True
    assert out[0].configured_order_min == 2
    assert out[0].order_selection_reason == "practical_analysis_scope"
    assert "string" in (out[0].available_covariates or []) or out[0].string_name
    assert not (out[0].missing_covariates or [])


def test_harmonic_selection_covariates_not_bow() -> None:
    d = select_model(
        DataAvailability(
            technique="artificial_harmonic",
            instrument="vln",
            dynamic="mf",
            target_quantity="EWSD_score_acoustic_balanced",
            n_target_observations=0,
            missing_covariates=["harmonic_type", "string", "harmonic_order"],
        )
    )
    assert d.selected_model_id == "harmonic_modal_metadata_gate"
    assert d.fallback_level == "no_numeric_fallback"
    assert d.modal_metadata_status == "incomplete"
    assert d.acoustic_calibration_status == "unavailable"
    assert "beta" not in d.required_covariates
    assert "bow_force" not in d.required_covariates
    assert "ASSUMP_HARMONIC_REQUIRES_MODAL_METADATA" in d.assumption_ids


def test_baseline_extrapolation_annotation() -> None:
    t = {"sounding_midi_float": 108.0, "sounding_midi": 108}  # C8
    a = annotate_baseline_extrapolation(t, baseline_midi_min=55, baseline_midi_max=103)
    assert a["outside_ordinary_baseline_range"] is True
    assert a["baseline_extrapolation_semitones"] == 5.0
