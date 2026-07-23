"""Adversarial and malformed input stress tests."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from string_technique_model.prediction.requests import PredictionRequest
from string_technique_model.production.bow_contact import compute_beta
from string_technique_model.testing.signal_generators import generate_signal

pytestmark = [pytest.mark.acoustics_stress, pytest.mark.adversarial]


def test_empty_and_nan_signals() -> None:
    silence = generate_signal("silence", duration_s=0.01)
    assert silence.samples.size >= 1
    nan_sig = generate_signal("nan_contaminated", duration_s=0.05)
    with pytest.raises(ValueError):
        nan_sig.assert_finite()
    inf_sig = generate_signal("inf_contaminated", duration_s=0.05)
    with pytest.raises(ValueError):
        inf_sig.assert_finite()


def test_zero_and_negative_sample_rate_rejected() -> None:
    with pytest.raises(ValueError):
        generate_signal("pure_sine", sample_rate_hz=0)
    with pytest.raises(ValueError):
        generate_signal("pure_sine", sample_rate_hz=-44100)


def test_unknown_ontology_technique_on_request() -> None:
    with pytest.raises(ValidationError):
        PredictionRequest(instrument="vln", target_technique="not_a_real_technique")


def test_unknown_instrument_on_request() -> None:
    with pytest.raises(ValidationError):
        PredictionRequest(instrument="piano", target_technique="sul_ponticello")


def test_beta_does_not_coerce_invalid_silently() -> None:
    with pytest.raises(ValueError):
        compute_beta(0.1, 0.0)
