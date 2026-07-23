"""Ordinary baseline spline tests."""

from __future__ import annotations

import pandas as pd

from string_technique_model.extrapolation.nonlinear.baseline import fit_ordinary_baseline
from string_technique_model.extrapolation.register_builder import build_register_from_notes


def _ordinary_frame() -> pd.DataFrame:
    reg = build_register_from_notes("G3", "C6", "vln", "pp")
    rows = []
    for i, r in enumerate(reg):
        rows.append(
            {
                "instrument": "vln",
                "technique": "ordinary",
                "dynamic": "pp",
                "note": r["note"],
                "midi": r["midi"],
                "value": 50.0 * (0.97**i),
                "quantity": "EWSD_score_acoustic_balanced",
            }
        )
    return pd.DataFrame(rows)


def test_baseline_fit_and_predict_in_range() -> None:
    df = _ordinary_frame()
    fits = fit_ordinary_baseline(df)
    bf = fits.get("vln", "pp")
    assert bf is not None
    mean, outside = bf.predict(float(df.iloc[10]["midi"]))
    assert float(mean[0]) > 0
    assert not bool(outside[0])


def test_outside_baseline_range_flagged() -> None:
    df = _ordinary_frame()
    fits = fit_ordinary_baseline(df)
    bf = fits.get("vln", "pp")
    assert bf is not None
    _mean, outside = bf.predict(20.0)
    assert bool(outside[0])


def test_missing_instrument_dynamic_returns_none() -> None:
    df = pd.DataFrame(
        [
            {
                "instrument": "vln",
                "technique": "ordinary",
                "dynamic": "pp",
                "note": "A4",
                "midi": 69,
                "value": 20.0,
                "quantity": "EWSD_score_acoustic_balanced",
            },
            {
                "instrument": "vln",
                "technique": "ordinary",
                "dynamic": "pp",
                "note": "B4",
                "midi": 71,
                "value": 18.0,
                "quantity": "EWSD_score_acoustic_balanced",
            },
        ]
    )
    fits = fit_ordinary_baseline(df)
    assert fits.get("cb", "ff") is None
