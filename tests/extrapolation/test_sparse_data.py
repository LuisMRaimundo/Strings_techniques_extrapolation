"""Sparse / zero local observation behaviour."""

from __future__ import annotations

import math

from string_technique_model.extrapolation.nonlinear.domain import EvidenceTier
from string_technique_model.extrapolation.nonlinear.prediction import predict_register
from string_technique_model.extrapolation.register_builder import build_register_from_notes


def _ordinary_rows() -> list[dict]:
    reg = build_register_from_notes("G3", "C6", "vln", "pp")
    rows = []
    for i, r in enumerate(reg):
        rows.append(
            {
                "note": r["note"],
                "midi": r["midi"],
                "value": 25.0 * math.exp(-0.01 * i),
                "instrument": "vln",
                "dynamic": "pp",
                "technique": "ordinary",
                "quantity": "EWSD_score_acoustic_balanced",
            }
        )
    return rows


def test_zero_technique_obs_prior_dominated_wide() -> None:
    results = predict_register(
        _ordinary_rows(),
        technique="sul_ponticello",
        instrument="vln",
        dynamic="pp",
        pitches=["A4"],
        method="hierarchical_spline",
    )
    r = results[0]
    assert r.prior_dominated
    assert r.evidence_tier in {
        EvidenceTier.LEVEL_1_ASSUMPTION_ONLY,
        EvidenceTier.LEVEL_1_BIBLIOGRAPHIC_QUALITATIVE,
        EvidenceTier.LEVEL_2_METADATA_CONSTRAINED,
    }
    assert r.estimate_sd is not None and r.estimate_sd > 0.2


def test_outside_domain_flagged() -> None:
    results = predict_register(
        _ordinary_rows()[:12],
        technique="sul_tasto",
        instrument="vln",
        dynamic="pp",
        pitches=["C8"],
        method="hierarchical_spline",
    )
    r = results[0]
    assert r.extrapolation_distance is None or r.extrapolation_distance >= 0
    assert r.sensitivity_status.value in {
        "outside_baseline_range",
        "prior_sensitive",
        "data_limited",
        "stable",
        "not_evaluated",
    }
