"""Typed attenuation / gain conversions — amplitude vs power cannot be confused."""

from __future__ import annotations

import math
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

QuantityKind = Literal["amplitude", "power_or_intensity"]


class AttenuationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    value_db: float
    quantity_kind: QuantityKind
    formula: str
    unit: str = "dB"
    measurement_domain: str
    warnings: list[str] = Field(default_factory=list)


def amplitude_ratio_to_db(a2: float, a1: float, *, measurement_domain: str) -> AttenuationResult:
    """dB = 20 log10(A2/A1)."""
    if a1 == 0:
        raise ValueError("a1 must be non-zero")
    if a2 < 0 or a1 < 0:
        raise ValueError("amplitudes must be non-negative for this conversion")
    if a2 == 0:
        value = float("-inf")
    else:
        value = 20.0 * math.log10(a2 / a1)
    return AttenuationResult(
        value_db=value,
        quantity_kind="amplitude",
        formula="20*log10(A2/A1)",
        measurement_domain=measurement_domain,
    )


def power_ratio_to_db(p2: float, p1: float, *, measurement_domain: str) -> AttenuationResult:
    """dB = 10 log10(P2/P1)."""
    if p1 == 0:
        raise ValueError("p1 must be non-zero")
    if p2 < 0 or p1 < 0:
        raise ValueError("power/intensity must be non-negative")
    if p2 == 0:
        value = float("-inf")
    else:
        value = 10.0 * math.log10(p2 / p1)
    return AttenuationResult(
        value_db=value,
        quantity_kind="power_or_intensity",
        formula="10*log10(P2/P1)",
        measurement_domain=measurement_domain,
    )


def db_to_amplitude_ratio(db: float) -> float:
    """A2/A1 = 10^(dB/20)."""
    return 10.0 ** (db / 20.0)


def db_to_power_ratio(db: float) -> float:
    """P2/P1 = 10^(dB/10)."""
    return 10.0 ** (db / 10.0)


def refuse_sones_as_db(label: str) -> None:
    if "sone" in label.lower():
        raise ValueError("sones must not be treated as decibels")


def refuse_bridge_mobility_as_spl(domain: str) -> None:
    if domain == "bridge_mobility":
        raise ValueError(
            "bridge_mobility attenuation must not be treated as radiated SPL attenuation"
        )
