"""Evidence-tier and evidence-only gating."""

from __future__ import annotations

from string_technique_model.extrapolation.nonlinear.bayesian_backend import check_backend
from string_technique_model.extrapolation.nonlinear.descriptor_model import ewsd_mapping_status
from string_technique_model.extrapolation.nonlinear.domain import EvidenceTier, ValueKind
from string_technique_model.extrapolation.nonlinear.prediction import predict_register


def test_evidence_only_returns_qualitative_na() -> None:
    rows = [
        {
            "note": "A4",
            "midi": 69,
            "value": 10.0,
            "instrument": "vln",
            "dynamic": "pp",
            "technique": "ordinary",
            "quantity": "EWSD_score_acoustic_balanced",
        },
        {
            "note": "B4",
            "midi": 71,
            "value": 9.0,
            "instrument": "vln",
            "dynamic": "pp",
            "technique": "ordinary",
            "quantity": "EWSD_score_acoustic_balanced",
        },
    ]
    results = predict_register(
        rows,
        technique="sul_ponticello",
        instrument="vln",
        dynamic="pp",
        pitches=["A4"],
        method="evidence_only",
    )
    assert results[0].value_kind == ValueKind.QUALITATIVE_ONLY
    assert results[0].posterior_mean is None
    assert results[0].evidence_tier == EvidenceTier.LEVEL_1_BIBLIOGRAPHIC_QUALITATIVE


def test_ewsd_mapping_status_documented() -> None:
    status = ewsd_mapping_status("EWSD_score_acoustic_balanced")
    assert status in {"observed_scalar_direct_model", "validated_transfer_function_F", "mapping_unresolved"}


def test_bayes_backend_honest_unavailable() -> None:
    status = check_backend()
    if not status.available:
        assert status.capability_status == "bayesian_backend_unavailable"
