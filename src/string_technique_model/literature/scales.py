"""Explicit numerical-scale distinctions. Never treat dB as a density multiplier."""

from __future__ import annotations

import math
from enum import Enum


class NumericalScale(str, Enum):
    LINEAR_AMPLITUDE_RATIO = "linear_amplitude_ratio"
    LINEAR_POWER_RATIO = "linear_power_ratio"
    AMPLITUDE_DECIBEL = "amplitude_decibel"
    POWER_DECIBEL = "decibel_power"
    RAW_DENSITY = "raw_density"
    LOG_DENSITY = "log_density"
    SPECTRAL_SLOPE = "spectral_slope"
    FREQUENCY_DEPENDENT_TRANSFER = "frequency_dependent_transfer"
    DIMENSIONLESS_RATIO = "dimensionless_ratio"


DENSITY_SCALES = frozenset(
    {
        NumericalScale.RAW_DENSITY.value,
        NumericalScale.LOG_DENSITY.value,
    }
)

DECIBEL_SCALES = frozenset(
    {
        NumericalScale.AMPLITUDE_DECIBEL.value,
        NumericalScale.POWER_DECIBEL.value,
        "decibel_amplitude",
        "decibel_power",
    }
)


def is_decibel_scale(scale: str | None) -> bool:
    if scale is None:
        return False
    return str(scale).lower() in {s.lower() for s in DECIBEL_SCALES} or "decibel" in str(scale).lower()


def is_density_scale(scale: str | None) -> bool:
    if scale is None:
        return False
    return str(scale).lower() in {s.value for s in DENSITY_SCALES} or str(scale).lower() in {
        "raw_density",
        "log_density",
        "density",
    }


def decibel_power_to_linear_power_ratio(db: float) -> float:
    """Convert power dB to linear power ratio. Not a density multiplier."""
    return 10.0 ** (db / 10.0)


def decibel_amplitude_to_linear_amplitude_ratio(db: float) -> float:
    return 10.0 ** (db / 20.0)


def refuse_db_as_density_multiplier(scale: str | None, operation_type: str | None) -> bool:
    """True when a value must not be used as a density multiplier."""
    if is_decibel_scale(scale):
        return True
    if operation_type in {"decibel_gain", "validity_bound", "range_constraint"}:
        return True
    return False


def assert_not_db_density(scale: str | None, *, context: str = "") -> None:
    if is_decibel_scale(scale):
        raise ValueError(
            f"Decibel scale must not be interpreted as density{(': ' + context) if context else ''}"
        )


def safe_log10(x: float) -> float:
    if x <= 0:
        raise ValueError("log10 requires positive argument")
    return math.log10(x)
