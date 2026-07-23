"""Missing baseline / cross-instrument transfer guards."""

from __future__ import annotations

from string_technique_model.extrapolation.nonlinear.prediction import predict_register


def test_missing_baseline_returns_na() -> None:
    # Ordinary rows for violin; request cello
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
        technique="sul_ponticello",
        instrument="vlc",
        dynamic="pp",
        pitches=["A4"],
        method="hierarchical_spline",
    )
    assert results[0].posterior_mean is None
    assert results[0].na_reason in {"missing_baseline_or_pitch", "missing_baseline"}


def test_no_silent_violin_to_bass_transfer() -> None:
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
        technique="con_sordino",
        instrument="cb",
        dynamic="pp",
        pitches=["A4"],
        method="hierarchical_spline",
    )
    assert results[0].posterior_mean is None
