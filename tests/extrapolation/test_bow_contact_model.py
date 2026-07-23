"""Bow-contact submodel tests (sul tasto / sul ponticello)."""

from __future__ import annotations

import math

import pandas as pd

from string_technique_model.extrapolation.nonlinear.baseline import fit_ordinary_baseline
from string_technique_model.extrapolation.nonlinear.bow_contact_model import fit_bow_contact_effect
from string_technique_model.extrapolation.nonlinear.mute_model import fit_mute_effect


def _baseline_df() -> pd.DataFrame:
    rows = []
    for midi in range(55, 90):
        rows.append(
            {
                "instrument": "vln",
                "technique": "ordinary",
                "dynamic": "pp",
                "note": f"M{midi}",
                "midi": midi,
                "value": 40.0 * math.exp(-0.01 * (midi - 55)),
                "quantity": "EWSD_score_acoustic_balanced",
            }
        )
    return pd.DataFrame(rows)


def test_sul_ponticello_prior_dominated_without_technique_obs() -> None:
    baseline = fit_ordinary_baseline(_baseline_df())
    fit = fit_bow_contact_effect(
        baseline,
        None,
        technique="sul_ponticello",
        instrument="vln",
        dynamic="pp",
    )
    assert fit is not None
    assert fit.prior_dominated
    assert fit.alpha_t > 0
    assert fit.model_id == "constant_technique_effect_over_smoothed_baseline"
    assert fit.register_shape_identified is False
    bf = baseline.get("vln", "pp")
    assert bf is not None
    pred = fit.predict(bf, 69.0)
    assert float(pred["mean"][0]) > float(pred["baseline_mean"][0])
    assert pred["g_t_active"] is False


def test_sul_tasto_direction_opposite_to_ponticello() -> None:
    baseline = fit_ordinary_baseline(_baseline_df())
    st = fit_bow_contact_effect(baseline, None, technique="sul_tasto", instrument="vln", dynamic="pp")
    sp = fit_bow_contact_effect(baseline, None, technique="sul_ponticello", instrument="vln", dynamic="pp")
    assert st.alpha_t < 0 < sp.alpha_t


def test_bow_and_mute_are_distinct_submodels() -> None:
    baseline = fit_ordinary_baseline(_baseline_df())
    bow = fit_bow_contact_effect(baseline, None, technique="sul_tasto", instrument="vln", dynamic="pp")
    mute = fit_mute_effect(baseline, None, instrument="vln", dynamic="pp")
    assert bow.submodel_id != mute.submodel_id
    assert "bow" in bow.submodel_id
    assert "mute" in mute.submodel_id
