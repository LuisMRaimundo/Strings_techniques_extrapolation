"""Operation and link stress tests."""

from __future__ import annotations

import numpy as np
import pytest

from string_technique_model.prediction.links import link_forward, link_inverse
from string_technique_model.prediction.operations import OperationError, apply_operation
from string_technique_model.testing.metamorphic_checks import (
    additive_vs_multiplicative_distinction,
    db_amplitude_roundtrip,
    db_power_roundtrip,
    link_roundtrip,
)

pytestmark = pytest.mark.acoustics_stress


@pytest.mark.mathematical_exact
@pytest.mark.parametrize("link", ["identity", "log"])
def test_link_roundtrip(link: str) -> None:
    values = np.array([0.1, 1.0, 10.0, 50.0])
    if link == "logit":
        values = np.array([0.1, 0.5, 0.9])
    assert link_roundtrip(link, values)


@pytest.mark.mathematical_exact
def test_logit_roundtrip_unit_interval() -> None:
    assert link_roundtrip("logit", np.array([0.01, 0.5, 0.99]))


@pytest.mark.mathematical_exact
def test_db_conversions() -> None:
    assert db_amplitude_roundtrip(-6.0)
    assert db_power_roundtrip(-3.0)


@pytest.mark.mathematical_exact
def test_additive_not_confused_with_eta_plus_delta() -> None:
    result = additive_vs_multiplicative_distinction()
    assert abs(result["d_add"] - result["expected_d_add"]) < 1e-12
    assert abs(result["d_mul"] - result["expected_d_mul"]) < 1e-12
    assert result["eta_add_differs_from_eta_plus_delta"] is True


@pytest.mark.domain_boundary
def test_multiplicative_rejects_nonpositive_ratio() -> None:
    d = np.array([10.0])
    eta, _ = link_forward(d, "log")
    with pytest.raises(OperationError):
        apply_operation(
            operation_type="multiplicative_ratio",
            draws=np.array([0.0]),
            eta=eta,
            d_ordinary=d,
            numerical_scale="density_ratio",
            link="log",
        )


@pytest.mark.unsupported_extrapolation
def test_decibel_ops_rejected_as_density() -> None:
    d = np.array([10.0])
    eta, _ = link_forward(d, "log")
    with pytest.raises(OperationError):
        apply_operation(
            operation_type="decibel_amplitude_gain",
            draws=np.array([-6.0]),
            eta=eta,
            d_ordinary=d,
            numerical_scale="amplitude_decibel",
            link="log",
        )


@pytest.mark.domain_boundary
def test_log_link_zero_rejected_tiny_positive_safeguarded() -> None:
    with pytest.raises(ValueError):
        link_forward(np.array([0.0]), "log")
    eta, app = link_forward(np.array([1e-20]), "log")
    assert np.isfinite(eta).all()
    assert app.numerical_safeguard_applied is True
    back = link_inverse(eta, "log")
    assert np.isfinite(back).all()
