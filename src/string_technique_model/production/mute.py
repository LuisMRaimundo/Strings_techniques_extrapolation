"""Mute mass normalization."""

from __future__ import annotations

import re

_MASS_WITH_UNIT = re.compile(
    r"^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*(g|gram|grams|kg|kilogram|kilograms|mg|milligram|milligrams)\s*$",
    re.IGNORECASE,
)
_NUMERIC_ONLY = re.compile(r"^\s*([+-]?(?:\d+(?:\.\d*)?|\.\d+))\s*$")

_UNIT_TO_GRAMS: dict[str, float] = {
    "g": 1.0,
    "gram": 1.0,
    "grams": 1.0,
    "mg": 0.001,
    "milligram": 0.001,
    "milligrams": 0.001,
    "kg": 1000.0,
    "kilogram": 1000.0,
    "kilograms": 1000.0,
}


def normalize_mute_mass(value: str | float | int | None) -> tuple[float | None, str | None, list[str]]:
    """
    Parse mute mass strings such as ``35 g`` into grams.

    Returns ``(mute_mass_g, mass_raw, warnings)``. Numeric values without a
    recognized unit remain ``None`` for mass with a warning — they are not
    silently treated as grams.
    """
    warnings: list[str] = []
    if value is None:
        return None, None, warnings

    if isinstance(value, (int, float)):
        warnings.append(
            f"numeric mute mass {value} supplied without unit; mass_g left null"
        )
        return None, str(value), warnings

    text = str(value).strip()
    if not text:
        return None, None, warnings

    match_unit = _MASS_WITH_UNIT.match(text)
    if match_unit:
        amount = float(match_unit.group(1))
        unit = match_unit.group(2).lower()
        grams = amount * _UNIT_TO_GRAMS[unit]
        return grams, text, warnings

    match_numeric = _NUMERIC_ONLY.match(text)
    if match_numeric:
        warnings.append(
            f"mute mass {text!r} lacks unit; not silently interpreted as grams"
        )
        return None, text, warnings

    warnings.append(f"could not parse mute mass {text!r}")
    return None, text, warnings
