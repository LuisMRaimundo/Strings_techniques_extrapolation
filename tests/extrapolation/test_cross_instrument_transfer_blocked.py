"""Violin calibration must never silently feed viola/cello."""

from __future__ import annotations

from string_technique_model.extrapolation.nonlinear.harmonic_source_resolver import (
    clear_harmonic_calibration_cache,
    resolve_harmonic_value,
)
from string_technique_model.extrapolation.nonlinear.harmonic_support import HarmonicSupportClass


def setup_function() -> None:
    clear_harmonic_calibration_cache()


def test_viola_does_not_consume_violin_values_for_unshared_or_any_default() -> None:
    # Cello has no calibration → must be unsupported even if violin has the note
    res = resolve_harmonic_value(
        instrument="vlc",
        technique="artificial_harmonic",
        note="G5",
        dynamic="mf",
    )
    assert res.support_class == HarmonicSupportClass.UNSUPPORTED
    assert res.mean is None
    assert res.cross_instrument_transfer_enabled is False
    assert any(
        c.rejection_reason == "cross_instrument_transfer_disabled" for c in res.candidates
    )


def test_cross_instrument_flag_still_does_not_silently_transfer() -> None:
    res = resolve_harmonic_value(
        instrument="vlc",
        technique="artificial_harmonic",
        note="G5",
        dynamic="mf",
        allow_cross_instrument=True,
    )
    assert res.mean is None
    assert res.support_class == HarmonicSupportClass.UNSUPPORTED
    assert any(
        c.rejection_reason == "cross_instrument_transfer_not_implemented"
        for c in res.candidates
    )


def test_viola_artificial_uses_vla_source_instrument_only() -> None:
    res = resolve_harmonic_value(
        instrument="vla",
        technique="artificial_harmonic",
        note="A5",
        dynamic="mf",
    )
    assert res.mean is not None
    assert res.source_instrument == "vla"
    assert res.source_instrument != "vln"
    assert res.support_class in {
        HarmonicSupportClass.SAME_INSTRUMENT_SAME_COLLECTION_MEASURED,
        HarmonicSupportClass.SAME_INSTRUMENT_CROSS_COLLECTION_MEASURED,
    }
