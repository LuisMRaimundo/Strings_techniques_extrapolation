"""Harmonic interval/order and sounding-pitch scope tests."""

from __future__ import annotations

import pytest

from string_technique_model.ontology import interval_to_order, normalize_touched_interval
from string_technique_model.production.harmonics import validate_harmonic_interval_order
from string_technique_model.production.models import HarmonicInstruction
from string_technique_model.testing.literature_oracles import physics_oracle_sounding_hz

pytestmark = pytest.mark.acoustics_stress


@pytest.mark.mathematical_exact
@pytest.mark.parametrize(
    "interval,order",
    [("P4", 4), ("M3", 5), ("m3", 6), ("P5", 3), ("perfect_fourth", 4)],
)
def test_interval_order_map(interval: str, order: int) -> None:
    assert interval_to_order(normalize_touched_interval(interval) or interval) == order


@pytest.mark.mathematical_exact
@pytest.mark.benchmark
def test_benchmark_c_interval_order_contradiction() -> None:
    result = validate_harmonic_interval_order("perfect_fifth", 4)
    assert result.ok is False
    assert result.errors


@pytest.mark.unsupported_extrapolation
@pytest.mark.benchmark
def test_benchmark_b_sounding_frequency_not_auto_computed() -> None:
    """Physics oracle: 220 Hz × 4 = 880 Hz; production API does not compute it."""
    assert physics_oracle_sounding_hz(220.0, 4) == 880.0
    hi = HarmonicInstruction(
        left_hand_regime="artificial_harmonic",
        harmonic_type="artificial",
        touched_interval="P4",
        harmonic_order=4,
        stopped_pitch_midi=57.0,  # A3-ish placeholder; no auto sounding fill
    )
    assert hi.sounding_pitch_midi is None
    assert hi.sounding_pitch_name is None


@pytest.mark.domain_boundary
@pytest.mark.adversarial
@pytest.mark.parametrize("order", [0, -1, 7])
def test_invalid_harmonic_orders(order: int) -> None:
    result = validate_harmonic_interval_order("P4", order)
    assert result.ok is False


@pytest.mark.unsupported_extrapolation
def test_harmonic_notation_does_not_imply_loudness() -> None:
    hi = HarmonicInstruction(
        left_hand_regime="artificial_harmonic",
        harmonic_type="artificial",
        harmonic_order=4,
    )
    assert not hasattr(hi, "loudness_sones")
    dumped = hi.model_dump()
    assert "loudness" not in dumped or dumped.get("loudness") is None
