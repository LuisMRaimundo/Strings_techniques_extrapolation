"""Metamorphic / property helpers for implemented calculations."""

from __future__ import annotations

import math
from typing import Any

import numpy as np

from string_technique_model.prediction.links import link_forward, link_inverse
from string_technique_model.prediction.operations import (
    amplitude_ratio_from_db,
    apply_operation,
    power_ratio_from_db,
)
from string_technique_model.production.bow_contact import compute_beta
from string_technique_model.testing.tolerance_profiles import abs_close, rel_close


def beta_scale_invariance(distance_m: float, length_m: float, factor: float) -> bool:
    if factor <= 0:
        raise ValueError("factor must be positive")
    b1 = compute_beta(distance_m, length_m)
    b2 = compute_beta(distance_m * factor, length_m * factor)
    return rel_close(b1, b2)


def beta_monotonic_in_distance(length_m: float = 0.6) -> bool:
    b_lo = compute_beta(0.02, length_m)
    b_hi = compute_beta(0.04, length_m)
    return b_hi > b_lo


def beta_increases_when_length_decreases(distance_m: float = 0.03) -> bool:
    b_long = compute_beta(distance_m, 0.70)
    b_short = compute_beta(distance_m, 0.50)
    return b_short > b_long


def link_roundtrip(link: str, values: np.ndarray) -> bool:
    eta, _ = link_forward(values, link)
    back = link_inverse(eta, link)
    return bool(np.allclose(back, values, rtol=1e-10, atol=1e-12))


def db_amplitude_roundtrip(db: float) -> bool:
    ratio = float(amplitude_ratio_from_db(db))
    recovered = 20.0 * math.log10(ratio)
    return abs_close(recovered, db)


def db_power_roundtrip(db: float) -> bool:
    ratio = float(power_ratio_from_db(db))
    recovered = 10.0 * math.log10(ratio)
    return abs_close(recovered, db)


def additive_vs_multiplicative_distinction(
    d0: float = 10.0,
    delta: float = 2.0,
    ratio: float = 1.5,
) -> dict[str, Any]:
    """Ensure additive density delta is not applied as η += delta under log link."""
    d = np.array([d0], dtype=float)
    eta, _ = link_forward(d, "log")
    eta_add, d_add, _ = apply_operation(
        operation_type="additive_difference",
        draws=np.array([delta]),
        eta=eta,
        d_ordinary=d,
        numerical_scale="density_ratio",
        link="log",
    )
    eta_mul, d_mul, _ = apply_operation(
        operation_type="multiplicative_ratio",
        draws=np.array([ratio]),
        eta=eta,
        d_ordinary=d,
        numerical_scale="density_ratio",
        link="log",
    )
    wrong_add_on_eta = float(eta[0] + delta)
    return {
        "d_add": float(d_add[0]),
        "expected_d_add": d0 + delta,
        "eta_add_differs_from_eta_plus_delta": not abs_close(float(eta_add[0]), wrong_add_on_eta),
        "d_mul": float(d_mul[0]),
        "expected_d_mul": d0 * ratio,
    }
