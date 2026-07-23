"""Mute submodel tests."""

from __future__ import annotations

import math

import pandas as pd

from string_technique_model.extrapolation.nonlinear.baseline import fit_ordinary_baseline
from string_technique_model.extrapolation.nonlinear.mute_model import fit_mute_effect


def test_mute_uses_scalar_reduction_flag() -> None:
    rows = [
        {
            "instrument": "vln",
            "technique": "ordinary",
            "dynamic": "pp",
            "note": f"n{m}",
            "midi": m,
            "value": 30.0 * math.exp(-0.008 * (m - 55)),
            "quantity": "EWSD_score_acoustic_balanced",
        }
        for m in range(55, 85)
    ]
    baseline = fit_ordinary_baseline(pd.DataFrame(rows))
    fit = fit_mute_effect(baseline, None, instrument="vln", dynamic="pp")
    assert fit.model_reduction == "scalar_descriptor_approximation"
    assert fit.alpha_mute < 0
    assert fit.prior_dominated


def test_heavy_mute_refused() -> None:
    rows = [
        {
            "instrument": "vln",
            "technique": "ordinary",
            "dynamic": "pp",
            "note": f"n{m}",
            "midi": m,
            "value": 20.0,
            "quantity": "EWSD_score_acoustic_balanced",
        }
        for m in (60, 62, 64, 66)
    ]
    tech = pd.DataFrame(
        [
            {
                "instrument": "vln",
                "technique": "con_sordino",
                "dynamic": "pp",
                "note": "A4",
                "midi": 69,
                "value": 5.0,
                "quantity": "EWSD_score_acoustic_balanced",
                "mute_type": "heavy_practice",
            }
        ]
    )
    baseline = fit_ordinary_baseline(pd.DataFrame(rows))
    out = fit_mute_effect(baseline, tech, instrument="vln", dynamic="pp")
    assert isinstance(out, dict)
    assert out.get("refused")
