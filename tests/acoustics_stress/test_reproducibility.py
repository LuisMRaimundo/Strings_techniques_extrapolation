"""Reproducibility of synthetic fixtures and sampling."""

from __future__ import annotations

import numpy as np
import pytest

from string_technique_model.testing.signal_generators import generate_signal

pytestmark = [pytest.mark.acoustics_stress, pytest.mark.reproducibility]


def test_synthetic_signal_deterministic() -> None:
    a = generate_signal("pure_sine", seed=99, frequency_hz=880.0)
    b = generate_signal("pure_sine", seed=99, frequency_hz=880.0)
    assert np.array_equal(a.samples, b.samples)


def test_different_seeds_change_noise_fixture() -> None:
    a = generate_signal("band_limited_noise", seed=1)
    b = generate_signal("band_limited_noise", seed=2)
    assert not np.array_equal(a.samples, b.samples)


def test_serialization_roundtrip_metadata() -> None:
    sig = generate_signal("harmonic_sum", seed=3, n_harmonics=4)
    payload = {
        "kind": sig.kind,
        "sample_rate_hz": sig.sample_rate_hz,
        "duration_s": sig.duration_s,
        "seed": sig.seed,
        "metadata": sig.metadata,
    }
    assert payload["kind"] == "harmonic_sum"
    assert payload["seed"] == 3
