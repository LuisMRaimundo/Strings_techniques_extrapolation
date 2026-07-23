"""Bow-contact / beta stress tests."""

from __future__ import annotations

import pytest

from string_technique_model.production.bow_contact import compute_beta, validate_bow_contact
from string_technique_model.production.models import BowContactInstruction
from string_technique_model.testing.metamorphic_checks import (
    beta_increases_when_length_decreases,
    beta_monotonic_in_distance,
    beta_scale_invariance,
)
from string_technique_model.testing.tolerance_profiles import abs_close

pytestmark = pytest.mark.acoustics_stress


@pytest.mark.mathematical_exact
@pytest.mark.benchmark
def test_benchmark_a_beta_exact(benchmarks) -> None:
    b = benchmarks["A"]
    beta = compute_beta(b.inputs["bow_bridge_distance_m"], b.inputs["speaking_length_m"])
    assert abs_close(beta, b.expected["beta"])


@pytest.mark.mathematical_exact
def test_beta_unit_scale_invariance() -> None:
    assert beta_scale_invariance(0.03, 0.60, 1000.0)  # mm-scale factor


@pytest.mark.metamorphic
def test_beta_monotonic_properties() -> None:
    assert beta_monotonic_in_distance()
    assert beta_increases_when_length_decreases()


@pytest.mark.domain_boundary
@pytest.mark.adversarial
@pytest.mark.parametrize(
    "distance,length",
    [
        (0.03, 0.0),
        (0.03, -0.6),
        (-0.01, 0.6),
    ],
)
def test_beta_invalid_lengths_raise(distance: float, length: float) -> None:
    with pytest.raises(ValueError):
        compute_beta(distance, length)


@pytest.mark.domain_boundary
def test_beta_greater_than_one_warns_on_speaking_string() -> None:
    instr = BowContactInstruction(
        category="sul_ponticello",
        excitation_region="speaking_string",
        relative_bow_bridge_distance_beta=1.2,
        bow_bridge_distance_m=0.72,
        speaking_length_m=0.60,
    )
    result = validate_bow_contact(instr)
    # Contradiction or warning path — must not silently invent timbre
    assert result.errors or result.warnings


@pytest.mark.mathematical_exact
def test_beta_contradiction_detection() -> None:
    instr = BowContactInstruction(
        relative_bow_bridge_distance_beta=0.10,
        bow_bridge_distance_m=0.03,
        speaking_length_m=0.60,
        excitation_region="speaking_string",
    )
    result = validate_bow_contact(instr)
    assert any("contradiction" in e.lower() for e in result.errors)


@pytest.mark.unsupported_extrapolation
@pytest.mark.physical_plausibility
def test_beta_alone_does_not_force_centroid_or_ewsd() -> None:
    beta = compute_beta(0.03, 0.60)
    assert abs_close(beta, 0.05)
    # Scope: no API maps beta -> spectral centroid / EWSD in production helpers
    assert not hasattr(compute_beta, "to_centroid")
    assert not hasattr(compute_beta, "to_ewsd")
