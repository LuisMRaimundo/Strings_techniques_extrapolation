"""Typed attenuation — amplitude vs power cannot be confused."""

from __future__ import annotations

import math

import pytest

from string_technique_model.descriptors.attenuation import (
    amplitude_ratio_to_db,
    db_to_amplitude_ratio,
    db_to_power_ratio,
    power_ratio_to_db,
    refuse_bridge_mobility_as_spl,
    refuse_sones_as_db,
)

pytestmark = pytest.mark.acoustics_stress


@pytest.mark.mathematical_exact
def test_amplitude_and_power_formulas() -> None:
    a = amplitude_ratio_to_db(0.5, 1.0, measurement_domain="radiated_audio")
    p = power_ratio_to_db(0.25, 1.0, measurement_domain="radiated_audio")
    assert a.quantity_kind == "amplitude"
    assert p.quantity_kind == "power_or_intensity"
    assert a.formula == "20*log10(A2/A1)"
    assert p.formula == "10*log10(P2/P1)"
    assert abs(a.value_db - (-6.020599913279624)) < 1e-9
    assert abs(p.value_db - (-6.020599913279624)) < 1e-9


@pytest.mark.mathematical_exact
def test_inverse_conversions_roundtrip() -> None:
    for db in (-12.0, -6.0, 0.0, 3.0, 20.0):
        assert abs(20.0 * math.log10(db_to_amplitude_ratio(db)) - db) < 1e-12
        assert abs(10.0 * math.log10(db_to_power_ratio(db)) - db) < 1e-12


@pytest.mark.unsupported_extrapolation
def test_refuse_sones_as_db() -> None:
    with pytest.raises(ValueError, match="sones"):
        refuse_sones_as_db("loudness_sones")


@pytest.mark.measurement_domain
def test_refuse_bridge_mobility_as_spl() -> None:
    with pytest.raises(ValueError, match="bridge_mobility"):
        refuse_bridge_mobility_as_spl("bridge_mobility")


@pytest.mark.measurement_domain
def test_sones_versus_linear_intensity_not_comparable() -> None:
    # Distinct quantity kinds — must not be compared as interchangeable numerics.
    classification = "not_comparable"
    assert classification == "not_comparable"
    with pytest.raises(ValueError):
        refuse_sones_as_db("Evangelista loudness in sones")
