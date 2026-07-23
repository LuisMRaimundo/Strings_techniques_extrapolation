"""Seed / deterministic frequentist path."""

from __future__ import annotations

import math

from string_technique_model.extrapolation.nonlinear.prediction import predict_register
from string_technique_model.extrapolation.register_builder import build_register_from_notes


def _rows() -> list[dict]:
    reg = build_register_from_notes("G3", "C5", "vln", "pp")
    return [
        {
            "note": r["note"],
            "midi": r["midi"],
            "value": 22.0 * math.exp(-0.01 * i),
            "instrument": "vln",
            "dynamic": "pp",
            "technique": "ordinary",
            "quantity": "EWSD_score_acoustic_balanced",
        }
        for i, r in enumerate(reg)
    ]


def test_hierarchical_prediction_deterministic() -> None:
    a = predict_register(_rows(), technique="sul_tasto", instrument="vln", dynamic="pp", pitches=["A4"])
    b = predict_register(_rows(), technique="sul_tasto", instrument="vln", dynamic="pp", pitches=["A4"])
    assert a[0].estimate_mean == b[0].estimate_mean
    assert a[0].estimate_sd == b[0].estimate_sd
