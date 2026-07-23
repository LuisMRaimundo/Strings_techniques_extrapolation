"""M0 vs M1 comparison smoke test."""

from __future__ import annotations

import math

from string_technique_model.extrapolation.nonlinear.comparison import compare_models
from string_technique_model.extrapolation.register_builder import build_register_from_notes


def test_compare_models_runs() -> None:
    reg = build_register_from_notes("G3", "A5", "vln", "pp")
    rows = []
    for i, r in enumerate(reg):
        rows.append(
            {
                "note": r["note"],
                "midi": r["midi"],
                "value": 30.0 * math.exp(-0.008 * i),
                "instrument": "vln",
                "dynamic": "pp",
                "technique": "ordinary",
                "quantity": "EWSD_score_acoustic_balanced",
            }
        )
    cmp_ = compare_models(rows, technique="sul_ponticello", instrument="vln", dynamic="pp")
    assert cmp_.status in {"completed", "insufficient_for_comparison", "skipped"}
    assert cmp_.m0_model_id.startswith("M0")
    assert cmp_.m1_model_id.startswith("M1")
