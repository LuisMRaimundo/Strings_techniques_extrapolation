"""Scientific honesty: constant technique effect must not be labeled as fitted spline."""

from __future__ import annotations

import math

from string_technique_model.extrapolation.nonlinear.prediction import predict_register
from string_technique_model.extrapolation.register_builder import build_register_from_notes


def _ordinary_rows(dynamic: str = "mf") -> list[dict]:
    reg = build_register_from_notes("G3", "G7", "vln", dynamic)
    rows = []
    for i, r in enumerate(reg):
        rows.append(
            {
                "note": r["note"],
                "midi": r["midi"],
                "value": 40.0 * math.exp(-0.01 * i),
                "instrument": "vln",
                "dynamic": dynamic,
                "technique": "ordinary",
                "quantity": "EWSD_score_acoustic_balanced",
                "source_path": "synthetic://ordinary_register",
                "data_status": "synthetic",
            }
        )
    return rows


def test_zero_tech_obs_model_id_is_constant_over_smoothed() -> None:
    results = predict_register(
        _ordinary_rows(),
        technique="sul_ponticello",
        instrument="vln",
        dynamic="mf",
        method="hierarchical_spline",
    )
    assert results
    r = results[0]
    assert r.model_id == "constant_technique_effect_over_smoothed_baseline"
    assert r.register_shape_identified is False
    assert r.shape_source == "constant_effect"
    assert r.target_technique_observations == 0
    assert r.g_t_active is False
    assert r.prior_dominated is True
    assert r.effect_kind == "regularization_assumption"
    assert r.alpha_t is not None
    assert r.alpha_origin
    assert r.baseline_record_ids
    assert r.interval_type == "assumption_distribution_interval"
    assert r.sigma_estimated_from_data is False
    assert "ASSUMP_" in ";".join(r.assumptions_used)
    assert "exp(" in (r.interval_formula or "")
    assert r.data_status == "synthetic"
    assert r.model_family == "bow_contact_model"
    assert r.selection_reason == "no_target_technique_observations"
    assert r.value_kind.value == "assumption_based_extrapolation"


def test_constant_multiplier_across_register() -> None:
    results = predict_register(
        _ordinary_rows(),
        technique="sul_tasto",
        instrument="vln",
        dynamic="mf",
        method="hierarchical_spline",
    )
    ratios = []
    for r in results:
        assert r.baseline_value and r.estimate_mean
        assert r.posterior_mean is None  # frequentist/assumption path
        ratios.append(r.estimate_mean / r.baseline_value)
    assert max(ratios) - min(ratios) < 1e-9
    assert all(r.technique_multiplier == ratios[0] for r in results)


def test_st_sp_not_exact_inverses() -> None:
    st = predict_register(_ordinary_rows(), technique="sul_tasto", instrument="vln", dynamic="mf")[0]
    sp = predict_register(_ordinary_rows(), technique="sul_ponticello", instrument="vln", dynamic="mf")[0]
    assert st.alpha_t is not None and sp.alpha_t is not None
    assert abs(st.alpha_t + sp.alpha_t) > 1e-6  # not symmetric inverses


def test_intervals_scale_with_baseline() -> None:
    results = predict_register(
        _ordinary_rows(),
        technique="sul_tasto",
        instrument="vln",
        dynamic="mf",
        pitches=["G3", "G7"],
        method="hierarchical_spline",
    )
    by_note = {r.pitch: r for r in results}
    g3, g7 = by_note["G3"], by_note["G7"]
    assert g3.interval_high and g3.estimate_mean
    assert g7.interval_high and g7.estimate_mean
    half3 = g3.interval_high - g3.estimate_mean
    half7 = g7.interval_high - g7.estimate_mean
    # Absolute half-width should shrink with baseline (multiplicative)
    assert half3 > half7
