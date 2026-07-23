"""Lightweight performance / scaling checks (not heavy benchmarks)."""

from __future__ import annotations

import time

import pytest

from string_technique_model.testing.signal_generators import generate_signal

pytestmark = [pytest.mark.acoustics_stress, pytest.mark.performance]


@pytest.mark.slow
def test_long_signal_generation_completes() -> None:
    t0 = time.perf_counter()
    sig = generate_signal("harmonic_sum", duration_s=2.0, sample_rate_hz=48000.0, seed=0)
    elapsed = time.perf_counter() - t0
    assert sig.samples.size == int(round(2.0 * 48000.0))
    assert elapsed < 5.0


def test_batch_fixture_generation_fast_path() -> None:
    t0 = time.perf_counter()
    for i in range(20):
        generate_signal("pure_sine", duration_s=0.05, seed=i)
    assert time.perf_counter() - t0 < 2.0
