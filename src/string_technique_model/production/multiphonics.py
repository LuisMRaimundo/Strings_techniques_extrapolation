"""Helpers distinguishing multiphonics from ordinary harmonic techniques."""

from __future__ import annotations

_ORDINARY_HARMONIC_KINDS = frozenset(
    {
        "natural_harmonic",
        "artificial_harmonic",
        "half_harmonic",
        "natural_harmonic_glissando",
        "artificial_harmonic_glissando",
        "double_stop",
    }
)

_MULTIPHONIC_KIND = "multiphonic"


def assert_distinct_from_harmonics(kind: str) -> None:
    """
    Raise if ``kind`` labels an ordinary harmonic technique rather than a multiphonic.

    Multiphonics are not natural/artificial/half harmonics, double stops, or harmonic glissandi.
    """
    normalized = kind.strip().lower()
    if normalized in _ORDINARY_HARMONIC_KINDS:
        raise ValueError(
            f"technique kind {kind!r} is an ordinary harmonic label; "
            "multiphonics must not be classified as natural/artificial/half harmonics, "
            "double stops, or harmonic glissandi"
        )
    if normalized != _MULTIPHONIC_KIND:
        raise ValueError(
            f"technique kind {kind!r} is not recognized as multiphonic; "
            f"expected {_MULTIPHONIC_KIND!r}"
        )
